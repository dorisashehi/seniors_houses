import os
import json
import requests
from flask import Flask, render_template, request, jsonify, session
from anthropic import Anthropic

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "nyc-housing-concierge-secret-2024")

anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
NIMBLE_API_KEY = os.environ.get("NIMBLE_API_KEY", "")

QUESTIONS = [
    {
        "id": "budget",
        "question": "What's your monthly rent budget?",
        "subtitle": "We'll find options that fit your finances",
        "type": "slider",
        "min": 500,
        "max": 2000,
        "default": 1200,
        "unit": "$",
        "icon": "💰"
    },
    {
        "id": "transit",
        "question": "Do you need easy access to public transportation?",
        "subtitle": "Subway, bus, or commuter rail nearby",
        "type": "choice",
        "options": ["Yes, essential", "Nice to have", "Not a priority"],
        "icon": "🚇"
    },
    {
        "id": "priority",
        "question": "What matters most to you in your neighborhood?",
        "subtitle": "Pick your top priority",
        "type": "choice",
        "options": ["Space & size", "Short commute", "Parks & nature", "Nightlife & dining", "Peace & quiet"],
        "icon": "🏙️"
    },
    {
        "id": "pets",
        "question": "Do you have pets that need a pet-friendly home?",
        "subtitle": "We'll filter for buildings that welcome your furry family",
        "type": "choice",
        "options": ["Yes, dogs", "Yes, cats", "Yes, both", "No pets"],
        "icon": "🐾"
    },
    {
        "id": "elevator",
        "question": "Walk-up okay, or do you need an elevator?",
        "subtitle": "Some great deals are in walk-up buildings",
        "type": "choice",
        "options": ["Walk-up is fine", "Elevator preferred", "Elevator required"],
        "icon": "🛗"
    },
    {
        "id": "borough",
        "question": "Which borough are you drawn to?",
        "subtitle": "Or let us surprise you with the best match",
        "type": "choice",
        "options": ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Open to all"],
        "icon": "🗽"
    },
    {
        "id": "workplace",
        "question": "Where do you work or volunteer?",
        "subtitle": "We'll factor in your commute so every day is easier",
        "type": "text",
        "placeholder": "e.g. Midtown Manhattan, Downtown Brooklyn, Remote...",
        "icon": "💼"
    }
]


def scrape_listings_nimble(query_params: dict) -> dict:
    """Use Nimbleway Extract API to scrape housing listings."""
    budget = query_params.get("budget", 1500)
    borough = query_params.get("borough", "Open to all").lower().replace(" ", "-")
    
    search_url = f"https://streeteasy.com/for-rent/nyc/price:{budget}?sort_by=listed_desc"
    
    if borough != "open-to-all":
        borough_map = {
            "manhattan": "manhattan",
            "brooklyn": "brooklyn", 
            "queens": "queens",
            "the-bronx": "bronx"
        }
        area = borough_map.get(borough, "nyc")
        search_url = f"https://streeteasy.com/for-rent/{area}/price:{budget}?sort_by=listed_desc"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {NIMBLE_API_KEY}"
    }
    
    payload = {
        "url": search_url,
        "render": True,
        "country": "US",
        "state": "NY",
        "city": "new_york",
        "locale": "en-US",
        "formats": ["markdown"],
        "driver": "vx8",
        "render_options": {
            "render_type": "idle2",
            "timeout": 30000
        }
    }
    
    try:
        response = requests.post(
            "https://sdk.nimbleway.com/v1/extract",
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned {response.status_code}", "raw": response.text}
    except Exception as e:
        return {"error": str(e)}


def get_ai_recommendations(user_prefs: dict, scraped_data: dict = None) -> str:
    """Use Claude to generate personalized housing recommendations."""
    
    scraped_context = ""
    if scraped_data and "data" in scraped_data:
        markdown = scraped_data.get("data", {}).get("markdown", "")
        if markdown:
            scraped_context = f"\n\nHere is live listing data scraped from StreetEasy:\n{markdown[:3000]}"
    
    prompt = f"""You are a warm, knowledgeable NYC housing concierge helping someone find their perfect home.

User's preferences:
- Monthly budget: up to ${user_prefs.get('budget', 1500)}
- Public transit access: {user_prefs.get('transit', 'Not specified')}
- Top neighborhood priority: {user_prefs.get('priority', 'Not specified')}
- Pets: {user_prefs.get('pets', 'Not specified')}
- Building type: {user_prefs.get('elevator', 'Not specified')}
- Preferred borough: {user_prefs.get('borough', 'Open to all')}
- Workplace/commute from: {user_prefs.get('workplace', 'Not specified')}
{scraped_context}

Based on their profile, provide:
1. **Your Top 3 Neighborhood Picks** — specific NYC neighborhoods that fit their needs, with a brief, enthusiastic explanation of why each is a great match (commute, vibe, price range, transit)
2. **Insider Tips** — 2-3 practical tips for finding housing in NYC at their budget (timing, what to look for, red flags)
3. **Your Housing Roadmap** — a simple 3-step action plan to get them into a home within 30-60 days

Keep the tone warm, encouraging, and specific to NYC. Use emojis sparingly. Format with clear headers."""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"


@app.route("/")
def index():
    session.clear()
    return render_template("index.html", questions=QUESTIONS, total=len(QUESTIONS))


@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.json
    user_prefs = data.get("answers", {})
    
    session["user_prefs"] = user_prefs
    
    # Scrape listings via Nimble
    scraped = None
    if NIMBLE_API_KEY:
        scraped = scrape_listings_nimble(user_prefs)
    
    # Get AI recommendations
    recommendations = get_ai_recommendations(user_prefs, scraped)
    
    return jsonify({
        "success": True,
        "recommendations": recommendations,
        "scraped_url": scraped.get("url") if scraped else None
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """Follow-up chat with the AI concierge."""
    data = request.json
    message = data.get("message", "")
    history = data.get("history", [])
    user_prefs = session.get("user_prefs", {})
    
    system_prompt = f"""You are a warm, expert NYC housing concierge. The user has already told you their preferences:
- Budget: up to ${user_prefs.get('budget', 1500)}/month
- Transit needs: {user_prefs.get('transit', 'Not specified')}
- Priority: {user_prefs.get('priority', 'Not specified')}
- Pets: {user_prefs.get('pets', 'Not specified')}
- Building preference: {user_prefs.get('elevator', 'Not specified')}
- Borough: {user_prefs.get('borough', 'Open to all')}
- Workplace: {user_prefs.get('workplace', 'Not specified')}

Answer their follow-up questions helpfully, drawing on deep NYC housing knowledge. Be specific, practical, and encouraging."""

    messages = history + [{"role": "user", "content": message}]
    
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            system=system_prompt,
            messages=messages
        )
        return jsonify({"reply": response.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
