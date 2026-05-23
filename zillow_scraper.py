import json
import os
import re
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests

load_dotenv()

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"

CITY = "New York, NY"
PAGES = 5
ZILLOW_BASE_URL = "https://www.zillow.com/new-york-ny/rentals/{page}_p/"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {NIMBLE_API_KEY}",
}


def fetch_page(page_num):
    if page_num > 1:
        url = ZILLOW_BASE_URL.format(page=page_num)
    else:
        url = ZILLOW_BASE_URL.format(page=1).replace("/1_p/", "/")
    print(f"  Fetching page {page_num}: {url}")
    payload = {
        "url": url,
        "render": True,
        "country": "US",
        "locale": "en",
    }
    response = requests.post(NIMBLE_EXTRACT_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    return response.json().get("data", {}).get("html", "")


def parse_price(text):
    match = re.search(r"\$[\d,]+", text)
    if match:
        return int(match.group().replace("$", "").replace(",", ""))
    return None


def build_link(card):
    link_el = card.find("a", href=True)
    if not link_el:
        return ""
    href = link_el["href"]
    return "https://www.zillow.com" + href if href.startswith("/") else href


def clean_address(raw):
    if raw.lower().startswith("(undisclosed"):
        # extract the neighborhood/city/zip after the comma
        parts = raw.split(",", 1)
        return parts[1].strip() if len(parts) > 1 else raw
    return raw


def parse_card(card):
    address_el = card.find("address")
    address = clean_address(address_el.get_text(strip=True)) if address_el else "N/A"

    price_el = card.find("span", class_="srp-bueOgM")
    price_text = price_el.get_text(strip=True) if price_el else ""
    price = parse_price(price_text)

    card_text = card.get_text(" ", strip=True)
    beds = re.search(r"(\d+)\s*bd", card_text)
    baths = re.search(r"(\d+)\s*ba", card_text)
    sqft = re.search(r"([\d,]+)\s*sqft", card_text)

    return {
        "address": address,
        "price_per_month": price,
        "beds": int(beds.group(1)) if beds else None,
        "baths": int(baths.group(1)) if baths else None,
        "sqft": int(sqft.group(1).replace(",", "")) if sqft else None,
        "link": build_link(card),
    }


def parse_listings(html):
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.find_all("article"):
        try:
            listings.append(parse_card(card))
        except (AttributeError, KeyError, ValueError):
            continue
    return listings



def scrape_all_pages():
    all_listings = []
    seen_addresses = set()

    for page_num in range(1, PAGES + 1):
        html = fetch_page(page_num)
        if not html:
            print(f"  No HTML on page {page_num}, stopping.")
            break

        page_listings = parse_listings(html)
        new = [l for l in page_listings if l["address"] not in seen_addresses]

        if not new:
            print(f"  No new listings on page {page_num}, stopping.")
            break

        seen_addresses.update(l["address"] for l in new)
        all_listings.extend(new)
        print(f"  Page {page_num}: {len(new)} new listings (total: {len(all_listings)})")

        if page_num < PAGES:
            time.sleep(1)

    return all_listings


def main():
    print("=== Zillow Housing Scraper ===")
    print(f"City:  {CITY}")
    print(f"Pages: {PAGES}\n")

    all_listings = scrape_all_pages()

    print(f"\nTotal listings found: {len(all_listings)}")

    output = {
        "city": CITY,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total_found": len(all_listings),
        "listings": all_listings,
    }

    with open("zillow_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to zillow_results.json")
    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    main()
