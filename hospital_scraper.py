import json
import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests

load_dotenv()

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"

STATE = "NY"
CITY = "New York"
PAGE_SIZE = 100
TOTAL_PAGES = 5

# Medicare CMS Hospital General Information open data API
CMS_API_BASE = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
    "?conditions[0][property]=state"
    "&conditions[0][value]=NY"
    "&conditions[0][operator]=="
    f"&limit={PAGE_SIZE}"
    "&offset={offset}"
)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {NIMBLE_API_KEY}",
}


def fetch_page(offset):
    url = CMS_API_BASE.format(offset=offset)
    print(f"  Fetching records {offset}–{offset + PAGE_SIZE}...")
    payload = {"url": url, "render": False, "country": "US"}
    response = requests.post(NIMBLE_EXTRACT_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    html = response.json().get("data", {}).get("html", "")

    # CMS returns JSON directly — parse it from the response body
    match = re.search(r"\{.*\}", html, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {}


def parse_hospital(record):
    return {
        "facility_id": record.get("facility_id"),
        "name": record.get("facility_name"),
        "address": record.get("address"),
        "city": record.get("citytown"),
        "state": record.get("state"),
        "zip_code": record.get("zip_code"),
        "county": record.get("countyparish"),
        "phone": record.get("telephone_number"),
        "hospital_type": record.get("hospital_type"),
        "ownership": record.get("hospital_ownership"),
        "emergency_services": record.get("emergency_services") == "Yes",
        "overall_rating": (
            int(record["hospital_overall_rating"])
            if record.get("hospital_overall_rating", "").isdigit()
            else None
        ),
    }


def main():
    print(f"=== Hospital Scraper — {CITY} (Medicare Care Compare) ===\n")

    all_hospitals = []

    for page in range(TOTAL_PAGES):
        offset = page * PAGE_SIZE
        data = fetch_page(offset)
        records = data.get("results", [])

        if not records:
            print(f"  No more records at offset {offset}, stopping.")
            break

        parsed = [parse_hospital(r) for r in records]
        all_hospitals.extend(parsed)
        print(f"  Page {page + 1}: {len(records)} hospitals (total: {len(all_hospitals)})")

        if len(records) < PAGE_SIZE:
            break

    # sort by rating descending (None last)
    all_hospitals.sort(
        key=lambda h: h["overall_rating"] if h["overall_rating"] else 0,
        reverse=True,
    )

    rated = [h for h in all_hospitals if h["overall_rating"]]
    with_er = [h for h in all_hospitals if h["emergency_services"]]

    print(f"\nTotal hospitals: {len(all_hospitals)}")
    print(f"With ratings:    {len(rated)}")
    print(f"With ER:         {len(with_er)}")

    output = {
        "state": STATE,
        "source": "medicare.gov/care-compare via CMS Open Data API",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total_hospitals": len(all_hospitals),
        "hospitals": all_hospitals,
    }

    with open("hospital_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to hospital_results.json")
    print("\nTop 5 rated hospitals:")
    for h in rated[:5]:
        print(f"  ⭐ {h['overall_rating']}/5 — {h['name']} ({h['city']})")

    return output


if __name__ == "__main__":
    main()
