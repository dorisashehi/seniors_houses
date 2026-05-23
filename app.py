import json
import os

import anthropic
import clickhouse_connect
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ── ClickHouse client ────────────────────────────────────────────────────────

_raw = os.getenv("CLICKHOUSE_HOST", "").replace("https://", "").replace("http://", "")
_host, _, _port_s = _raw.partition(":")
CH = clickhouse_connect.get_client(
    host=_host,
    port=int(_port_s or 8443),
    username="default",
    password=os.getenv("CLICKHOUSE_PASSWORD"),
    secure=True,
)

# ── Anthropic client ─────────────────────────────────────────────────────────

AI = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

# ── FastAPI ──────────────────────────────────────────────────────────────────

app = FastAPI()


class UserProfile(BaseModel):
    max_budget: int
    min_beds: int
    need_hospital: bool
    need_transit: bool
    borough: str = ""


# ── Agent tools ──────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_listings",
        "description": "Search rental listings from ClickHouse filtered by budget and bedrooms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_budget": {"type": "integer", "description": "Max rent per month in USD"},
                "min_beds": {"type": "integer", "description": "Minimum number of bedrooms (0 = studio)"},
                "borough": {"type": "string", "description": "NYC borough filter (optional), e.g. Brooklyn, Queens"},
            },
            "required": ["max_budget", "min_beds"],
        },
    },
    {
        "name": "get_hospitals",
        "description": "Get top-rated hospitals in New York with emergency services.",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_rating": {"type": "integer", "description": "Minimum star rating (1-5)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_transit_hubs",
        "description": "Get major transit hubs and subway/bus connections in New York.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_property_taxes",
        "description": "Get property tax rates by county in New York.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def search_listings(max_budget: int, min_beds: int, borough: str = "") -> list:
    where = f"price_per_month <= {max_budget}"
    if min_beds > 0:
        where += f" AND beds >= {min_beds}"
    if borough:
        where += f" AND address ILIKE '%{borough}%'"
    rows = CH.query(
        f"SELECT address, price_per_month, beds, baths, sqft, link "
        f"FROM listings WHERE {where} ORDER BY price_per_month ASC LIMIT 10"
    ).result_rows
    return [
        {"address": r[0], "price": r[1], "beds": r[2], "baths": r[3], "sqft": r[4], "link": r[5]}
        for r in rows
    ]


def get_hospitals(min_rating: int = 4) -> list:
    rows = CH.query(
        f"SELECT name, city, overall_rating, emergency_services, address "
        f"FROM hospitals WHERE overall_rating >= {min_rating} AND emergency_services = 1 "
        f"ORDER BY overall_rating DESC LIMIT 10"
    ).result_rows
    return [
        {"name": r[0], "city": r[1], "rating": r[2], "emergency": bool(r[3]), "address": r[4]}
        for r in rows
    ]


def get_transit_hubs() -> list:
    rows = CH.query(
        "SELECT name, type, lat, lon, lines FROM transit_hubs ORDER BY name ASC"
    ).result_rows
    return [
        {"name": r[0], "type": r[1], "lat": r[2], "lon": r[3], "lines": r[4]}
        for r in rows
    ]


def get_property_taxes() -> list:
    rows = CH.query(
        "SELECT county, tax_rate_pct FROM property_taxes ORDER BY tax_rate_pct ASC"
    ).result_rows
    return [{"county": r[0], "tax_rate_pct": r[1]} for r in rows]


def run_tool(name: str, inputs: dict):
    if name == "search_listings":
        return search_listings(**inputs)
    if name == "get_hospitals":
        return get_hospitals(**inputs)
    if name == "get_transit_hubs":
        return get_transit_hubs()
    if name == "get_property_taxes":
        return get_property_taxes()
    return {}


# ── Agent loop ───────────────────────────────────────────────────────────────

def run_agent(profile: UserProfile) -> str:
    system = (
        "You are SeniorGuide AI, a compassionate assistant helping seniors find the "
        "perfect home in New York. Use the available tools to search real listings, "
        "hospitals, and transit data. Then give a clear, friendly recommendation with "
        "3-5 top listings that best match the senior's needs. Include price, address, "
        "nearby hospitals if needed, and transit access. Keep the tone warm and simple."
    )

    user_msg = (
        f"I'm looking for a home in New York. Here's what I need:\n"
        f"- Monthly budget: ${profile.max_budget}\n"
        f"- Bedrooms needed: {profile.min_beds if profile.min_beds > 0 else 'Studio or any'}\n"
        f"- Must be near a hospital: {'Yes' if profile.need_hospital else 'No'}\n"
        f"- Need good public transit: {'Yes' if profile.need_transit else 'No'}\n"
        f"- Preferred borough: {profile.borough if profile.borough else 'No preference'}\n\n"
        "Please find me the best options."
    )

    messages = [{"role": "user", "content": user_msg}]

    while True:
        response = AI.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "No recommendation generated."

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
            messages.append({"role": "user", "content": tool_results})


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()


@app.post("/api/recommend")
def recommend(profile: UserProfile):
    result = run_agent(profile)
    return JSONResponse({"recommendation": result})
