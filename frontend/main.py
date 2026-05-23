import os
import json
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
import requests
import clickhouse_connect
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Groq AI client ────────────────────────────────────────────────────────────
_GROQ = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

app = Flask(
    __name__,
    static_folder="static",
    static_url_path=""
)

NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"
FALLBACK_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "zillow_fallback.json")

# ── ClickHouse ────────────────────────────────────────────────────────────────

def _get_ch_client():
    raw = os.getenv("CLICKHOUSE_HOST", "").replace("https://", "").replace("http://", "")
    host, _, port_s = raw.partition(":")
    return clickhouse_connect.get_client(
        host=host,
        port=int(port_s or 8443),
        username="default",
        password=os.getenv("CLICKHOUSE_PASSWORD"),
        secure=True,
    )

_ELEVATOR_HINTS = ["Tower", "Urby", "Riverbank", "Worth", "Monarch", "Aldyn", "Ashley", "Gateway", "Waterside", "Avalon"]
_PET_HINTS = ["Urby", "Archer", "AVA", "Avalon", "Kensington"]

def get_listings_from_clickhouse(budget: float, borough: str) -> List[Dict[str, Any]]:
    try:
        client = _get_ch_client()
        # Fetch up to budget + 20% so the scoring engine can gently penalise slightly-over listings
        ceiling = int(budget * 1.20) if budget > 0 else 99999
        conditions = [f"price_per_month IS NOT NULL", f"price_per_month <= {ceiling}"]
        if borough and borough.lower() not in ("all", "open to all", ""):
            safe_borough = borough.replace("'", "''")
            conditions.append(f"address ILIKE '%{safe_borough}%'")
        where = " AND ".join(conditions)
        rows = client.query(
            f"SELECT address, price_per_month, beds, baths, sqft, link "
            f"FROM listings WHERE {where} ORDER BY price_per_month ASC LIMIT 100"
        ).result_rows
        listings = []
        for r in rows:
            address = r[0]
            listings.append({
                "address": address,
                "price_per_month": r[1],
                "beds": r[2],
                "baths": r[3],
                "sqft": r[4],
                "link": r[5],
                "is_elevator": any(h.lower() in address.lower() for h in _ELEVATOR_HINTS),
                "is_pet_friendly": any(h.lower() in address.lower() for h in _PET_HINTS),
            })
        print(f"ClickHouse returned {len(listings)} listings.")
        return listings
    except Exception as e:
        print(f"ClickHouse query failed: {e}")
        return []

# Zillow Scraping helpers based on seniors_houses
def parse_price(text: str) -> Optional[int]:
    match = re.search(r"\$[\d,]+", text)
    if match:
        return int(match.group().replace("$", "").replace(",", ""))
    return None

def build_link(card) -> str:
    link_el = card.find("a", href=True)
    if not link_el:
        return ""
    href = link_el["href"]
    return "https://www.zillow.com" + href if href.startswith("/") else href

def parse_card(card) -> Dict[str, Any]:
    address_el = card.find("address")
    address = address_el.get_text(strip=True) if address_el else "N/A"

    price_el = card.find("span", class_="srp-bueOgM")
    price_text = price_el.get_text(strip=True) if price_el else ""
    price = parse_price(price_text)

    card_text = card.get_text(" ", strip=True)
    beds = re.search(r"(\d+)\s*bd", card_text)
    baths = re.search(r"(\d+)\s*ba", card_text)
    sqft = re.search(r"([\d,]+)\s*sqft", card_text)

    # Simple heuristic to check if it has elevator based on common high-rise building names
    building_indicators = ["Tower", "Urby", "Riverbank", "Worth", "Monarch", "Aldyn", "Ashley", "Gateway", "Waterside", "Avalon"]
    is_elevator = any(ind.lower() in address.lower() for ind in building_indicators)

    # Simple pet friendly heuristics based on building types or address
    is_pet_friendly = any(ind.lower() in address.lower() for ind in ["Urby", "Archer", "AVA", "Avalon", "Kensington"])

    return {
        "address": address,
        "price_per_month": price,
        "beds": int(beds.group(1)) if beds else 1 if "studio" in card_text.lower() else None,
        "baths": int(baths.group(1)) if baths else None,
        "sqft": int(sqft.group(1).replace(",", "")) if sqft else None,
        "link": build_link(card),
        "is_elevator": is_elevator,
        "is_pet_friendly": is_pet_friendly
    }

def scrape_zillow_listings(api_key: str, budget: float, borough: str) -> List[Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    # Construct Zillow URL based on Borough
    borough_slug = "new-york-ny"
    if borough.lower() == "manhattan":
        borough_slug = "manhattan-new-york-ny"
    elif borough.lower() == "brooklyn":
        borough_slug = "brooklyn-new-york-ny"
    elif borough.lower() == "queens":
        borough_slug = "queens-new-york-ny"
    elif borough.lower() == "bronx":
        borough_slug = "bronx-new-york-ny"

    url = f"https://www.zillow.com/{borough_slug}/rentals/"
    print(f"Scraping Zillow via Nimble: {url}")

    payload = {
        "url": url,
        "render": True,
        "country": "US",
        "locale": "en",
    }

    try:
        response = requests.post(NIMBLE_EXTRACT_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        html = response.json().get("data", {}).get("html", "")
        
        if not html:
            print("No HTML returned from Nimble.")
            return []

        soup = BeautifulSoup(html, "html.parser")
        listings = []
        for card in soup.find_all("article"):
            try:
                listings.append(parse_card(card))
            except Exception as e:
                print(f"Failed parsing card: {e}")
                continue
        return listings
    except Exception as e:
        print(f"Live scrape failed: {e}")
        return []

# Custom scoring engine
def calculate_scores(listings: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    scored_listings = []

    budget = float(profile.get("budget", 2000))
    needs_transit = bool(profile.get("needs_transit", True))
    lifestyle = str(profile.get("lifestyle", "space"))
    borough_pref = str(profile.get("borough", "all")).lower()

    for listing in listings:
        addr = listing.get("address", "").lower()
        price = listing.get("price_per_month")
        
        if not price:
            continue

        # 1. Budget Score (25% Weight)
        if price <= budget:
            budget_score = 100.0
        elif price <= budget + 300:
            # Scaled down from 100% to 20%
            budget_score = 100.0 - ((price - budget) / 300.0) * 80.0
        else:
            budget_score = 0.0

        # Filter out extremely over-budget apartments
        if budget_score < 10.0:
            continue

        # 2. Borough Match Score (20% Weight)
        listing_borough = "unknown"
        if "manhattan" in addr or "new york, ny" in addr:
            listing_borough = "manhattan"
        elif "brooklyn" in addr:
            listing_borough = "brooklyn"
        elif "queens" in addr or "astoria" in addr or "flushing" in addr or "rego park" in addr or "jamaica" in addr or "ozone park" in addr or "bayside" in addr or "bellerose" in addr or "whitestone" in addr:
            listing_borough = "queens"
        elif "bronx" in addr:
            listing_borough = "bronx"
        elif "staten island" in addr:
            listing_borough = "staten island"

        if borough_pref == "all" or borough_pref == "open to all" or borough_pref == "":
            borough_score = 100.0
        elif borough_pref in listing_borough:
            borough_score = 100.0
        else:
            borough_score = 15.0  # Penalize heavy but keep in list in case other scores are outstanding

        # 3. Transit Score (15% Weight)
        if needs_transit:
            # High-transit locations get great scores
            if listing_borough in ["manhattan", "brooklyn"]:
                transit_score = 100.0
            elif "astoria" in addr or "rego park" in addr or "jamaica" in addr:
                transit_score = 90.0
            elif "flushing" in addr or "bronx" in addr:
                transit_score = 80.0
            else:
                transit_score = 50.0  # Outer areas/Staten Island
        else:
            transit_score = 100.0

        # 4. Lifestyle Score (20% Weight)
        lifestyle_score = 50.0  # neutral starting point
        lifestyle_details = ""

        if lifestyle == "space":
            beds = listing.get("beds") or 1
            sqft = listing.get("sqft")
            if sqft:
                lifestyle_score = min(100.0, (sqft / 1000.0) * 100.0)
                lifestyle_details = f"Generous {sqft} sqft layout offers ample room."
            else:
                lifestyle_score = 60.0 + (beds * 15.0)
                lifestyle_score = min(100.0, lifestyle_score)
                lifestyle_details = f"{beds} Bedroom layout provides good space efficiency."

        elif lifestyle == "commute":
            # Estimate commute from listing borough to work borough
            if listing_borough == work_borough:
                lifestyle_score = 100.0
                lifestyle_details = "Located in the same borough as your work, promising a short commute."
            elif (listing_borough == "queens" and work_borough == "manhattan") or (listing_borough == "manhattan" and work_borough == "queens"):
                lifestyle_score = 80.0
                lifestyle_details = "Direct subway transit links to your work location."
            elif (listing_borough == "brooklyn" and work_borough == "manhattan") or (listing_borough == "manhattan" and work_borough == "brooklyn"):
                lifestyle_score = 85.0
                lifestyle_details = "Direct train links connecting Brooklyn to your Manhattan work."
            elif (listing_borough == "bronx" and work_borough == "manhattan") or (listing_borough == "manhattan" and work_borough == "bronx"):
                lifestyle_score = 75.0
                lifestyle_details = "Easy subway commute options straight down to Manhattan."
            else:
                lifestyle_score = 45.0
                lifestyle_details = "Commuting from this area might take 45-60 minutes."

        elif lifestyle == "park":
            green_indicators = ["riverside", "park", "ocean pkwy", "beach", "bay ridge", "flushing", "bayside", "whitestone"]
            if any(ind in addr for ind in green_indicators):
                lifestyle_score = 100.0
                lifestyle_details = "Located near outstanding green parks or coastal areas for fresh air."
            else:
                lifestyle_score = 65.0
                lifestyle_details = "Standard residential neighborhood with neighborhood park access."

        elif lifestyle == "nightlife":
            nightlife_neighborhoods = ["astoria", "williamsburg", "brooklyn, ny", "manhattan", "43rd st", "66th st", "worth st", "high line"]
            if any(n in addr for n in nightlife_neighborhoods):
                lifestyle_score = 100.0
                lifestyle_details = "Vibrant local scene with trendy cafes, bars, and evening entertainment."
            else:
                lifestyle_score = 40.0
                lifestyle_details = "Very quiet residential enclave; nightlife requires transit travel."

        elif lifestyle == "quiet":
            quiet_areas = ["whitestone", "bellerose", "bayside", "south ozone", "rego park", "staten island", "jamaica"]
            if any(q in addr for q in quiet_areas):
                lifestyle_score = 100.0
                lifestyle_details = "Peaceful, low-density neighborhood perfect for rest and focus."
            elif listing_borough == "manhattan":
                lifestyle_score = 50.0
                lifestyle_details = "Active Manhattan area; urban noise is expected."
            else:
                lifestyle_score = 75.0
                lifestyle_details = "Calm residential street with standard ambient city noise."

        # Calculate weighted overall score (budget 30%, borough 25%, transit 20%, lifestyle 25%)
        overall_score = (
            budget_score * 0.30 +
            borough_score * 0.25 +
            transit_score * 0.20 +
            lifestyle_score * 0.25
        )

        scored_listings.append({
            **listing,
            "overall_score": round(overall_score, 1),
            "breakdown": {
                "budget": round(budget_score, 1),
                "borough": round(borough_score, 1),
                "transit": round(transit_score, 1),
                "lifestyle": round(lifestyle_score, 1),
            },
            "lifestyle_details": lifestyle_details,
            "borough_name": listing_borough.capitalize()
        })

    # Sort by overall score descending
    scored_listings.sort(key=lambda x: x["overall_score"], reverse=True)
    return scored_listings

def _build_listings_summary(matches: List[Dict[str, Any]]) -> str:
    lines = []
    for i, l in enumerate(matches[:5], 1):
        beds = l.get("beds") or "Studio"
        baths = l.get("baths", "?")
        sqft = f"{l['sqft']} sqft" if l.get("sqft") else "size N/A"
        lines.append(
            f"{i}. {l['address']} — ${l['price_per_month']}/mo | "
            f"{beds} bed, {baths} bath, {sqft} | Score: {l['overall_score']}%"
        )
    return "\n".join(lines)


def generate_ai_concierge_report(matches: List[Dict[str, Any]], profile: Dict[str, Any]) -> str:
    if not matches:
        return "I could not find any properties that match your budget and criteria. Please try broadening your filters!"

    budget = profile.get("budget", 2000)
    lifestyle = profile.get("lifestyle", "space")
    needs_transit = profile.get("needs_transit", False)
    has_pets = profile.get("has_pets", False)
    elevator_only = profile.get("elevator_only", False)
    borough = profile.get("borough") or "no preference"
    work_location = profile.get("work_location") or "not specified"

    listings_summary = _build_listings_summary(matches)

    prompt = (
        "You are SeniorGuide AI, a warm and knowledgeable housing concierge helping seniors "
        "find the perfect home in New York City.\n\n"
        f"The senior's profile:\n"
        f"- Monthly budget: ${budget}\n"
        f"- Preferred borough: {borough}\n"
        f"- Lifestyle priority: {lifestyle}\n"
        f"- Needs good public transit: {'Yes' if needs_transit else 'No'}\n"
        f"- Has pets: {'Yes' if has_pets else 'No'}\n"
        f"- Elevator required: {'Yes' if elevator_only else 'No'}\n"
        f"- Work / volunteer location: {work_location}\n\n"
        f"Top matching listings (already scored and ranked for this senior):\n"
        f"{listings_summary}\n\n"
        "Write a warm, personal concierge report in markdown (3-4 paragraphs). "
        "Use ### for the main heading and #### for sub-headings. "
        "Highlight the #1 recommendation by name, explain why it fits their lifestyle, "
        "mention transit access if they need it, pets or elevator if relevant, "
        "and close with an encouraging note. Keep language simple and friendly for seniors."
    )

    try:
        response = _GROQ.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=900,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq AI call failed: {e}. Using template fallback.")
        return _template_concierge_report(matches, profile)


def _template_concierge_report(matches: List[Dict[str, Any]], profile: Dict[str, Any]) -> str:
    top = matches[0]
    borough = top["borough_name"]
    price = top["price_per_month"]
    address = top["address"]
    budget_pref = float(profile.get("budget", 2000))
    lifestyle_pref = str(profile.get("lifestyle", "space"))
    lifestyle_phrase = {
        "space": "gaining spacious interiors and high square footage for comfortable living",
        "commute": "prioritizing a direct, highly convenient commute to your work",
        "park": "staying close to lush community parks, coastal beaches, and nature walks",
        "nightlife": "living in the heart of NYC's dynamic evening spots and boutique dining",
        "quiet": "enjoying a calm, peaceful, and noise-sheltered sanctuary",
    }.get(lifestyle_pref, "finding an exceptional neighborhood fit")
    return (
        f"### Your Personal AI Housing Concierge Report\n\n"
        f"Based on your monthly budget of **${budget_pref}** and your desire for "
        f"**{lifestyle_phrase}**, I've identified **{borough}** as your best match.\n\n"
        f"#### Top Recommendation\n"
        f"**{address}** scores **{top['overall_score']}%** on our compatibility index "
        f"at **${price}/mo**.\n\n"
        f"*Click the listing card below to view full details on Zillow.*"
    )

@app.post("/api/match")
def match_apartments():
    profile = request.json
    if not profile:
        return jsonify({"status": "error", "message": "Missing JSON request body"}), 400

    budget = float(profile.get("budget", 2000))
    borough = str(profile.get("borough", "all"))
    nimble_api_key = profile.get("nimble_api_key")

    listings = []

    # 1. Primary source: ClickHouse (pre-loaded real NYC rental data)
    print("Querying ClickHouse for listings...")
    listings = get_listings_from_clickhouse(budget, borough)

    # 2. Live Nimble scrape if ClickHouse returned nothing and user supplied API key
    if not listings and nimble_api_key:
        try:
            print("Falling back to live Zillow scrape via Nimble...")
            listings = scrape_zillow_listings(nimble_api_key, budget, borough)
        except Exception as e:
            print(f"Live scrape failed: {e}")

    # 3. Local JSON fallback as last resort
    if not listings:
        print("Using local pre-scraped Zillow dataset fallback...")
        if os.path.exists(FALLBACK_DATA_PATH):
            with open(FALLBACK_DATA_PATH, "r", encoding="utf-8") as f:
                fallback_data = json.load(f)
                listings = fallback_data.get("listings", [])
        else:
            return jsonify({
                "status": "error",
                "message": "No data available. ClickHouse unavailable and no fallback found."
            }), 500

    # 2. Score listings based on user profile
    matches = calculate_scores(listings, profile)

    if not matches:
        return jsonify({"status": "error", "message": "No matching apartments found. Please increase your budget or adjust filters."}), 44

    # 3. Generate plain-language AI concierge report
    concierge_report = generate_ai_concierge_report(matches, profile)

    # 4. Limit to top 15 results for performance
    top_matches = matches[:15]

    return jsonify({
        "status": "success",
        "total_results": len(matches),
        "concierge_report": concierge_report,
        "matches": top_matches
    })

# Serve Frontend static files
@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

if __name__ == "__main__":
    # Default local dev port
    app.run(host="127.0.0.1", port=8000, debug=True)
