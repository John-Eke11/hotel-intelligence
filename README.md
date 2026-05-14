# Hermes — Hotel Revenue Intelligence

AI-powered revenue management platform for independent hotels. Ask questions about your hotel's performance in plain English and get data-backed answers.

## What it does

| Feature | Description |
|---|---|
| **Dashboard** | Live KPI cards (Occupancy, ADR, RevPAR, TRevPAR), revenue breakdowns by channel and segment, actual vs budget trend, and an events calendar |
| **Chat** | Natural language interface — ask revenue questions and the AI translates them into SQL, runs them, and returns a summary with the underlying data |

## Architecture

```
React (frontend-react/)
    │  HTTP (fetch)
FastAPI (api/)
    ├── Static metrics endpoints  →  PostgreSQL (Supabase)
    └── /chat endpoint
            │
         llm/agent.py
            ├── generate_sql_or_answer()     →  Ollama (local LLM)
            ├── fetch_all()                  →  PostgreSQL
            ├── generate_fixed_sql()         →  Ollama (error recovery)
            └── generate_contextual_answer() →  Ollama
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running
- PostgreSQL database (local or [Supabase](https://supabase.com) free tier)

## Setup

### 1. Clone and install dependencies

```bash
# API dependencies
pip install -r api/requirements.txt

# Frontend dependencies
cd frontend-react && npm install
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
DATABASE_URL=postgresql://user:password@host:6543/postgres?sslmode=require
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
```

> **Supabase users:** Use the **Transaction mode** connection string (port `6543`), not the direct connection (port `5432`).

Configure the frontend API URL (optional — defaults to `http://localhost:8000`):

```bash
cp frontend-react/.env.example frontend-react/.env
```

```env
VITE_API_URL=http://localhost:8000
```

### 3. Set up the database

```bash
python db/run_all.py
```

To wipe and regenerate from scratch:

```bash
python db/run_all.py --reset
```

This creates 6 tables and generates ~16 months of synthetic data for a 100-room hotel in Lisbon (≈13,600 reservations).

### 4. Pull the LLM model

```bash
ollama pull qwen2.5-coder:14b
```

> This downloads ~9 GB. Requires at least 12 GB of available RAM. Ollama must stay running while the app is in use.

## Running the app

Start both servers in separate terminals:

```bash
# Terminal 1 — API (from project root)
uvicorn api.main:app --reload

# Terminal 2 — Frontend
cd frontend-react && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

The API runs on [http://localhost:8000](http://localhost:8000). You can explore the endpoints at [http://localhost:8000/docs](http://localhost:8000/docs).

## Project structure

```
ATLAS/
├── api/
│   ├── main.py              # FastAPI app — metrics endpoints + /chat
│   ├── models.py            # Pydantic request/response models
│   └── requirements.txt
├── frontend-react/
│   ├── src/
│   │   ├── api/             # Typed fetch client for the FastAPI backend
│   │   ├── components/      # UI primitives, layout, charts, chat components
│   │   ├── context/         # Shared app state (date range, chat history)
│   │   ├── hooks/           # Data-fetching hooks (useKPIs, useRevenue, useChat)
│   │   ├── pages/           # Home, Dashboard, Chat
│   │   ├── types/           # TypeScript interfaces matching API responses
│   │   └── utils/           # formatCurrency, formatPercent, formatDate, etc.
│   ├── .env.example
│   └── package.json
├── llm/
│   └── agent.py             # NL-to-SQL pipeline (Ollama integration)
├── db/
│   ├── run_all.py           # Orchestrates schema creation + data generation
│   ├── generate_reservations.py
│   ├── generate_events.py
│   ├── generate_event_bookings.py
│   ├── generate_competitor_rates.py
│   ├── generate_budget_targets.py
│   └── generate_property.py
├── .env.example
└── README.md
```

## Environment variables

### Backend (`.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | No | Ollama server URL (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | No | Model to use (default: `qwen2.5-coder:14b`) |

### Frontend (`frontend-react/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | No | FastAPI base URL (default: `http://localhost:8000`) |

## Database schema

| Table | Description |
|---|---|
| `property` | Hotel profile (name, total rooms, star rating) |
| `reservations` | Individual room bookings with revenue breakdown |
| `events` | External market events (Web Summit, Ironman Cascais, etc.) |
| `event_bookings` | Internal group/event bookings (conferences, weddings) |
| `budget_targets` | Monthly occupancy and revenue targets |
| `competitor_rates` | Nightly rates from 4 competitor hotels |

## Known limitations

- **Single property** — all queries are scoped to `property_id = 1`. Multi-property support requires schema and prompt changes.
- **Synthetic data only** — the database is seeded with generated data for Hotel Lisboa Central. It is not connected to a live PMS.
- **Local LLM required** — the AI component runs on Ollama. A machine with sufficient RAM (12 GB+) must be available. Cloud LLM support (Gemini, Groq) can be enabled by swapping `llm/agent.py`.
- **No authentication** — all API endpoints are open. Do not expose the API publicly without adding an auth layer.
- **Chat history is session-only** — conversation history is stored in React state and lost on refresh.
