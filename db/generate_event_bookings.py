"""
generate_event_bookings.py
Generates group event bookings hosted at the hotel.
These are corporate conferences, weddings, meetings, and dinners — 
internal revenue events completely independent from the external events table.

Data period: January 2024 - April 2026 (16 months)
Volume: ~2-3 events per month = ~40 total events

Revenue logic (based on Kaggle hotel dataset and industry benchmarks):
- Meetings:     small (10-30 pax), 1 night, low room block, moderate F&B
- Conferences:  medium-large (30-150 pax), 2-3 nights, larger room block, high F&B + AV
- Weddings:     medium (50-120 pax), 1-2 nights, moderate room block, high catering
- Dinners:      small-medium (20-80 pax), 0 room block, moderate catering, no AV

Room blocks:
- Group rates are 10-20% below BAR (standard negotiated discount)
- Conferences tend to book during shoulder/low season (corporate calendar)
- Weddings peak in spring and autumn
- Meetings distributed evenly year-round
"""

import os
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from datetime import date, timedelta
import random
from dotenv import load_dotenv, find_dotenv

# ── CONNECTION ───────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

np.random.seed(99)
random.seed(99)

PROPERTY_ID = 1

# ── CLIENT NAMES ─────────────────────────────────────────────
CORPORATE_CLIENTS = [
    "Deloitte Portugal", "EDP Renewables", "Galp Energia",
    "Millenium BCP", "Novo Banco", "NOS Comunicacoes",
    "Vodafone Portugal", "Siemens Portugal", "Jerónimo Martins",
    "Sonae Group", "TAP Air Portugal", "Fidelidade Seguros",
    "BPI Bank", "Lusitania Insurance", "CTT Correios",
    "Meo Altice", "Santander Portugal", "KPMG Portugal",
    "PwC Portugal", "Accenture Lisboa",
]

WEDDING_CLIENTS = [
    "Silva & Ferreira Wedding", "Costa & Rodrigues Wedding",
    "Pereira & Santos Wedding", "Martins & Oliveira Wedding",
    "Sousa & Carvalho Wedding", "Fernandes & Lopes Wedding",
    "Gomes & Alves Wedding", "Ribeiro & Mendes Wedding",
]

# ── SEASONAL BASE RATES ──────────────────────────────────────
# Group rate = BAR rate * group_discount
# BAR rates mirror seasonal_base from competitor_rates generator
SEASONAL_BAR = {
    (2024,  1): 110, (2024,  2): 112, (2024,  3): 125,
    (2024,  4): 138, (2024,  5): 150, (2024,  6): 158,
    (2024,  7): 172, (2024,  8): 176, (2024,  9): 153,
    (2024, 10): 133, (2024, 11): 142, (2024, 12): 118,
    (2025,  1): 112, (2025,  2): 114, (2025,  3): 127,
    (2025,  4): 140, (2025,  5): 152, (2025,  6): 160,
    (2025,  7): 174, (2025,  8): 178, (2025,  9): 155,
    (2025, 10): 135, (2025, 11): 144, (2025, 12): 120,
    (2026,  1): 114, (2026,  2): 116, (2026,  3): 129,
    (2026,  4): 142,
}

# ── EVENT DEFINITIONS ────────────────────────────────────────
# Each tuple: (event_type, client_pool, pax_range, nights_range,
#              room_block_range, group_discount, space_per_pax,
#              catering_per_pax, av_per_event)

EVENT_TYPES = {
    "meeting": {
        "client_pool":      CORPORATE_CLIENTS,
        "pax_range":        (10, 30),
        "nights_range":     (1, 1),
        "room_block_range": (5, 15),
        "group_discount":   0.85,    # 15% below BAR
        "space_per_pax":    45,      # €45/pax for room hire
        "catering_per_pax": 55,      # €55/pax for coffee breaks + lunch
        "av_flat":          350,     # flat AV charge for small meetings
    },
    "conference": {
        "client_pool":      CORPORATE_CLIENTS,
        "pax_range":        (40, 150),
        "nights_range":     (2, 3),
        "room_block_range": (20, 60),
        "group_discount":   0.82,    # 18% below BAR
        "space_per_pax":    65,
        "catering_per_pax": 120,     # full day catering + dinner
        "av_flat":          1800,    # full AV setup
    },
    "wedding": {
        "client_pool":      WEDDING_CLIENTS,
        "pax_range":        (50, 120),
        "nights_range":     (1, 2),
        "room_block_range": (15, 35),
        "group_discount":   0.88,    # 12% below BAR
        "space_per_pax":    80,      # venue hire per guest
        "catering_per_pax": 150,     # wedding dinner + drinks
        "av_flat":          1200,    # sound + lighting
    },
    "dinner": {
        "client_pool":      CORPORATE_CLIENTS,
        "pax_range":        (20, 80),
        "nights_range":     (0, 0),  # no room block
        "room_block_range": (0, 0),
        "group_discount":   1.00,    # no rooms, irrelevant
        "space_per_pax":    30,
        "catering_per_pax": 95,      # dinner + drinks
        "av_flat":          0,
    },
}

# ── EVENT CALENDAR ───────────────────────────────────────────
# Distribution logic:
# - Conferences: shoulder and low season (corporate avoids peak summer)
# - Weddings: spring (Apr-Jun) and autumn (Sep-Oct)
# - Meetings: year-round, slightly less in peak summer
# - Dinners: year-round, more in Q4 (end of year corporate dinners)

EVENT_CALENDAR = [
    # 2024
    (2024,  1, "conference", "2024-01-15", "Novo Banco Annual Planning Conference"),
    (2024,  1, "meeting",    "2024-01-23", "Deloitte Portugal Q1 Strategy Meeting"),
    (2024,  2, "dinner",     "2024-02-07", "Vodafone Portugal Board Dinner"),
    (2024,  2, "meeting",    "2024-02-20", "KPMG Portugal Client Meeting"),
    (2024,  3, "conference", "2024-03-11", "EDP Renewables Sustainability Forum"),
    (2024,  3, "meeting",    "2024-03-25", "Santander Portugal Team Meeting"),
    (2024,  4, "wedding",    "2024-04-13", "Silva & Ferreira Wedding"),
    (2024,  4, "conference", "2024-04-22", "Galp Energia Investor Conference"),
    (2024,  5, "wedding",    "2024-05-18", "Costa & Rodrigues Wedding"),
    (2024,  5, "dinner",     "2024-05-28", "TAP Air Portugal Gala Dinner"),
    (2024,  6, "wedding",    "2024-06-08", "Pereira & Santos Wedding"),
    (2024,  6, "dinner",     "2024-06-25", "Jerónimo Martins Summer Dinner"),
    (2024,  7, "meeting",    "2024-07-09", "NOS Comunicacoes Mid-Year Review"),
    (2024,  8, "dinner",     "2024-08-14", "Siemens Portugal Client Dinner"),
    (2024,  9, "conference", "2024-09-09", "Millenium BCP Annual Conference"),
    (2024,  9, "wedding",    "2024-09-28", "Martins & Oliveira Wedding"),
    (2024, 10, "conference", "2024-10-14", "Accenture Lisboa Innovation Summit"),
    (2024, 10, "meeting",    "2024-10-28", "BPI Bank Quarterly Meeting"),
    (2024, 11, "conference", "2024-11-18", "PwC Portugal Year-End Forum"),
    (2024, 11, "dinner",     "2024-11-26", "CTT Correios Corporate Dinner"),
    (2024, 12, "dinner",     "2024-12-10", "Fidelidade Seguros Christmas Dinner"),
    (2024, 12, "dinner",     "2024-12-18", "Meo Altice Year-End Dinner"),

    # 2025
    (2025,  1, "conference", "2025-01-13", "Lusitania Insurance Planning Conference"),
    (2025,  1, "meeting",    "2025-01-27", "Sonae Group Strategy Meeting"),
    (2025,  2, "dinner",     "2025-02-05", "EDP Renewables Board Dinner"),
    (2025,  2, "meeting",    "2025-02-19", "PwC Portugal Client Meeting"),
    (2025,  3, "conference", "2025-03-10", "Novo Banco Leadership Summit"),
    (2025,  3, "meeting",    "2025-03-24", "Deloitte Portugal Team Meeting"),
    (2025,  4, "wedding",    "2025-04-12", "Sousa & Carvalho Wedding"),
    (2025,  4, "conference", "2025-04-25", "Vodafone Portugal Partner Conference"),
    (2025,  5, "wedding",    "2025-05-17", "Fernandes & Lopes Wedding"),
    (2025,  5, "dinner",     "2025-05-27", "Galp Energia Summer Dinner"),
    (2025,  6, "wedding",    "2025-06-07", "Gomes & Alves Wedding"),
    (2025,  6, "dinner",     "2025-06-24", "Santander Portugal Client Dinner"),
    (2025,  7, "meeting",    "2025-07-08", "KPMG Portugal Mid-Year Review"),
    (2025,  8, "dinner",     "2025-08-13", "Accenture Lisboa Client Dinner"),
    (2025,  9, "conference", "2025-09-08", "Millenium BCP Strategy Forum"),
    (2025,  9, "wedding",    "2025-09-27", "Ribeiro & Mendes Wedding"),
    (2025, 10, "conference", "2025-10-13", "NOS Comunicacoes Annual Summit"),
    (2025, 10, "meeting",    "2025-10-27", "Siemens Portugal Quarterly Meeting"),
    (2025, 11, "conference", "2025-11-17", "BPI Bank Year-End Conference"),
    (2025, 11, "dinner",     "2025-11-25", "TAP Air Portugal Corporate Dinner"),
    (2025, 12, "dinner",     "2025-12-09", "Meo Altice Christmas Dinner"),
    (2025, 12, "dinner",     "2025-12-17", "Jerónimo Martins Year-End Dinner"),

    # 2026 YTD
    (2026,  1, "conference", "2026-01-12", "Fidelidade Seguros Planning Conference"),
    (2026,  1, "meeting",    "2026-01-26", "CTT Correios Strategy Meeting"),
    (2026,  2, "dinner",     "2026-02-04", "Novo Banco Board Dinner"),
    (2026,  2, "meeting",    "2026-02-18", "Sonae Group Team Meeting"),
    (2026,  3, "conference", "2026-03-09", "EDP Renewables Leadership Forum"),
    (2026,  3, "wedding",    "2026-03-21", "Silva & Ferreira Second Wedding Event"),
    (2026,  4, "wedding",    "2026-04-11", "Costa & Rodrigues Wedding"),
    (2026,  4, "conference", "2026-04-24", "Deloitte Portugal Client Conference"),
]


def generate_event_bookings(conn):
    with conn.cursor() as cur:
        inserted = 0
        records = []

        for year, month, etype, event_date_str, event_name in EVENT_CALENDAR:
            event_date = date.fromisoformat(event_date_str)
            cfg = EVENT_TYPES[etype]

            # Booking date: 2-8 weeks before event
            lead_weeks = random.randint(2, 8)
            booking_date = event_date - timedelta(weeks=lead_weeks)

            # Pax and nights
            pax = random.randint(*cfg["pax_range"])
            nights = random.randint(*cfg["nights_range"])

            # Room block
            if cfg["room_block_range"][1] == 0:
                num_rooms = 0
            else:
                num_rooms = random.randint(*cfg["room_block_range"])
                num_rooms = min(num_rooms, pax // 2)  # rooms can't exceed half pax
                num_rooms = max(num_rooms, 0)

            # Group rate
            bar = SEASONAL_BAR.get((year, month), 130)
            group_rate = round(bar * cfg["group_discount"] * 2) / 2  # round to 0.50

            # Associated room revenue
            associated_room_revenue = round(num_rooms * group_rate * max(nights, 1), 2) if num_rooms > 0 else 0.0

            # Event revenue components
            space_revenue    = round(pax * cfg["space_per_pax"] * (1 + np.random.normal(0, 0.05)), 2)
            catering_revenue = round(pax * cfg["catering_per_pax"] * (1 + np.random.normal(0, 0.05)), 2)
            av_revenue       = round(cfg["av_flat"] * (1 + np.random.normal(0, 0.03)), 2) if cfg["av_flat"] > 0 else 0.0

            # Floor all revenue at 0
            space_revenue    = max(space_revenue, 0)
            catering_revenue = max(catering_revenue, 0)
            av_revenue       = max(av_revenue, 0)

            total_event_revenue = round(space_revenue + catering_revenue + av_revenue, 2)

            records.append((
                PROPERTY_ID,
                booking_date,
                # pick client name from event_name if wedding, else pick from corporate list
                event_name.replace(" Wedding", "").replace(" Second Wedding Event", "") if "Wedding" in event_name else random.choice(cfg["client_pool"]),
                event_name,
                etype,
                num_rooms,
                group_rate,
                max(nights, 1),
                associated_room_revenue,
                space_revenue,
                catering_revenue,
                av_revenue,
                total_event_revenue,
            ))

        rows = execute_values(cur, """
            INSERT INTO event_bookings (
                property_id, booking_date, client_name, event_name, event_type,
                num_rooms, group_rate_per_night, num_nights,
                associated_room_revenue, space_revenue, catering_revenue,
                av_revenue, total_event_revenue
            ) VALUES %s
            RETURNING event_booking_id
        """, records, fetch=True)

        ids = [row[0] for row in rows]
        inserted = len(ids)
        conn.commit()

        for i, row in enumerate(records):
            print(f"  event_booking_id={ids[i]}: {row[3]} on {row[1]} "
                  f"({row[4]}, {row[5]} rooms, €{row[12]:,.0f} event revenue)")

        print(f"\nDone. {inserted} event bookings inserted.")
        return ids


if __name__ == "__main__":
    conn = psycopg2.connect(DB_URL)
    try:
        generate_event_bookings(conn)
    finally:
        conn.close()
