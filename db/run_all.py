"""
run_all.py
Master script — runs all generators in the correct dependency order.

Order:
  1. schema.sql       — create tables (run manually in psql or via this script)
  2. generate_property.py        — no dependencies
  3. generate_events.py          — no dependencies
  4. generate_budget_targets.py  — depends on property
  5. generate_competitor_rates.py — no FK dependencies
  6. generate_event_bookings.py  — depends on property
  7. generate_reservations.py    — depends on property + event_bookings

Usage:
  1. Set DB_URL below
  2. Make sure schema.sql has already been run against your database
  3. Run: python run_all.py

To reset and regenerate from scratch:
  python run_all.py --reset
  (drops all data and reruns all generators)
"""


import argparse
import os
import psycopg2
import sys
from dotenv import load_dotenv, find_dotenv

# ── CONFIG ───────────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

# ── IMPORT GENERATORS ────────────────────────────────────────
from generate_property        import generate_property
from generate_events          import generate_events
from generate_budget_targets  import generate_budget_targets
from generate_competitor_rates import generate_competitor_rates
from generate_event_bookings  import generate_event_bookings
from generate_reservations    import generate_reservations


# ── RESET ────────────────────────────────────────────────────
def reset_all_data(conn):
    """
    Truncates all tables in reverse dependency order.
    Resets all SERIAL sequences back to 1.
    Use this to wipe and regenerate clean data.
    """
    print("Resetting all tables...")
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE TABLE
                reservations,
                event_bookings,
                budget_targets,
                competitor_rates,
                events,
                property
            RESTART IDENTITY CASCADE;
        """)
        conn.commit()
    print("All tables cleared.\n")


# ── VALIDATION ───────────────────────────────────────────────
def validate(conn):
    """
    Basic row count checks after generation.
    Flags obvious problems before you hand the database to the team.
    """
    checks = [
        ("property",          "SELECT COUNT(*) FROM property",          1,    1),
        ("events",            "SELECT COUNT(*) FROM events",            28,   36),
        ("budget_targets",    "SELECT COUNT(*) FROM budget_targets",    36,   36),
        ("competitor_rates",  "SELECT COUNT(*) FROM competitor_rates",  80000, 100000),
        ("event_bookings",    "SELECT COUNT(*) FROM event_bookings",    40,   55),
        ("reservations",      "SELECT COUNT(*) FROM reservations",      10000, 18000),
    ]

    print("\n── Validation ──────────────────────────────────────")
    all_ok = True
    with conn.cursor() as cur:
        for table, query, min_expected, max_expected in checks:
            cur.execute(query)
            count = cur.fetchone()[0]
            status = "OK" if min_expected <= count <= max_expected else "WARN"
            if status == "WARN":
                all_ok = False
            print(f"  [{status}] {table}: {count:,} rows (expected {min_expected:,}–{max_expected:,})")

    # Constraint spot-checks
    with conn.cursor() as cur:
        # Check no active bookings have zero revenue
        cur.execute("""
            SELECT COUNT(*) FROM reservations
            WHERE booking_status = 'checked_out'
            AND total_room_revenue = 0
        """)
        bad_revenue = cur.fetchone()[0]
        status = "OK" if bad_revenue == 0 else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] checked_out bookings with zero revenue: {bad_revenue}")

        # Check no cancelled bookings have non-zero revenue
        cur.execute("""
            SELECT COUNT(*) FROM reservations
            WHERE booking_status IN ('cancelled', 'no_show')
            AND total_revenue > 0
        """)
        bad_cancel = cur.fetchone()[0]
        status = "OK" if bad_cancel == 0 else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] cancelled/no_show with non-zero revenue: {bad_cancel}")

        # Check net_rate constraint
        cur.execute("""
            SELECT COUNT(*) FROM reservations
            WHERE ABS(net_rate_per_night - rate_per_night * (1 - commission_rate)) > 0.01
        """)
        bad_net = cur.fetchone()[0]
        status = "OK" if bad_net == 0 else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] reservations with incorrect net_rate: {bad_net}")

        # Check budget_targets has one row per month
        cur.execute("""
            SELECT COUNT(*) FROM budget_targets
            WHERE EXTRACT(DAY FROM month) != 1
        """)
        bad_month = cur.fetchone()[0]
        status = "OK" if bad_month == 0 else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] budget_targets with non-first-day month: {bad_month}")

        # Check competitor_rates uniqueness
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT stay_date, hotel_name, channel, room_type, COUNT(*)
                FROM competitor_rates
                GROUP BY stay_date, hotel_name, channel, room_type
                HAVING COUNT(*) > 1
            ) dupes
        """)
        dupes = cur.fetchone()[0]
        status = "OK" if dupes == 0 else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] duplicate competitor_rate rows: {dupes}")

    print()
    if all_ok:
        print("All checks passed. Database is ready.")
    else:
        print("Some checks failed. Review warnings above before using the database.")


# ── MAIN ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Run all ATLAS data generators.")
    parser.add_argument("--reset", action="store_true",
                        help="Truncate all tables before generating")
    args = parser.parse_args()

    print("Connecting to database...")
    try:
        conn = psycopg2.connect(DB_URL)
        print("Connected.\n")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        if args.reset:
            reset_all_data(conn)

        # ── 1. Property ──────────────────────────────────────
        print("── Step 1: Property ────────────────────────────────")
        property_id = generate_property(conn)
        print()

        # ── 2. Events ────────────────────────────────────────
        print("── Step 2: Events ──────────────────────────────────")
        generate_events(conn)
        print()

        # ── 3. Budget Targets ────────────────────────────────
        print("── Step 3: Budget Targets ──────────────────────────")
        generate_budget_targets(conn)
        print()

        # ── 4. Competitor Rates ──────────────────────────────
        print("── Step 4: Competitor Rates ────────────────────────")
        generate_competitor_rates(conn)
        print()

        # ── 5. Event Bookings ────────────────────────────────
        print("── Step 5: Event Bookings ──────────────────────────")
        event_booking_ids = generate_event_bookings(conn)
        print()

        # ── 6. Reservations ──────────────────────────────────
        print("── Step 6: Reservations ────────────────────────────")
        generate_reservations(conn, event_booking_ids)
        print()

        # ── Validate ─────────────────────────────────────────
        validate(conn)

    except Exception as e:
        print(f"\nError during generation: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
