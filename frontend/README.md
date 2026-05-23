# HomeKey NYC — AI Housing Concierge

A personal AI housing concierge that helps anyone navigate NYC's complex housing market. Users answer 7 questions about their lifestyle and budget, then receive AI-powered neighborhood recommendations, insider tips, and a 30-60 day action plan.

## Architecture

```
User → Flask Web UI → Anthropic Claude API (recommendations)
                    → Nimbleway Extract API (live StreetEasy listings)
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export NIMBLE_API_KEY="your-nimbleway-api-key"
export FLASK_SECRET_KEY="your-random-secret"   # optional, has default
```

### 3. Run
```bash
python app.py
```

Then open http://localhost:5000

---

## How It Works

### User Questionnaire (7 questions)
1. **Budget** — Slider up to $2,000/month
2. **Transit** — Public transportation importance
3. **Priority** — Space / commute / parks / nightlife / quiet
4. **Pets** — Pet-friendly building requirements
5. **Building type** — Walk-up vs elevator
6. **Borough** — Manhattan, Brooklyn, Queens, Bronx, or all
7. **Workplace** — For commute calculation

### Backend Flow

**Step 1 — Nimbleway Extract API**  
Constructs a StreetEasy search URL based on budget + borough, then calls the Nimbleway `/v1/extract` endpoint with:
- `render: true` (JavaScript-heavy page)
- `driver: vx8`
- `formats: ["markdown"]` (clean structured output)
- `render_options.render_type: "idle2"` (waits for full load)

**Step 2 — Claude AI Recommendations**  
Passes user preferences + scraped listing data to Claude Sonnet, which generates:
- Top 3 neighborhood picks with reasoning
- Insider NYC housing tips
- 30-60 day action roadmap

**Step 3 — Interactive Chat**  
Users can ask follow-up questions; Claude maintains context of their full preference profile.

---

## API Reference

### POST /api/submit
Accepts user answers, triggers Nimble scrape + AI recommendations.

**Request:**
```json
{
  "answers": {
    "budget": 1500,
    "transit": "Yes, essential",
    "priority": "Short commute",
    "pets": "No pets",
    "elevator": "Walk-up is fine",
    "borough": "Brooklyn",
    "workplace": "Midtown Manhattan"
  }
}
```

**Response:**
```json
{
  "success": true,
  "recommendations": "## Your Top 3 Neighborhoods...",
  "scraped_url": "https://streeteasy.com/..."
}
```

### POST /api/chat
Follow-up questions to the concierge.

**Request:**
```json
{
  "message": "What's the commute from Astoria to Midtown?",
  "history": []
}
```

**Response:**
```json
{
  "reply": "From Astoria, Queens..."
}
```

---

## Nimbleway Integration

The app uses the Nimbleway Extract API (`POST https://sdk.nimbleway.com/v1/extract`) to scrape live rental listings from StreetEasy. Authentication is via Bearer token in the Authorization header.

The scraped markdown is passed as context to Claude for grounded, real-time recommendations.
