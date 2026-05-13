"""
FastAPI backend for Hotel Revenue Intelligence.

Endpoints
---------
GET  /health
GET  /metrics/kpis                 occupancy, ADR, RevPAR, TRevPAR + period deltas
GET  /metrics/revenue-by-channel   revenue breakdown by booking channel
GET  /metrics/revenue-by-segment   revenue breakdown by guest segment
GET  /metrics/monthly-trend        actual vs budget revenue per month
GET  /events                       external demand drivers in a date range
POST /chat                         NL query → SQL → tabular results (LLM mocked)
POST /api/query                    legacy NL endpoint with LRU cache (LLM mocked)
"""

import json
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), "audit.log"))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(file_handler)

from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import sqlglot
from sqlglot import exp

from models import ChatRequest, ChatResponse, QueryRequest, QueryResponse

from llm.agent import (
    generate_sql_from_text,
    generate_natural_answer,
    generate_sql_or_answer,
    generate_contextual_answer,
)

load_dotenv()

app = FastAPI(title="Hotel Revenue Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db_connection():
    """Establishes a connection to the PostgreSQL database using DATABASE_URL."""
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def fetch_all(sql: str, params: tuple) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # L3 Output Validation: Enforce DB-level read-only role (Slide 96)
            cur.execute("SET TRANSACTION READ ONLY;")
            
            # psycopg2 treats % as a parameter placeholder — escape any literal
            # % in LLM-generated SQL (e.g. ILIKE '%value%') when no params are used.
            if not params:
                sql = sql.replace("%", "%%")
            
            audit_logger.info(f"EXECUTED SQL: {sql} | PARAMS: {params}")
            
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple) -> Optional[dict]:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None

def validate_sql_for_tenant(sql: str, expected_property_id: int):
    """
    L3 Output Validation & L2 Authorization (per Slide 96 & 108).
    Parses the AST to prevent stacked queries and destructive commands,
    and enforces cross-tenant data isolation.
    """
    try:
        statements = sqlglot.parse(sql, read="postgres")
        if not statements or len(statements) != 1:
            raise ValueError("Security block: Exactly one SQL statement is allowed.")
        
        ast = statements[0]
        if not isinstance(ast, exp.Select):
            raise ValueError("Security block: Only SELECT queries are permitted.")
            
        # Prevent data-modifying operations inside CTEs or main query
        for node in ast.find_all((exp.Delete, exp.Update, exp.Insert, exp.Drop, exp.Alter, exp.Command)):
            raise ValueError("Security block: Data modifying operations are strictly prohibited.")
            
        # L2 Authorization: Enforce cross-tenant isolation
        # Ensure the query explicitly filters for the authorized property_id
        if str(expected_property_id) not in sql:
            raise ValueError("Security block: Cross-tenant data isolation violation. Missing property_id filter.")
            
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"Security block: SQL syntax invalid or unparseable: {e}")



# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── KPI metrics ───────────────────────────────────────────────────────────────

def _kpis_for_period(from_d: date, to_d: date, property_id: int) -> dict:
    """
    Compute occupancy, ADR, RevPAR, TRevPAR for a given date range.

    Basis: reservations with check_in_date within [from_d, to_d].
    TRevPAR includes event_bookings revenue (booked within the same window).
    """
    days = max((to_d - from_d).days, 1)

    stay_sql = """
        SELECT
            p.total_rooms,
            COALESCE(SUM(r.length_of_stay), 0)::float AS nights_sold,
            COALESCE(SUM(r.total_room_revenue),   0)::float AS room_revenue,
            COALESCE(SUM(r.total_revenue),  0)::float AS stay_revenue
        FROM property p
        LEFT JOIN reservations r
               ON r.property_id = p.property_id
              AND r.check_in_date BETWEEN %s AND %s
              AND r.booking_status NOT IN ('cancelled', 'no_show')
        WHERE p.property_id = %s
        GROUP BY p.total_rooms
    """
    row = fetch_one(stay_sql, (from_d, to_d, property_id))
    if not row:
        return {}

    event_sql = """
        SELECT COALESCE(SUM(total_event_revenue), 0)::float AS event_revenue
        FROM event_bookings
        WHERE property_id = %s AND booking_date BETWEEN %s AND %s
    """
    event_row = fetch_one(event_sql, (property_id, from_d, to_d))
    event_rev = event_row["event_revenue"] if event_row else 0.0

    available   = row["total_rooms"] * days
    nights_sold = row["nights_sold"]
    room_rev    = row["room_revenue"]
    total_rev   = row["stay_revenue"] + event_rev

    return {
        "occupancy": nights_sold / available if available else 0.0,
        "adr":       room_rev / nights_sold  if nights_sold else 0.0,
        "revpar":    room_rev / available    if available else 0.0,
        "trevpar":   total_rev / available   if available else 0.0,
    }


@app.get("/metrics/kpis")
def get_kpis(
    from_date:   date = Query(...),
    to_date:     date = Query(...),
    property_id: int  = Query(default=1),
):
    current = _kpis_for_period(from_date, to_date, property_id)
    if not current:
        raise HTTPException(status_code=404, detail="Property not found.")

    # Previous period of equal length for delta calculation
    duration  = to_date - from_date
    prev_to   = from_date - timedelta(days=1)
    prev_from = prev_to - duration
    previous  = _kpis_for_period(prev_from, prev_to, property_id)

    result: dict = {}
    for metric in ("occupancy", "adr", "revpar", "trevpar"):
        result[metric] = current[metric]
        result[f"{metric}_delta"] = (
            current[metric] - previous[metric] if previous else None
        )
    return result


# ── Revenue by channel ────────────────────────────────────────────────────────

@app.get("/metrics/revenue-by-channel")
def get_revenue_by_channel(
    from_date:   date = Query(...),
    to_date:     date = Query(...),
    property_id: int  = Query(default=1),
):
    sql = """
        SELECT booking_channel AS channel,
               SUM(total_revenue)::float AS total_revenue
        FROM reservations
        WHERE property_id = %s
          AND check_in_date BETWEEN %s AND %s
          AND booking_status NOT IN ('cancelled', 'no_show')
        GROUP BY booking_channel
        ORDER BY total_revenue DESC
    """
    return fetch_all(sql, (property_id, from_date, to_date))


# ── Revenue by segment ────────────────────────────────────────────────────────

@app.get("/metrics/revenue-by-segment")
def get_revenue_by_segment(
    from_date:   date = Query(...),
    to_date:     date = Query(...),
    property_id: int  = Query(default=1),
):
    sql = """
        SELECT guest_segment AS segment,
               SUM(total_revenue)::float AS total_revenue
        FROM reservations
        WHERE property_id = %s
          AND check_in_date BETWEEN %s AND %s
          AND booking_status NOT IN ('cancelled', 'no_show')
        GROUP BY guest_segment
        ORDER BY total_revenue DESC
    """
    return fetch_all(sql, (property_id, from_date, to_date))


# ── Monthly revenue vs budget ─────────────────────────────────────────────────

@app.get("/metrics/monthly-trend")
def get_monthly_trend(
    from_date:   date = Query(...),
    to_date:     date = Query(...),
    property_id: int  = Query(default=1),
):
    """
    Returns monthly actual revenue vs computed budget target.

    Budget target = target_occupancy * total_rooms * days_in_month * target_adr
                  + target_fnb_revenue + target_spa_revenue
    """
    sql = """
        WITH actuals AS (
            SELECT
                DATE_TRUNC('month', check_in_date)::date AS month,
                SUM(total_revenue)::float                AS actual_revenue
            FROM reservations
            WHERE property_id = %s
              AND check_in_date BETWEEN %s AND %s
              AND booking_status NOT IN ('cancelled', 'no_show')
            GROUP BY DATE_TRUNC('month', check_in_date)::date
        ),
        targets AS (
            SELECT
                bt.month,
                (bt.target_occupancy
                 * p.total_rooms
                 * ((bt.month + INTERVAL '1 month')::date - bt.month)
                 * bt.target_adr
                 + bt.target_fnb_revenue
                 + bt.target_spa_revenue
                )::float AS target_revenue
            FROM budget_targets bt
            JOIN property p ON p.property_id = bt.property_id
            WHERE bt.property_id = %s
        )
        SELECT
            TO_CHAR(a.month, 'YYYY-MM-DD') AS month,
            a.actual_revenue,
            t.target_revenue
        FROM actuals a
        LEFT JOIN targets t ON t.month = a.month
        ORDER BY a.month
    """
    return fetch_all(sql, (property_id, from_date, to_date, property_id))


# ── Events calendar ───────────────────────────────────────────────────────────

@app.get("/events")
def get_events(
    from_date: date = Query(...),
    to_date:   date = Query(...),
):
    sql = """
        SELECT
            event_name,
            event_type,
            TO_CHAR(event_start_date, 'YYYY-MM-DD') AS event_start_date,
            TO_CHAR(event_end_date,   'YYYY-MM-DD') AS event_end_date,
            historical_rate_uplift,
            is_recurring
        FROM events
        WHERE event_start_date <= %s
          AND event_end_date   >= %s
        ORDER BY event_start_date
    """
    return fetch_all(sql, (to_date, from_date))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_history(raw_messages: list) -> list[dict]:
    """Convert frontend chat history to Ollama-compatible {role, content} strings."""
    result = []
    for msg in raw_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, dict):
            text = content.get("summary", "")
            data = content.get("data")
            if data and data.get("rows"):
                n = len(data["rows"])
                cols = data.get("columns", [])
                sample = [dict(zip(cols, r)) for r in data["rows"][:5]]
                text += (
                    f"\n[Query returned {n} rows. "
                    f"Sample: {json.dumps(sample, default=str)}]"
                )
        else:
            text = str(content)
        result.append({"role": role, "content": text})
    return result


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        history = _serialize_history(request.messages)
        history.append({"role": "user", "content": request.query})

        content, is_sql = generate_sql_or_answer(history, request.property_id)

        if not is_sql:
            return ChatResponse(summary=content, sql=None, data=None)

        # L3 Output Validation & L2 Authorization
        validate_sql_for_tenant(content, request.property_id)

        rows_raw = fetch_all(content, ())
        columns  = list(rows_raw[0].keys()) if rows_raw else []
        rows     = [[row[c] for c in columns] for row in rows_raw]
        summary  = generate_contextual_answer(history, rows_raw)

        return ChatResponse(
            summary=summary,
            sql=content,
            data={"columns": columns, "rows": rows},
        )
    except Exception as e:
        return ChatResponse(
            summary=f"Sorry, I couldn't process that query: {e}",
            sql=None,
            data=None,
        )


# ── Legacy NL query endpoint (kept from API branch) ───────────────────────────

# Apply a cache to remember the last 100 unique queries.
# This saves LLM compute and database round-trips once the LLM is wired.
@lru_cache(maxsize=100)
def process_and_cache_query(user_prompt: str, property_id: int):
    sql_query = generate_sql_from_text(user_prompt, property_id)

    # L3 Output Validation & L2 Authorization
    validate_sql_for_tenant(sql_query, property_id)

    raw_results = fetch_all(sql_query, ())
    final_answer = generate_natural_answer(user_prompt, raw_results)

    return final_answer, sql_query


@app.post("/api/query", response_model=QueryResponse)
def process_revenue_query(request: QueryRequest):
    """Legacy endpoint: process a natural language query and return SQL + answer."""
    try:
        final_answer, sql_query = process_and_cache_query(
            request.user_prompt,
            request.property_id,
        )
        return QueryResponse(answer=final_answer, generated_sql=sql_query)
    except Exception as e:
        return QueryResponse(
            answer="An error occurred while processing the request.",
            error=str(e),
        )
