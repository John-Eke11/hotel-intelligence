"""
generate_budget_targets.py
Generates and inserts monthly budget targets into the budget_targets table.
One row per month covering January 2024 - December 2026 (36 months).
Run after generate_property.py.

Seasonality modelled on INE (Statistics Portugal) data for 4-star Lisbon hotels:
- Low season:    Jan, Feb, Dec          occupancy ~55-60%, ADR ~115-120
- Shoulder:      Mar, Apr, Oct, Nov     occupancy ~65-72%, ADR ~130-145
- High season:   May, Jun, Sep          occupancy ~78-82%, ADR ~155-165
- Peak summer:   Jul, Aug               occupancy ~88-92%, ADR ~175-185
- Web Summit:    Nov                    +15% ADR premium over shoulder
- F&B and spa targets scale with occupancy
"""

import os
import psycopg2
from datetime import date
from dotenv import load_dotenv, find_dotenv

# ── CONNECTION ───────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

# ── PROPERTY ─────────────────────────────────────────────────
PROPERTY_ID = 1

# ── MONTHLY TARGETS ──────────────────────────────────────────
# Format: (year, month, target_occupancy, target_adr, target_fnb, target_spa)
# F&B target: avg €18/occupied room night (breakfast + bar)
# Spa target: avg €8/occupied room night
# Both scale with occupancy x total_rooms x days_in_month

MONTHLY_TARGETS = [
    # 2024
    (2024,  1, 0.57, 115.00, 16200,  7200),  # Jan - low season
    (2024,  2, 0.58, 116.00, 15800,  7000),  # Feb - low season, Carnival uplift
    (2024,  3, 0.65, 130.00, 19500,  8700),  # Mar - shoulder, Easter late Mar
    (2024,  4, 0.72, 142.00, 23400,  9800),  # Apr - shoulder, Easter + Estoril Open
    (2024,  5, 0.78, 155.00, 27800, 11200),  # May - high season begins
    (2024,  6, 0.82, 162.00, 30500, 12400),  # Jun - high season, Santo Antonio, Rock in Rio
    (2024,  7, 0.90, 178.00, 36900, 15200),  # Jul - peak summer
    (2024,  8, 0.91, 182.00, 37900, 15600),  # Aug - peak summer
    (2024,  9, 0.80, 158.00, 28900, 11800),  # Sep - high season, Ironman
    (2024, 10, 0.70, 138.00, 22200,  9400),  # Oct - shoulder, Congress
    (2024, 11, 0.73, 148.00, 24400, 10200),  # Nov - shoulder + Web Summit premium
    (2024, 12, 0.60, 122.00, 18500,  7800),  # Dec - low season, Christmas uplift

    # 2025
    (2025,  1, 0.58, 117.00, 16500,  7400),  # Jan - low season
    (2025,  2, 0.59, 118.00, 16200,  7200),  # Feb - low season
    (2025,  3, 0.66, 132.00, 20000,  8900),  # Mar - shoulder
    (2025,  4, 0.74, 145.00, 24500, 10200),  # Apr - shoulder, Easter + Estoril Open
    (2025,  5, 0.79, 157.00, 28400, 11500),  # May - high season
    (2025,  6, 0.83, 164.00, 31200, 12700),  # Jun - high season, Santo Antonio
    (2025,  7, 0.91, 180.00, 37600, 15500),  # Jul - peak summer
    (2025,  8, 0.92, 184.00, 38600, 15900),  # Aug - peak summer
    (2025,  9, 0.81, 160.00, 29500, 12000),  # Sep - high season, Ironman, Congress
    (2025, 10, 0.71, 140.00, 22700,  9600),  # Oct - shoulder
    (2025, 11, 0.74, 150.00, 24900, 10400),  # Nov - shoulder + Web Summit premium
    (2025, 12, 0.61, 124.00, 18900,  8000),  # Dec - low season, Christmas uplift

    # 2026
    (2026,  1, 0.59, 118.00, 16800,  7500),  # Jan - low season
    (2026,  2, 0.60, 120.00, 16500,  7300),  # Feb - low season, Carnival
    (2026,  3, 0.67, 134.00, 20500,  9100),  # Mar - shoulder
    (2026,  4, 0.75, 147.00, 25200, 10500),  # Apr - shoulder, Easter
    (2026,  5, 0.80, 159.00, 29000, 11800),  # May - high season begins
    (2026,  6, 0.84, 166.00, 31900, 13000),  # Jun - high season, Santo Antonio
    (2026,  7, 0.92, 182.00, 38400, 15800),  # Jul - peak summer
    (2026,  8, 0.93, 186.00, 39300, 16200),  # Aug - peak summer
    (2026,  9, 0.82, 162.00, 30100, 12200),  # Sep - high season, Ironman
    (2026, 10, 0.72, 142.00, 23200,  9800),  # Oct - shoulder
    (2026, 11, 0.75, 152.00, 25400, 10600),  # Nov - shoulder + Web Summit premium
    (2026, 12, 0.62, 126.00, 19300,  8200),  # Dec - low season, Christmas uplift
]


def generate_budget_targets(conn):
    with conn.cursor() as cur:
        inserted = 0
        for row in MONTHLY_TARGETS:
            year, month, occ, adr, fnb, spa = row
            month_date = date(year, month, 1)

            cur.execute("""
                INSERT INTO budget_targets (
                    property_id, month,
                    target_occupancy, target_adr,
                    target_fnb_revenue, target_spa_revenue
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING budget_id;
            """, (PROPERTY_ID, month_date, occ, adr, fnb, spa))

            budget_id = cur.fetchone()[0]
            print(f"  budget_id={budget_id}: {month_date.strftime('%b %Y')} "
                  f"occ={occ:.0%} ADR=€{adr:.0f} F&B=€{fnb:,} Spa=€{spa:,}")
            inserted += 1

        conn.commit()
        print(f"\nDone. {inserted} monthly budget targets inserted.")


if __name__ == "__main__":
    conn = psycopg2.connect(DB_URL)
    try:
        generate_budget_targets(conn)
    finally:
        conn.close()
