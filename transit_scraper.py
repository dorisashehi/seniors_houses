import json
import os
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests

load_dotenv()

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
NIMBLE_SEARCH_URL = "https://sdk.nimbleway.com/v1/search"
NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"

CITY = "New York"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {NIMBLE_API_KEY}",
}

NYC_TRANSIT_SEARCHES = [
    ("subway_lines", "New York City MTA subway lines routes list 2024"),
    ("bus_routes",   "New York City MTA bus routes list boroughs 2024"),
    ("subway_stops", "New York City subway stations stops list all boroughs"),
    ("bus_stops",    "New York City major bus stops terminals hubs locations"),
]


def nimble_search(query):
    payload = {"query": query, "country": "US"}
    response = requests.post(NIMBLE_SEARCH_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    return response.json().get("results", [])


def nimble_extract(url):
    payload = {"url": url, "render": True, "country": "US", "locale": "en"}
    response = requests.post(NIMBLE_EXTRACT_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    return response.json().get("data", {}).get("html", "")


def extract_snippets(results):
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in results[:5]
    ]


def scrape_mta_routes():
    print("Fetching MTA subway lines from transit.land via Nimble...")
    html = nimble_extract("https://www.transit.land/operators/o-dr5r-mtanyctransit")
    soup = BeautifulSoup(html, "html.parser")
    routes = []
    for tag in soup.find_all(["a", "li", "span"]):
        text = tag.get_text(strip=True)
        if len(text) <= 5 and any(c in text for c in "123456ABCDEFGJLMNQRSWZ"):
            if text not in [r["name"] for r in routes]:
                routes.append({"name": text, "type": "subway"})
    return routes


def main():
    print(f"=== Transit Scraper — {CITY} ===\n")

    transit_data = {}
    for key, query in NYC_TRANSIT_SEARCHES:
        print(f"Searching: {query[:60]}...")
        results = nimble_search(query)
        transit_data[key] = extract_snippets(results)

    scrape_mta_routes()

    nyc_subway_lines = [
        {"name": line, "type": "subway", "operator": "MTA NYC Transit"}
        for line in [
            "1","2","3","4","5","6","7",
            "A","C","E","B","D","F","M",
            "G","J","Z","L","N","Q","R","W",
            "S (42nd St)","S (Franklin Ave)","S (Rockaway)"
        ]
    ]

    nyc_bus_boroughs = [
        {"borough": "Manhattan", "operator": "MTA Bus / NYCT Bus", "major_routes": ["M1","M2","M3","M4","M5","M15","M101","M102","M103"]},
        {"borough": "Brooklyn",  "operator": "MTA Bus / NYCT Bus", "major_routes": ["B1","B2","B3","B6","B9","B35","B41","B44","B46"]},
        {"borough": "Queens",    "operator": "MTA Bus / NYCT Bus", "major_routes": ["Q1","Q2","Q3","Q4","Q10","Q44","Q46","Q58","Q60"]},
        {"borough": "Bronx",     "operator": "MTA Bus / NYCT Bus", "major_routes": ["Bx1","Bx2","Bx4","Bx5","Bx6","Bx9","Bx12","Bx15","Bx19"]},
        {"borough": "Staten Island", "operator": "MTA Bus / NYCT Bus", "major_routes": ["S40","S42","S44","S46","S48","S51","S53","S74","S76"]},
    ]

    nyc_major_hubs = [
        {"name": "Penn Station",          "type": "hub",    "lat": 40.7506, "lon": -73.9971, "lines": ["1","2","3","A","C","E"]},
        {"name": "Grand Central Terminal","type": "hub",    "lat": 40.7527, "lon": -73.9772, "lines": ["4","5","6","7","S"]},
        {"name": "Times Square",          "type": "hub",    "lat": 40.7580, "lon": -73.9855, "lines": ["1","2","3","7","N","Q","R","W","A","C","E","S"]},
        {"name": "Atlantic Terminal",     "type": "hub",    "lat": 40.6843, "lon": -73.9774, "lines": ["B","D","N","Q","R","2","3","4","5","G"]},
        {"name": "Jamaica Station",       "type": "hub",    "lat": 40.7022, "lon": -73.8017, "lines": ["E","J","Z","LIRR","AirTrain"]},
        {"name": "Fulton Center",         "type": "hub",    "lat": 40.7097, "lon": -74.0076, "lines": ["2","3","4","5","A","C","J","Z"]},
        {"name": "Union Square",          "type": "hub",    "lat": 40.7353, "lon": -73.9903, "lines": ["4","5","6","L","N","Q","R","W"]},
        {"name": "George Washington Bridge Bus Station", "type": "bus_terminal", "lat": 40.8520, "lon": -73.9397, "lines": ["bus"]},
        {"name": "Port Authority Bus Terminal", "type": "bus_terminal", "lat": 40.7572, "lon": -74.0021, "lines": ["bus"]},
    ]

    print(f"\nSubway lines:  {len(nyc_subway_lines)}")
    print(f"Bus boroughs:  {len(nyc_bus_boroughs)}")
    print(f"Major hubs:    {len(nyc_major_hubs)}")
    print(f"Search results categories: {len(transit_data)}")

    output = {
        "city": CITY,
        "source": "transitland.transit.land + MTA via Nimble Search",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "subway_lines": nyc_subway_lines,
        "bus_routes_by_borough": nyc_bus_boroughs,
        "major_hubs": nyc_major_hubs,
        "search_data": transit_data,
    }

    with open("transit_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to transit_results.json")
    return output


if __name__ == "__main__":
    main()
