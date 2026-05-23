# SeniorGuide AI

A proactive AI agent for seniors that finds the right home and acts as a daily companion.

---

## The Problem

Over 55 million seniors in the US face two hard challenges alone:

1. **Housing decisions** — navigating property taxes, neighborhood safety, proximity to healthcare and transit is overwhelming without help
2. **Daily coordination** — missing doctor appointments, not knowing when the bus comes, losing track of local events

SeniorGuide AI solves both.

---

## What It Does

### Home Finder Module

The senior fills out a simple profile:
- Monthly budget and income
- Age and health needs
- Lifestyle priorities (public transit, walkability, proximity to hospitals)
- Financial goals (minimize taxes, build equity)

The agent searches real listings and scores neighborhoods based on:
- Property tax burden relative to income
- Distance to hospitals and clinics
- Bus and subway route frequency and coverage
- Nearby grocery stores, pharmacies, shopping centers

**Output:** A ranked, plain-language report the senior can actually understand.

> *"This area saves you $3,200/year in taxes and has a bus to your doctor's office every 15 minutes."*

---

### Daily Companion Module

The agent acts as a proactive personal assistant:

- **Doctor reminders** — "Your cardiologist appointment is tomorrow at 2pm"
- **Real-time transit alerts** — "Bus 42 arrives in 5 minutes — leave now"
- **Event notifications** — "Free senior yoga at the community center this Thursday"
- **Voice access** — available through Google Assistant so no app is needed

---

## Sponsor Tool Integration

| Tool | Role |
|------|------|
| **Nimble** | Scrapes real estate listings, property tax records, transit schedules, and hospital locations in real time |
| **ClickHouse** | Stores senior profiles, neighborhood scores, event logs, and AI agent traces — fast queries for matching and analytics |
| **Senso.ai** | Generates cited, plain-language neighborhood reports and personalized daily briefings grounded in real data |
| **Datadog** | Monitors every agent action — logs reminders sent, traces API calls, alerts on failures, surfaces real-time telemetry |

---

## Architecture & Data Flow

```
Senior's Profile Input
        │
        ▼
Nimble ──► Scrapes real-time data:
           • Real estate listings
           • Property tax records
           • Transit schedules (bus/subway)
           • Hospital & clinic locations
           • Nearby amenities
        │
        ▼
ClickHouse ──► Stores & scores:
               • Neighborhood datasets
               • Senior profile matches
               • Historical event logs
               • AI agent traces
        │
        ▼
Senso.ai ──► Generates:
             • Cited neighborhood summary reports
             • Personalized daily briefings
             • Accessibility assessments
        │
        ▼
Google Assistant ──► Delivers to senior via:
                     • Voice responses
                     • Proactive spoken alerts
                     • SMS fallback
        │
        ▼
Datadog ──► Observes everything:
            • Logs each reminder and alert sent
            • Traces every Nimble and transit API call
            • Metrics on agent response latency
            • Alerts if agent fails to notify
```

---

## ClickHouse Schema (Core Tables)

```sql
-- Senior profiles
CREATE TABLE seniors (
    senior_id     UUID,
    age           UInt8,
    monthly_income Float32,
    max_tax_budget Float32,
    needs_transit  Boolean,
    needs_hospital_proximity Boolean,
    created_at    DateTime
) ENGINE = MergeTree() ORDER BY senior_id;

-- Neighborhood scores
CREATE TABLE neighborhoods (
    neighborhood_id UUID,
    city            String,
    state           String,
    avg_property_tax Float32,
    hospital_dist_km Float32,
    transit_score   Float32,
    grocery_dist_km Float32,
    overall_score   Float32,
    scraped_at      DateTime
) ENGINE = MergeTree() ORDER BY (city, state, scraped_at);

-- Agent event log
CREATE TABLE agent_events (
    event_id    UUID,
    senior_id   UUID,
    event_type  String,   -- 'reminder', 'transit_alert', 'notification'
    payload     String,
    status      String,   -- 'sent', 'failed', 'pending'
    created_at  DateTime
) ENGINE = MergeTree() ORDER BY (senior_id, created_at);
```

---

## Datadog Observability

Every agent action is instrumented:

- **Logs** — each reminder sent, each scrape completed, each alert triggered
- **Traces** — full distributed trace from user request → Nimble scrape → ClickHouse query → Senso.ai generation → delivery
- **Metrics** — agent response latency, notification delivery rate, scrape success rate
- **Monitors** — alert if a scheduled reminder fails to send within its window

The Datadog dashboard showing live agent telemetry is a strong demo asset.

---

## Why This Works at a Hackathon

- **All 4 sponsor tools are load-bearing** — each one has a clear, non-replaceable role
- **Compelling live demo** — a senior asks via voice: *"Find me a neighborhood near a hospital, under $2,000/month in taxes"* and gets a cited, spoken answer in seconds
- **Real problem, real users** — housing and daily coordination are two of the biggest pain points for the 55M+ senior population in the US
- **Visible observability** — the Datadog dashboard showing real-time traces and metrics looks impressive during a presentation

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Agent logic | Python + Anthropic Claude API |
| Web scraping | Nimble Web Search & Scraping API |
| Data storage | ClickHouse |
| Content generation | Senso.ai |
| Voice interface | Google Assistant Actions |
| Monitoring | Datadog (logs, APM, metrics) |

---

## MVP Scope (Hackathon)

1. Senior onboarding form (budget, health needs, transit preferences)
2. Nimble scrapes one city's real estate + transit + hospital data
3. ClickHouse stores and scores neighborhoods
4. Senso.ai generates a cited summary report
5. One live demo reminder delivered via Google Assistant
6. Datadog dashboard showing agent traces live
