"""
generate_events.py
Generates and inserts demand events into the events table.
These are external market events that drive hotel demand across the Lisbon/Estoril area.
Run after generate_property.py.

Data period: January 2024 - December 2026
"""

import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

# ── CONNECTION ──────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

# ── RECURRING EVENTS ─────────────────────────────────────────
# (base_name, event_type, historical_rate_uplift, [(start, end), ...])
# Year label is derived from the end date's year.

RECURRING_EVENTS = [
    ("New Year", "holiday", 0.55, [
        ("2024-01-01", "2024-01-02"),
        ("2024-12-30", "2025-01-02"),
        ("2025-12-30", "2026-01-02"),
        ("2026-12-30", "2027-01-02"),
    ]),
    ("Carnival", "festival", 0.20, [
        ("2024-02-10", "2024-02-13"),
        ("2025-03-01", "2025-03-04"),
        ("2026-02-14", "2026-02-17"),
    ]),
    ("Easter Weekend", "holiday", 0.45, [
        ("2024-03-29", "2024-04-01"),
        ("2025-04-18", "2025-04-21"),
        ("2026-04-03", "2026-04-06"),
    ]),
    ("Estoril Open Tennis", "sporting", 0.35, [
        ("2024-04-29", "2024-05-05"),
        ("2025-04-28", "2025-05-04"),
        ("2026-04-27", "2026-05-03"),
    ]),
    ("Festas de Lisboa - Santo Antonio", "festival", 0.30, [
        ("2024-06-12", "2024-06-13"),
        ("2025-06-12", "2025-06-13"),
        ("2026-06-12", "2026-06-13"),
    ]),
    ("Peak Summer", "festival", 0.40, [
        ("2024-07-15", "2024-08-31"),
        ("2025-07-15", "2025-08-31"),
        ("2026-07-15", "2026-08-31"),
    ]),
    ("Ironman Cascais", "sporting", 0.90, [
        ("2024-09-19", "2024-09-22"),
        ("2025-09-18", "2025-09-21"),
        ("2026-09-17", "2026-09-20"),
    ]),
    ("Web Summit", "congress", 1.20, [
        ("2024-11-11", "2024-11-14"),
        ("2025-11-10", "2025-11-13"),
        ("2026-11-09", "2026-11-12"),
    ]),
    ("Christmas Period", "holiday", 0.40, [
        ("2024-12-23", "2024-12-26"),
        ("2025-12-23", "2025-12-26"),
        ("2026-12-23", "2026-12-26"),
    ]),
]

# ── ONE-OFF EVENTS ───────────────────────────────────────────
# (event_name, event_type, historical_rate_uplift, start, end)

ONE_OFF_EVENTS = [
    ("Rock in Rio Lisboa 2024",               "festival", 0.60, "2024-06-15", "2024-06-22"),
    ("Estoril Congress Centre Event Q4 2024", "congress", 0.35, "2024-10-07", "2024-10-10"),
    ("Estoril Congress Centre Event Q3 2025", "congress", 0.35, "2025-09-29", "2025-10-02"),
]


def _build_events():
    events = []
    for base_name, etype, uplift, date_pairs in RECURRING_EVENTS:
        for start, end in date_pairs:
            year = end[:4]
            events.append({
                "event_name":             f"{base_name} {year}",
                "event_start_date":       start,
                "event_end_date":         end,
                "event_type":             etype,
                "historical_rate_uplift": uplift,
                "is_recurring":           True,
            })
    for name, etype, uplift, start, end in ONE_OFF_EVENTS:
        events.append({
            "event_name":             name,
            "event_start_date":       start,
            "event_end_date":         end,
            "event_type":             etype,
            "historical_rate_uplift": uplift,
            "is_recurring":           False,
        })
    return sorted(events, key=lambda e: e["event_start_date"])


EVENTS = _build_events()


# ── INSERT ───────────────────────────────────────────────────
def generate_events(conn):
    with conn.cursor() as cur:
        inserted = 0
        for event in EVENTS:
            cur.execute("""
                INSERT INTO events (
                    event_name, event_start_date, event_end_date,
                    event_type, historical_rate_uplift, is_recurring
                )
                VALUES (
                    %(event_name)s, %(event_start_date)s, %(event_end_date)s,
                    %(event_type)s, %(historical_rate_uplift)s, %(is_recurring)s
                )
                RETURNING event_id;
            """, event)
            event_id = cur.fetchone()[0]
            print(f"  Inserted event_id={event_id}: {event['event_name']}")
            inserted += 1
        conn.commit()
        print(f"\nDone. {inserted} events inserted.")


if __name__ == "__main__":
    conn = psycopg2.connect(DB_URL)
    try:
        generate_events(conn)
    finally:
        conn.close()