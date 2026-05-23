import json
import os
from datetime import datetime

from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()

_raw_host = os.getenv("CLICKHOUSE_HOST", "")
_raw_host = _raw_host.replace("https://", "").replace("http://", "")
_host, _, _port_str = _raw_host.partition(":")
_port = int(_port_str) if _port_str else 8443

CLIENT = clickhouse_connect.get_client(
    host=_host,
    port=_port,
    username=os.getenv("CLICKHOUSE_USER", "default"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
    secure=True,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def load_json(filename):
    with open(filename, encoding="utf-8") as f:
        return json.load(f)


def create_tables():
    CLIENT.command("""
        CREATE TABLE IF NOT EXISTS listings (
            address        String,
            price_per_month Nullable(Int32),
            beds           Nullable(Int8),
            baths          Nullable(Int8),
            sqft           Nullable(Int32),
            link           String,
            city           String,
            scraped_at     DateTime
        ) ENGINE = MergeTree()
        ORDER BY (city, address)
    """)

    CLIENT.command("""
        CREATE TABLE IF NOT EXISTS property_taxes (
            county         String,
            tax_rate_pct   Nullable(Float32),
            median_home_value Nullable(Int32),
            median_annual_tax Nullable(Int32),
            source         String,
            state          String,
            scraped_at     DateTime
        ) ENGINE = MergeTree()
        ORDER BY (state, county)
    """)

    CLIENT.command("""
        CREATE TABLE IF NOT EXISTS transit_hubs (
            name           String,
            type           String,
            lat            Nullable(Float64),
            lon            Nullable(Float64),
            lines          String,
            city           String,
            scraped_at     DateTime
        ) ENGINE = MergeTree()
        ORDER BY (city, name)
    """)

    CLIENT.command("""
        CREATE TABLE IF NOT EXISTS hospitals (
            facility_id    String,
            name           String,
            address        String,
            city           String,
            state          String,
            zip_code       String,
            county         String,
            phone          String,
            hospital_type  String,
            ownership      String,
            emergency_services UInt8,
            overall_rating Nullable(Int8),
            scraped_at     DateTime
        ) ENGINE = MergeTree()
        ORDER BY (state, city, facility_id)
    """)

    print("Tables created.")


# ── loaders ──────────────────────────────────────────────────────────────────

def load_listings():
    data = load_json("zillow_results.json")
    scraped_at = datetime.fromisoformat(data["scraped_at"])
    city = data["city"]

    rows = [
        [
            l["address"],
            l.get("price_per_month"),
            l.get("beds"),
            l.get("baths"),
            l.get("sqft"),
            l.get("link", ""),
            city,
            scraped_at,
        ]
        for l in data["listings"]
    ]

    CLIENT.insert(
        "listings",
        rows,
        column_names=["address", "price_per_month", "beds", "baths", "sqft", "link", "city", "scraped_at"],
    )
    print(f"  Inserted {len(rows)} listings.")


def load_property_taxes():
    data = load_json("property_tax_results.json")
    scraped_at = datetime.fromisoformat(data["scraped_at"])
    state = data["state"]

    rows = [
        [
            t["county"],
            t.get("tax_rate_pct"),
            t.get("median_home_value"),
            t.get("median_annual_tax"),
            t.get("source", ""),
            state,
            scraped_at,
        ]
        for t in data["property_taxes"]
    ]

    CLIENT.insert(
        "property_taxes",
        rows,
        column_names=["county", "tax_rate_pct", "median_home_value", "median_annual_tax", "source", "state", "scraped_at"],
    )
    print(f"  Inserted {len(rows)} property tax records.")


def load_transit():
    data = load_json("transit_results.json")
    scraped_at = datetime.fromisoformat(data["scraped_at"])
    city = data["city"]

    rows = [
        [
            h["name"],
            h.get("type", "hub"),
            h.get("lat"),
            h.get("lon"),
            json.dumps(h.get("lines", [])),
            city,
            scraped_at,
        ]
        for h in data["major_hubs"]
    ]

    CLIENT.insert(
        "transit_hubs",
        rows,
        column_names=["name", "type", "lat", "lon", "lines", "city", "scraped_at"],
    )
    print(f"  Inserted {len(rows)} transit hubs.")


def load_hospitals():
    data = load_json("hospital_results.json")
    scraped_at = datetime.fromisoformat(data["scraped_at"])

    rows = [
        [
            h.get("facility_id", ""),
            h.get("name", ""),
            h.get("address", ""),
            h.get("city", ""),
            h.get("state", ""),
            h.get("zip_code", ""),
            h.get("county", ""),
            h.get("phone", ""),
            h.get("hospital_type", ""),
            h.get("ownership", ""),
            1 if h.get("emergency_services") else 0,
            h.get("overall_rating"),
            scraped_at,
        ]
        for h in data["hospitals"]
    ]

    CLIENT.insert(
        "hospitals",
        rows,
        column_names=[
            "facility_id", "name", "address", "city", "state", "zip_code",
            "county", "phone", "hospital_type", "ownership",
            "emergency_services", "overall_rating", "scraped_at",
        ],
    )
    print(f"  Inserted {len(rows)} hospitals.")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== ClickHouse Loader ===\n")

    print("Creating tables...")
    create_tables()

    print("\nLoading data...")
    load_listings()
    load_property_taxes()
    load_transit()
    load_hospitals()

    print("\nVerifying row counts:")
    for table in ["listings", "property_taxes", "transit_hubs", "hospitals"]:
        result = CLIENT.query(f"SELECT count() FROM {table}")
        count = result.result_rows[0][0]
        print(f"  {table}: {count} rows")

    print("\nDone. All data loaded into ClickHouse.")


if __name__ == "__main__":
    main()
