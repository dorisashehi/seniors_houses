import json
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests

load_dotenv()

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
NIMBLE_SEARCH_URL = "https://sdk.nimbleway.com/v1/search"
NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"

STATE = "New York"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {NIMBLE_API_KEY}",
}

NY_COUNTIES = [
    "New York County", "Kings County", "Queens County",
    "Bronx County", "Richmond County", "Nassau County",
    "Suffolk County", "Westchester County", "Rockland County",
    "Orange County",
]


def search_tax_rate(county):
    payload = {
        "query": f"{county} New York property tax rate 2024",
        "country": "US",
    }
    response = requests.post(NIMBLE_SEARCH_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def extract_rate_from_text(text):
    match = re.search(r"(\d+\.?\d*)\s*%", text)
    if match:
        rate = float(match.group(1))
        if 0.1 < rate < 5.0:
            return rate
    return None


def extract_dollar(text):
    match = re.search(r"\$[\d,]+", text)
    if match:
        return int(match.group().replace("$", "").replace(",", ""))
    return None


def scrape_county(county):
    print(f"  Searching: {county}...")
    data = search_tax_rate(county)

    results = data.get("results", [])
    if not results:
        return {"county": county, "tax_rate_pct": None, "source": None}

    # scan top results for a tax rate
    for result in results[:5]:
        snippet = result.get("description", "") + " " + result.get("title", "")
        rate = extract_rate_from_text(snippet)
        if rate:
            return {
                "county": county,
                "tax_rate_pct": rate,
                "source": result.get("url"),
                "snippet": snippet[:200],
            }

    return {"county": county, "tax_rate_pct": None, "source": results[0].get("url") if results else None}


def fetch_smartasset_page():
    url = "https://smartasset.com/taxes/new-york-property-tax"
    print(f"Trying SmartAsset direct page: {url}")
    payload = {"url": url, "render": True, "country": "US", "locale": "en"}
    response = requests.post(NIMBLE_EXTRACT_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    html = response.json().get("data", {}).get("html", "")

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    if "page not found" in text.lower() or len(text) < 500:
        print("  SmartAsset page unavailable, falling back to search.")

        return []

    # try to extract table rows with county + rate
    results = []
    for row in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) >= 2:
            rate = extract_rate_from_text(cells[1] if len(cells) > 1 else "")
            if rate:
                results.append({
                    "county": cells[0],
                    "tax_rate_pct": rate,
                    "median_home_value": extract_dollar(cells[2]) if len(cells) > 2 else None,
                    "median_annual_tax": extract_dollar(cells[3]) if len(cells) > 3 else None,
                    "source": url,
                })
    return results


def main():
    print("=== Property Tax Scraper — New York ===\n")

    counties = fetch_smartasset_page()

    if not counties:
        print("\nFalling back: searching each county via Nimble Search...\n")
        counties = [scrape_county(c) for c in NY_COUNTIES]

    counties = [c for c in counties if c.get("tax_rate_pct")]
    counties.sort(key=lambda x: x["tax_rate_pct"])

    print(f"\nCounties with tax rate data: {len(counties)}")

    output = {
        "state": STATE,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total_counties": len(counties),
        "property_taxes": counties,
    }

    with open("property_tax_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to property_tax_results.json")
    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    main()
