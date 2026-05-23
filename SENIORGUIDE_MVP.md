# SeniorGuide AI — Minimal Version

A single-flow AI agent: senior describes their needs, agent finds the best neighborhood and sends one daily reminder.

---

## What It Does (MVP Only)

1. Senior fills a simple form: city, budget, income, needs (hospital/transit/shopping)
2. Agent scrapes real data for that city
3. Agent returns a plain-language neighborhood recommendation
4. Agent sends one proactive daily reminder (doctor appointment or bus alert)

That's it. No voice. No full dashboard. One city. One user flow.

---

## Sponsor Tools (Minimal Use)

| Tool           | MVP Role                                                                  |
| -------------- | ------------------------------------------------------------------------- |
| **Nimble**     | Scrape one city's real estate listings + nearby hospitals + transit stops |
| **ClickHouse** | Store the senior's profile and scraped neighborhood data                  |
| **Senso.ai**   | Generate the cited neighborhood recommendation summary                    |
| **Datadog**    | Log each agent step and trace the full request                            |

---

## Flow

```
User input (form)
      │
      ▼
Nimble scrapes city data
      │
      ▼
ClickHouse stores + scores neighborhoods
      │
      ▼
Senso.ai writes the recommendation
      │
      ▼
Agent returns result + schedules one daily reminder
      │
      ▼
Datadog logs and traces every step
```

---

## ClickHouse Tables (2 only)

```sql
CREATE TABLE seniors (
    senior_id      UUID,
    city           String,
    monthly_budget Float32,
    needs_transit  Boolean,
    needs_hospital Boolean,
    created_at     DateTime
) ENGINE = MergeTree() ORDER BY senior_id;

CREATE TABLE neighborhoods (
    name             String,
    city             String,
    avg_property_tax Float32,
    hospital_nearby  Boolean,
    transit_score    Float32,
    overall_score    Float32,
    scraped_at       DateTime
) ENGINE = MergeTree() ORDER BY (city, scraped_at);
```

---

## File Structure

```
seniorguide/
├── main.py              # entry point, runs the agent flow
├── scraper.py           # Nimble API calls
├── database.py          # ClickHouse read/write
├── recommender.py       # Senso.ai report generation
├── reminder.py          # schedules one daily alert
└── observability.py     # Datadog logging and tracing
```

---

## Demo Script (Hackathon)

1. Show the input form: city = "Chicago", budget = $1,500/month, needs hospital nearby
2. Agent scrapes and scores neighborhoods live
3. Senso.ai returns: _"Lincoln Square ranks highest — avg tax $1,340/mo, 0.4 km to Swedish Hospital, 3 bus lines"_
4. Agent schedules: _"Reminder: Doctor appointment tomorrow at 10am"_
5. Datadog dashboard shows the full trace of the request

---

## Out of Scope for MVP

- Voice / Google Assistant integration
- Multiple cities
- Multi-user support
- Event notifications
- SMS delivery

Get data first → store in ClickHouse → build agents on top

Agents need something to reason over. If ClickHouse is empty, the agent has nothing to query and falls back to hallucinating neighborhood details.

Separates concerns cleanly. Scraping is slow and rate-limited. If the agent triggers scraping on every request, your demo will be slow and fragile. Pre-loading data makes the agent fast and reliable.

Easier to debug. You can inspect the raw data in ClickHouse before the agent touches it and catch bad scrape results early.

Better demo story. You show the Nimble scrape as a data pipeline step, ClickHouse as the analytics layer, and the agent as the intelligence layer on top — each sponsor tool has a distinct visible role.

Suggested order:

Run scraper.py → collect hospitals, transit, shopping, housing for one city
Load results into ClickHouse
Build the agent with tools that query ClickHouse
Add Senso.ai for report generation
Add Datadog tracing around everything

Here are the best free public websites to scrape with Nimble for each data category:

Hospitals

medicare.gov/care-compare — official US hospital directory, fully public, no login
healthgrades.com — hospital ratings and locations
Public Transit

transitland.transit.land — open transit data for hundreds of cities (bus/subway routes, stops)
For Chicago specifically: transitchicago.com — CTA bus/train routes and stops, all public
Shopping (Grocery, Pharmacy)

openstreetmap.org — completely free, has every grocery store, pharmacy, mall mapped worldwide — best option
yelp.com — searchable by category and city, no login needed to view results
Housing / Rentals

craigslist.org — free listings, no login, very scrapable with Nimble
apartments.com — public listings, no login required
zillow.com — public listings with price and neighborhood info
Property Taxes

smartasset.com/taxes/property-taxes — has property tax rates by city/county
Chicago specifically: cookcountyassessor.com — fully public
Recommended combo for the MVP:

Category Source
Hospitals medicare.gov/care-compare
Transit transitchicago.com
Shopping openstreetmap.org
Housing craigslist.org
Property tax smartasset.com
All public, no API key needed — Nimble handles the scraping. Want me to update scraper.py to target these specific URLs?
