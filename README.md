# SeniorGuide AI — Aura Housing Concierge

An AI-powered housing assistant that helps seniors find the right rental in New York City based on their budget, lifestyle, transit needs, and preferred borough.

---

## What It Does

Users fill out a 4-step wizard. The app queries real NYC rental data from ClickHouse, scores every listing against the user's profile, and uses Groq AI to write a personalized concierge report.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Web scraping | Nimble API |
| Database | ClickHouse Cloud |
| AI report | Groq (`llama-3.3-70b-versatile`) |
| Backend | Flask (Python) |
| Frontend | Vanilla JS + CSS |

---

## Data in ClickHouse

| Table | Source | Records |
|---|---|---|
| `listings` | Zillow via Nimble | 45 NYC rentals |
| `hospitals` | CMS Medicare Open Data | 191 NY hospitals |
| `transit_hubs` | NYC transit reference data | 9 major hubs |
| `property_taxes` | SmartAsset via Nimble | 9 NY counties |

---

## How It Works

1. **Scrape** — four Python scripts collect data from Zillow, CMS, and SmartAsset using the Nimble API
2. **Load** — `clickhouse_loader.py` creates tables and inserts all records into ClickHouse Cloud
3. **Query** — on each user request, Flask queries ClickHouse for listings within budget and borough
4. **Score** — a weighted engine ranks listings: budget 30%, borough 25%, lifestyle 25%, transit 20%
5. **Report** — the AI agent reads the top matches and generates a personalized concierge report

---

## AI Agent

The AI agent runs inside `frontend/main.py` every time a user submits the wizard. It does the following:

1. **Receives the user profile** — budget, borough preference, transit need, and lifestyle priority
2. **Fetches ranked listings** — the scoring engine has already queried ClickHouse and sorted the best matches for this user
3. **Builds a prompt** — the top 5 listings are formatted with address, price, beds, baths, sqft, and match score, then combined with the user's full profile into a single prompt
4. **Calls Groq** — the prompt is sent to `llama-3.3-70b-versatile` via the Groq API
5. **Returns a markdown report** — Groq writes a warm, senior-friendly housing report that explains why the top listing was chosen, highlights neighborhood character, mentions transit access if needed, and ends with an encouraging note
6. **Fallback** — if Groq is unavailable, a built-in template generates a basic report automatically so the app never breaks

The agent does **not** use tool-calling or multi-step loops — it receives pre-fetched, pre-scored data and focuses entirely on turning that data into a clear, human explanation.

---

## Wizard Steps

1. Monthly budget
2. Public transit need
3. Lifestyle priority (space / parks / nightlife / quiet)
4. Preferred borough

---

## Project Structure

```
datadog_hackathon/
├── zillow_scraper.py        # Scrapes Zillow rentals via Nimble
├── hospital_scraper.py      # Pulls NY hospitals from CMS API via Nimble
├── transit_scraper.py       # NYC transit hub data
├── property_tax_scraper.py  # NY county tax rates via Nimble
├── clickhouse_loader.py     # Loads all JSON results into ClickHouse
├── frontend/
│   ├── main.py              # Flask app — scoring engine + Groq AI agent
│   └── static/
│       ├── index.html       # Aura wizard UI
│       ├── app.js           # Wizard logic + dashboard rendering
│       └── style.css        # Styles
└── .env                     # API keys (not committed)
```

---

## Setup

**1. Install dependencies**
```bash
pip install flask clickhouse-connect groq beautifulsoup4 requests python-dotenv
```

**2. Configure `.env`**
```
NIMBLE_API_KEY=...
CLICKHOUSE_HOST=https://<your-instance>.clickhouse.cloud:8443
CLICKHOUSE_PASSWORD=...
GROQ_API_KEY=...
```

**3. Scrape and load data** (one-time)
```bash
python3 zillow_scraper.py
python3 hospital_scraper.py
python3 transit_scraper.py
python3 property_tax_scraper.py
python3 clickhouse_loader.py
```

**4. Run the app**
```bash
cd frontend
python3 main.py
```

Open **http://127.0.0.1:8000**

---

## Sponsors Used

- **Nimble** — web scraping with rotating proxies
- **ClickHouse** — analytics database storing all NYC housing data
- **Groq** — fast LLM inference for the AI concierge report
- **Datadog** — observability and monitoring
