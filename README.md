# Hotel Intelligence

Revenue management intelligence platform for independent hotels.

## Project Structure

```
hotel-intelligence/
├── db/          # Schema and data generators (PostgreSQL / Supabase)
├── api/         # FastAPI backend
├── frontend/    # React or Streamlit UI
├── llm/         # NL-to-SQL pipeline and fine-tuning scripts
├── .env         # Local credentials (never committed)
└── .env.example # Credential template
```

## Setup

1. Copy `.env.example` to `.env` and fill in your database URL:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install psycopg2-binary numpy python-dotenv
   ```

3. Run the schema against your database, then generate data:
   ```bash
   python db/run_all.py
   # To reset and regenerate from scratch:
   python db/run_all.py --reset
   ```