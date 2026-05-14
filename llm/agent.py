"""NL-to-SQL agent using a local Ollama model."""

import json
import os
import re
from datetime import date

import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")

_SCHEMA = """
Database: PostgreSQL — Hotel Lisboa Central (100-room 4-star hotel in Lisbon)
Data range: January 2024 – April 2026

Tables:

property (property_id, property_name, total_rooms, star_rating, city)

reservations (
    booking_id, property_id, guest_id, event_booking_id,
    booking_date, check_in_date, check_out_date,
    length_of_stay,           -- nights (= check_out_date - check_in_date)
    lead_time_days,           -- days between booking_date and check_in_date
    guest_country, guest_segment, booking_channel, room_type,
    commission_rate, rate_per_night, net_rate_per_night,
    total_room_revenue, fnb_revenue, spa_revenue, total_revenue,
    booking_status            -- 'confirmed' | 'checked_out' | 'cancelled' | 'no_show'
)
  guest_segment:   'leisure' | 'corporate' | 'group'
                   -- Use guest_segment to filter by guest type (e.g. corporate guests = guest_segment = 'corporate')
                   -- Do NOT use booking_channel to identify guest type — they are different concepts.
  booking_channel: 'direct' | 'booking_com' | 'expedia' | 'corporate_account' | 'travel_agent'
                   -- 'corporate_account' is a booking channel (how the booking was made), NOT the same as guest_segment = 'corporate'
  room_type:       'standard' | 'superior' | 'deluxe' | 'suite'
  booking_status rules:
    - 'checked_out' = stay already completed → use this for ALL historical occupancy and revenue queries
    - 'confirmed'   = future/upcoming booking → use only when asked about forward-looking data (e.g. "what's on the books")
    - 'cancelled' / 'no_show' = exclude from occupancy and revenue unless explicitly asked about cancellations

events (
    event_id, event_name, event_type, event_start_date, event_end_date,
    historical_rate_uplift,   -- decimal, e.g. 0.90 = 90% rate uplift
    is_recurring
)
  event_type: 'holiday' | 'festival' | 'sporting' | 'congress'
  Event names follow the pattern "<Base Name> <Year>" (e.g. "Ironman Cascais 2025").
  The year suffix is derived from event_end_date — NOT event_start_date.
  Holiday events (New Year, Christmas) span year boundaries: e.g. "New Year 2025" starts 2024-12-30 and ends 2025-01-02.
  Base names (use these keywords in ILIKE patterns):
    'Ironman Cascais'     -- NOTE: one word "Ironman", not "Iron Man"
    'Web Summit'
    'Rock in Rio Lisboa'
    'New Year', 'Easter Weekend', 'Christmas Period', 'Peak Summer'
    'Estoril Open Tennis', 'Festas de Lisboa - Santo Antonio', 'Carnival'
  Filtering rules:
    - If the event name already contains the year (e.g. "New Year 2025"), match on name alone — do NOT add a redundant year filter on event_start_date or event_end_date.
      Example: WHERE event_name ILIKE '%%New Year%%' AND event_name ILIKE '%%2025%%'
    - If only filtering by base name without a year, use EXTRACT(YEAR FROM event_end_date) for the year (NOT event_start_date).
      Example: WHERE event_name ILIKE '%%Ironman%%' AND EXTRACT(YEAR FROM event_end_date) = 2025
  IMPORTANT: When a user mentions "Iron Man", map it to "Ironman" in the ILIKE pattern.
  NOTE: this table tracks external market events; it is separate from event_bookings.
  NOTE: events has NO room_type, booking_channel, or revenue columns — those are in reservations only.
        To analyse reservations during events, JOIN reservations r ON r.check_in_date BETWEEN e.event_start_date AND e.event_end_date.

event_bookings (
    event_booking_id, property_id, booking_date,
    client_name, event_name,
    event_type,               -- 'meeting' | 'conference' | 'wedding' | 'dinner'
    num_rooms, group_rate_per_night, num_nights,
    associated_room_revenue,  -- = num_rooms * group_rate_per_night * num_nights
    space_revenue, catering_revenue, av_revenue,
    total_event_revenue       -- = space_revenue + catering_revenue + av_revenue
)
  NOTE: internal group/event business hosted at the property; not linked to the events table.

budget_targets (
    budget_id, property_id,
    month,                    -- DATE, always first of month
    target_occupancy, target_adr, target_fnb_revenue, target_spa_revenue
)

competitor_rates (
    rate_id, stay_date, hotel_name, hotel_star_rating, channel, room_type, rate_per_night
)
  Hotels: 'Hotel Lisboa Central' (us), 'Estoril Palace Suites', 'Hotel Cascais Bay',
          'Sintra Garden Hotel', 'Lisbon Metro Inn'
  channel: 'direct' | 'booking_com' | 'expedia'
"""

_KPI_FORMULAS = """\
Hospitality Key KPI formulas (always use these exact definitions):

  rooms_available  = p.total_rooms * days_in_period
  rooms_sold       = SUM(r.length_of_stay)
                     -- length_of_stay is enforced as check_out_date - check_in_date

  Occupancy        = rooms_sold / rooms_available
  ADR              = SUM(r.total_room_revenue) / rooms_sold
  RevPAR           = SUM(r.total_room_revenue) / rooms_available

  Net ADR          = SUM(r.net_rate_per_night * r.length_of_stay) / rooms_sold
                     -- net_rate_per_night = rate_per_night * (1 - commission_rate), enforced by constraint
                     -- there is no stored total_net_room_revenue column; always derive as above

  Net RevPAR       = SUM(r.net_rate_per_night * r.length_of_stay) / rooms_available
                     -- represents post-commission room revenue per available room
                     -- always pair with gross RevPAR for context

  TRevPAR          = (SUM(r.total_revenue) + event_bookings_revenue) / rooms_available
                     -- r.total_revenue = total_room_revenue + fnb_revenue + spa_revenue
                     -- This already includes room revenue from group bookings (via event_booking_id FK)
                     -- event_bookings_revenue = space + catering + AV only (NOT associated_room_revenue,
                     --   which is already captured in reservations.total_room_revenue)
                     -- event_bookings_revenue subquery:
                     --   SELECT COALESCE(SUM(total_event_revenue), 0)
                     --   FROM event_bookings
                     --   WHERE property_id = {property_id}
                     --   AND booking_date >= from_date AND booking_date < to_date

  Cancellation Rate = COUNT(*) FILTER (WHERE booking_status = 'cancelled')
                      / NULLIF(COUNT(*), 0)
                      -- denominator = all bookings including cancelled/no_show
                      -- filter on booking_date (when the booking was made) for the period,
                      --   NOT check_in_date, so: booking_date >= from_date AND booking_date < to_date
                      -- do NOT filter on booking_status before the COUNT — include all statuses

  No-Show Rate     = COUNT(*) FILTER (WHERE booking_status = 'no_show')
                      / NULLIF(COUNT(*), 0)
                      -- same denominator and date filter logic as Cancellation Rate above

  Computing days_in_period in PostgreSQL:
    -- Always use >= from_date AND < to_date (exclusive upper bound) for both filter and denominator
    days_in_period = to_date::date - from_date::date   -- e.g. Mar 1 to Apr 1 = 31 days
    -- For a full calendar month where bt.month is a DATE truncated to the 1st:
    days_in_period = (bt.month + INTERVAL '1 month')::date - bt.month::date

  Standard filter for RevPAR / ADR / occupancy / Net RevPAR queries:
    WHERE r.property_id = {property_id}
      AND r.booking_status = 'checked_out'
      AND r.check_in_date >= from_date
      AND r.check_in_date <  to_date

  IMPORTANT LIMITATION: filtering on check_in_date attributes all room-nights of a stay
  to the check-in date. A 4-night stay checking in Jan 30 is fully counted in January
  even though 3 nights fall in February. This is a known simplification — do not attempt
  to prorate stays across period boundaries unless explicitly asked.

  Revenue by channel/segment: SUM(total_revenue) GROUP BY booking_channel / guest_segment
  Monthly trend: DATE_TRUNC('month', check_in_date) GROUP BY month
  Budget variance: JOIN budget_targets on DATE_TRUNC('month', check_in_date) = bt.month
"""

_FEW_SHOT_EXAMPLES = """\
These are some example queries for illustration:

Q: What was our occupancy last month?
A:
SELECT
  MAX(p.total_rooms)                                                                        AS total_rooms,
  SUM(r.length_of_stay)                                                                     AS rooms_sold,
  MAX(p.total_rooms) * (DATE_TRUNC('month', CURRENT_DATE)::date
    - DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date)                        AS rooms_available,
  ROUND(SUM(r.length_of_stay)::numeric / NULLIF(
    MAX(p.total_rooms) * (DATE_TRUNC('month', CURRENT_DATE)::date
    - DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date), 0), 4)                AS occupancy
FROM reservations r
JOIN property p ON p.property_id = r.property_id
WHERE r.property_id = {property_id}
  AND r.booking_status = 'checked_out'
  AND r.check_in_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
  AND r.check_in_date <  DATE_TRUNC('month', CURRENT_DATE)::date;

Q: Which booking channel generated the most revenue this year?
A:
SELECT booking_channel,
       SUM(total_revenue)::float AS total_revenue
FROM reservations
WHERE property_id = {property_id}
  AND booking_status = 'checked_out'
  AND check_in_date >= DATE_TRUNC('year', CURRENT_DATE)::date
  AND check_in_date <  CURRENT_DATE
GROUP BY booking_channel
ORDER BY total_revenue DESC;

Q: What is the average length of stay for corporate guests?
A:
-- guest_segment = 'corporate' identifies corporate guests. Do NOT use booking_channel for this.
SELECT
  ROUND(AVG(length_of_stay)::numeric, 2) AS avg_length_of_stay
FROM reservations
WHERE property_id = {property_id}
  AND booking_status = 'checked_out'
  AND guest_segment = 'corporate';

Q: How was our channel performance last month compared to the same time last year?
A:
-- Column is booking_channel (NOT channel). Use CTEs for YoY comparison.
WITH last_month AS (
  SELECT
    booking_channel,
    SUM(total_revenue)::numeric  AS revenue,
    COUNT(*)                     AS bookings
  FROM reservations
  WHERE property_id = {property_id}
    AND booking_status = 'checked_out'
    AND check_in_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
    AND check_in_date <  DATE_TRUNC('month', CURRENT_DATE)::date
  GROUP BY booking_channel
),
same_month_last_year AS (
  SELECT
    booking_channel,
    SUM(total_revenue)::numeric  AS revenue,
    COUNT(*)                     AS bookings
  FROM reservations
  WHERE property_id = {property_id}
    AND booking_status = 'checked_out'
    AND check_in_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '13 months')::date
    AND check_in_date <  DATE_TRUNC('month', CURRENT_DATE - INTERVAL '12 months')::date
  GROUP BY booking_channel
)
SELECT
  COALESCE(lm.booking_channel, ly.booking_channel)  AS booking_channel,
  COALESCE(lm.revenue, 0)                            AS revenue_last_month,
  COALESCE(ly.revenue, 0)                            AS revenue_same_month_ly,
  COALESCE(lm.revenue, 0) - COALESCE(ly.revenue, 0) AS variance,
  ROUND(
    (COALESCE(lm.revenue, 0) - COALESCE(ly.revenue, 0)) /
    NULLIF(COALESCE(ly.revenue, 0), 0) * 100, 1
  )                                                  AS pct_change
FROM last_month lm
FULL OUTER JOIN same_month_last_year ly USING (booking_channel)
ORDER BY revenue_last_month DESC;


Q: How did we price against competitors during Ironman Cascais 2025?
A:
-- Compares property avg rate vs competitor avg rate by stay date and room type
-- during the Ironman Cascais 2025 event window.
-- Property rates: checked_out reservations with check_in_date in event window (exclusive end).
-- Competitor rates: all competitors averaged by stay_date and room_type (inclusive end).
-- FULL OUTER JOIN preserves dates/room types missing on either side.
-- index_vs_comp > 1.0 = priced above comp set; < 1.0 = priced below; NULL = no comp data.
WITH event_window AS (
  SELECT
    event_name,
    event_start_date,
    event_end_date
  FROM events
  WHERE event_name ILIKE '%%Ironman%%'
    AND event_name ILIKE '%%2025%%'
),
property_rates AS (
  SELECT
    r.check_in_date                      AS stay_date,
    r.room_type,
    ROUND(AVG(r.rate_per_night), 2)      AS property_avg_rate,
    COUNT(*)                             AS bookings
  FROM reservations r
  JOIN event_window e
    ON r.check_in_date >= e.event_start_date
    AND r.check_in_date < e.event_end_date
  WHERE r.property_id = {property_id}
    AND r.booking_status = 'checked_out'
  GROUP BY r.check_in_date, r.room_type
),
comp_rates AS (
  SELECT
    cr.stay_date,
    cr.room_type,
    ROUND(AVG(cr.rate_per_night), 2)     AS comp_avg_rate,
    COUNT(DISTINCT cr.hotel_name)        AS num_competitors
  FROM competitor_rates cr
  JOIN event_window e
    ON cr.stay_date BETWEEN e.event_start_date AND e.event_end_date
  GROUP BY cr.stay_date, cr.room_type
)
SELECT
  COALESCE(pr.stay_date, cr.stay_date)           AS stay_date,
  COALESCE(pr.room_type, cr.room_type)           AS room_type,
  pr.property_avg_rate,
  cr.comp_avg_rate,
  cr.num_competitors,
  pr.bookings,
  ROUND(
    pr.property_avg_rate / NULLIF(cr.comp_avg_rate, 0), 4
  )                                              AS index_vs_comp,
  (SELECT event_name FROM event_window LIMIT 1)  AS matched_event
FROM property_rates pr
FULL OUTER JOIN comp_rates cr
  ON pr.stay_date = cr.stay_date
  AND pr.room_type = cr.room_type
ORDER BY stay_date, room_type;
"""

_SQL_SYSTEM = """\
You are an expert PostgreSQL analyst for a hotel revenue management system. /no_think
Today's date is {today}. IMPORTANT: Always use this exact date — never rely on your training data for the current date, month, or year.
Convert the user's question into a single valid SQL statement.
Ensure you write the SQL queries using the database schema defined here {schema}

{kpi_formulas}

{few_shot_examples}

Rules:
- Always filter reservations by property_id = {property_id} unless the question is about competitors.
- When joining multiple tables, always qualify property_id with its table alias (e.g. r.property_id = {property_id}, never bare property_id = {property_id}).
- When filtering by event name, use the exact stored spelling: "Ironman" is one word (not "Iron Man"). Map user input to the correct spelling in the ILIKE pattern.
- Use EXACT column names from the schema — never abbreviate or guess:
    guest_segment (NOT guest_type / NOT segment)
    booking_channel (NOT channel — 'channel' only exists in competitor_rates)
    room_type, booking_status, check_in_date, total_room_revenue
- Use consistent table aliases — never reuse the same alias for two different tables or CTEs:
    r=reservations, p=property, e=events, eb=event_bookings, bt=budget_targets, cr=competitor_rates
    CTEs must use descriptive names (e.g. last_month, comp_data) never the same as a table alias.
- For historical occupancy and revenue queries, filter booking_status = 'checked_out' only.
- Only include 'confirmed' status when the question is explicitly about future, upcoming, or on-books bookings (e.g. pace).
- Never include 'cancelled' or 'no_show' in occupancy or revenue queries unless cancellations or no-shows are specifically asked about.
- For cancellation rate and no-show rate queries: use booking_date (not check_in_date) as the period filter, and COUNT all booking statuses in the denominator before applying FILTER.
- Default period filter is check_in_date. Use booking_date only for: cancellation rate, no-show rate, and pace/pickup queries.
- Always use NULLIF to avoid division by zero in KPI calculations.
- Always cast revenue aggregates to ::numeric (not ::float) — PostgreSQL's ROUND(value, n) requires numeric, not double precision.
- Always write MAX(p.total_rooms) when using property.total_rooms alongside aggregate functions — never use bare p.total_rooms in an aggregate query. Only reference p.total_rooms in queries that JOIN the property table.
- For KPIs requiring multiple steps (pace, ARI, budget variance, TRevPAR), always use CTEs. Never inline subqueries.
- Every query must be a single, self-contained SQL statement. All CTEs must be defined with WITH in the same statement — never reference a CTE name that is not defined in the current query's WITH clause. There are no persistent views or helper tables such as event_window in the database.
- Output ONLY the raw SQL — no explanation, no markdown, no code fences.
- Add LIMIT 50 to row-level queries; aggregates do not need a limit.
"""

_SUMMARY_SYSTEM = """\
You are a hotel revenue analyst assistant. /no_think Today's date is {today}. IMPORTANT: Always use this exact date — never rely on your training data for the current date, month, or year.
Given a user's question and query results, write a clear answer analyzing the data and the implications.
Be specific: include key numbers, percentages, or rankings from the data.
Do not repeat raw data row-by-row. Do not mention SQL.
"""


def _call_ollama(messages: list[dict]) -> str:
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    return _strip_thinking(resp.json()["message"]["content"]).strip()


_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "run_sql_query",
        "description": "Run a SELECT query against the hotel database to answer a data question.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A valid PostgreSQL SELECT or WITH ... SELECT query.",
                }
            },
            "required": ["query"],
        },
    },
}


def _extract_json_object(text: str) -> dict | None:
    """Find and parse the first complete JSON object in text, ignoring trailing content."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (json.JSONDecodeError, ValueError):
                    return None
    return None


def _strip_thinking(text: str) -> str:
    """Remove thinking blocks emitted by various models."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    return text.strip()


def _normalize_sql(sql: str) -> str:
    """Replace unicode operators that models sometimes emit with ASCII equivalents."""
    return sql.replace("≥", ">=").replace("≤", "<=").replace("≠", "!=").replace("–", "-")


def _strip_fences(sql: str) -> str:
    """Remove markdown code fences if the model adds them despite instructions."""
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.splitlines()
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        sql = "\n".join(inner).strip()
    return sql


def _extract_sql(text: str) -> str | None:
    """Extract a SQL query from text that may contain explanations."""
    text = text.strip()

    # Already clean SQL
    upper = text.upper()
    if upper.startswith("SELECT"):
        return text
    # Only treat leading WITH as SQL if it matches the CTE pattern
    if re.match(r"WITH\s+\w+\s+AS\s*\(", text, re.IGNORECASE):
        return text

    # Markdown code fence: ```sql ... ``` or ``` ... ```
    fence = re.search(r"```(?:sql)?\s*\n([\s\S]+?)\n```", text, re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        upper_c = candidate.upper()
        if upper_c.startswith("SELECT") or re.match(r"WITH\s+\w+\s+AS\s*\(", candidate, re.IGNORECASE):
            return candidate

    # WITH CTE — check before SELECT so we don't extract a SELECT that's
    # inside a CTE body and miss the leading WITH <name> AS ( prefix.
    cte_start = re.search(r"\bWITH\s+\w+\s+AS\s*\(", text, re.IGNORECASE)
    if cte_start:
        candidate = text[cte_start.start():]
        last_semi = candidate.rfind(";")
        if last_semi != -1:
            return candidate[: last_semi + 1].strip()
        return candidate.strip()

    # SELECT embedded in explanation text
    sql_start = re.search(r"\bSELECT\b", text, re.IGNORECASE)
    if sql_start:
        candidate = text[sql_start.start():]
        last_semi = candidate.rfind(";")
        if last_semi != -1:
            return candidate[: last_semi + 1].strip()
        return candidate.strip()

    return None


def generate_fixed_sql(history: list[dict], failed_sql: str, error: str, property_id: int = 1) -> str:
    """Re-prompt the model with the failed SQL and the database error to get a corrected query."""
    system = _SQL_SYSTEM.format(
        schema=_SCHEMA,
        kpi_formulas=_KPI_FORMULAS.format(property_id=property_id),
        few_shot_examples=_FEW_SHOT_EXAMPLES.format(property_id=property_id),
        property_id=property_id,
        today=date.today().isoformat(),
    )
    fix_prompt = (
        f"The SQL query below failed with this database error:\n\n"
        f"Error: {error}\n\n"
        f"Failed SQL:\n{failed_sql}\n\n"
        f"Fix the SQL so it runs without errors. Output ONLY the corrected SQL — no explanation."
    )
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": fix_prompt},
    ]
    sql = _call_ollama(messages)
    return _strip_fences(_extract_sql(sql) or sql)


def generate_sql_from_text(user_query: str, property_id: int = 1) -> str:
    system = _SQL_SYSTEM.format(
        schema=_SCHEMA,
        kpi_formulas=_KPI_FORMULAS.format(property_id=property_id),
        few_shot_examples=_FEW_SHOT_EXAMPLES.format(property_id=property_id),
        property_id=property_id,
        today=date.today().isoformat(),
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_query},
    ]
    sql = _call_ollama(messages)
    return _strip_fences(sql)


def generate_natural_answer(user_query: str, results: list[dict]) -> str:
    if not results:
        return "No data was found for that query."

    sample = results[:25]
    results_json = json.dumps(sample, indent=2, default=str)

    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM.format(today=date.today().isoformat())},
        {
            "role": "user",
            "content": (
                f"Question: {user_query}\n\n"
                f"Query results ({len(results)} rows, showing first {len(sample)}):\n"
                f"{results_json}"
            ),
        },
    ]
    return _call_ollama(messages)


# ── Conversation-aware functions ──────────────────────────────────────────────

_ROUTER_SYSTEM = """\
You are a hotel revenue intelligence assistant for Hotel Lisboa Central. Today's date is {today}. IMPORTANT: Always use this exact date — never rely on your training data for the current date, month, or year.
You have access to a PostgreSQL database and deep hospitality industry knowledge.

════ WHEN TO CALL run_sql_query ════
Call run_sql_query when the question requires data from the database:
  - Specific numbers, metrics, or trends from this hotel's data
  - Actual performance (occupancy, revenue, ADR, bookings, etc.)
  - Fresh data not already shown in the conversation

════ WHEN TO RESPOND DIRECTLY ════
Respond with plain text — do NOT call run_sql_query — when:
  - The question asks for a definition or explanation (e.g. "what is RevPAR?", "explain ADR")
  - The question asks for opinion, recommendation, or analysis of data already in the conversation
  - The question is about industry benchmarks or general hospitality knowledge
  - The question is about the current date, month, or year — use the date already provided above, NEVER query the database for date or time information

Example of a direct answer (no tool call):
  Q: What month and year is it?
  A: Today is {today}. The current month is {month} and the year is {year}.

════ DATABASE SCHEMA & SQL RULES ════

{schema}

{kpi_formulas}

{few_shot_examples}

SQL rules:
- Always filter reservations by property_id = {property_id} unless the question is about competitors.
- When joining multiple tables, always qualify property_id with its table alias (e.g. r.property_id = {property_id}, never bare property_id = {property_id}).
- When filtering by event name, use the exact stored spelling: "Ironman" is one word (not "Iron Man"). Map user input to the correct spelling in the ILIKE pattern.
- Use EXACT column names from the schema — never abbreviate or guess:
    guest_segment (NOT guest_type / NOT segment)
    booking_channel (NOT channel — 'channel' only exists in competitor_rates)
    room_type, booking_status, check_in_date, total_room_revenue
- Use consistent table aliases — never reuse the same alias for two different tables or CTEs:
    r=reservations, p=property, e=events, eb=event_bookings, bt=budget_targets, cr=competitor_rates
    CTEs must use descriptive names (e.g. last_month, comp_data) never the same as a table alias.
- For historical occupancy and revenue queries, filter booking_status = 'checked_out' only.
- Only include 'confirmed' when the question is explicitly about future or upcoming bookings.
- Never include 'cancelled' or 'no_show' unless specifically asked.
- Always use MAX(p.total_rooms) when using property.total_rooms alongside aggregate functions.
- Always use NULLIF to avoid division by zero in KPI calculations.
- Always cast revenue aggregates to ::numeric (not ::float) — PostgreSQL's ROUND(value, n) requires numeric, not double precision.
- For multi-step KPIs use CTEs, not inline subqueries.
- Every query must be a single, self-contained SQL statement. All CTEs must be defined with WITH in the same statement — never reference a CTE name that is not defined in the current query's WITH clause. There are no persistent views or helper tables such as event_window in the database.
- Every column referenced in a JOIN condition must be explicitly selected in the CTE — never reference a column in ON/WHERE that was not included in the CTE's SELECT list.
- CTEs that are joined by stay_date or check_in_date MUST include that date column in their SELECT. CTEs that are CROSS JOINed (single aggregate row) must NOT include date columns.
- Add LIMIT 50 to row-level queries; aggregates do not need a limit.

"""

_CONTEXTUAL_SUMMARY_SYSTEM = """\
You are a hotel revenue intelligence assistant for Hotel Lisboa Central. /no_think Today's date is {today}. IMPORTANT: Always use this exact date — never rely on your training data for the current date, month, or year.
Given a user's question and the database results that answered it, write a thorough analysis as an experienced revenue manager would.
- Output ONLY natural language text. Never generate SQL queries.
- Lead with the direct answer to the question (key number, trend, or finding).
- ONLY IF an analysis is explicitly asked, provide an analysis of the results: what does this mean for the business? Is it good or bad? What might be driving it?
- Your response should be easy to scan with a clear recommendation and not overwhelm the user with too much text unless requested.
- Humanize your analysis using natural language so it's easy to understand.
- Reference earlier conversation context when relevant (comparisons, trends, follow-ups).
- Do not repeat raw data row-by-row. Do not mention SQL.
"""


def generate_sql_or_answer(messages: list[dict], property_id: int = 1) -> tuple[str, bool]:
    """
    Returns (content, is_sql):
      is_sql=True  → content is a SQL query from the run_sql_query tool call
      is_sql=False → content is a direct text answer
    """
    today = date.today()
    system = _ROUTER_SYSTEM.format(
        schema=_SCHEMA,
        kpi_formulas=_KPI_FORMULAS.format(property_id=property_id),
        few_shot_examples=_FEW_SHOT_EXAMPLES.format(property_id=property_id),
        property_id=property_id,
        today=today.isoformat(),
        month=today.strftime("%B"),
        year=today.year,
    )

    trimmed = messages[-6:] if len(messages) > 6 else messages
    full_messages = [{"role": "system", "content": system}] + trimmed

    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": full_messages,
            "tools": [_SQL_TOOL],
            "stream": False,
        },
        timeout=180,
    )
    resp.raise_for_status()
    message = resp.json()["message"]

    for call in message.get("tool_calls") or []:
        if call["function"]["name"] == "run_sql_query":
            args = call["function"]["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            sql = args.get("query", "") if isinstance(args, dict) else ""
            if sql:
                return sql, True

    content = _strip_thinking(message.get("content", "")).strip()

    # Some models output the tool call as JSON text in content instead of
    # using the tool API (e.g. {"name": "run_sql_query", "arguments": {...}}).
    # Use brace-matching to extract the JSON object, ignoring any trailing text.
    if content:
        parsed = _extract_json_object(content)
        if isinstance(parsed, dict) and parsed.get("name") == "run_sql_query":
            sql = parsed.get("arguments", {}).get("query", "")
            if sql:
                return _normalize_sql(sql), True

    # Model returned nothing — retry without tools and extract SQL from plain text.
    if not content:
        resp2 = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": full_messages, "stream": False},
            timeout=180,
        )
        resp2.raise_for_status()
        content = _strip_thinking(resp2.json()["message"].get("content", "")).strip()
        sql = _extract_sql(content)
        if sql:
            return _normalize_sql(sql), True

    return content, False


def generate_contextual_answer(messages: list[dict], results: list[dict]) -> str:
    """Generate a natural language answer from query results."""
    if not results:
        return "No data was found for that query."

    sample = results[:25]
    results_json = json.dumps(sample, indent=2, default=str)

    last_question = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"),
        ""
    )

    full_messages = [
        {"role": "system", "content": _CONTEXTUAL_SUMMARY_SYSTEM.format(today=date.today().isoformat())},
        {
            "role": "user",
            "content": (
                f"Question: {last_question}\n\n"
                f"Query results ({len(results)} rows, showing first {len(sample)}):\n"
                f"{results_json}\n\n"
            ),
        },
    ]
    return _call_ollama(full_messages)