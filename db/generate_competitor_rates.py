"""
generate_competitor_rates.py
Generates competitor rate data for 16 months (Jan 2024 - Apr 2026).

Competitive set: 5 hotels including subject property + 4 competitors
Channels: direct, booking_com, expedia
Room types: standard, superior, deluxe, suite

Pricing logic:
- Base rates vary by hotel positioning (budget, parity, premium relative to subject)
- Seasonal multipliers mirror budget_targets seasonality
- Event uplifts applied from events table hardcoded values
- Day-of-week variation: weekends +8-12% over weekdays for leisure hotels
- Channel variation: direct slightly below OTA (loyalty incentive), OTAs at parity
- Room type premiums: standard=base, superior=+20%, deluxe=+45%, suite=+100%
- Competitor-specific noise: random walk with mean reversion so competitors
  drift independently rather than moving in lockstep
- Occasional sold-out dates modelled as NULL rate (not inserted)
"""

import os
import psycopg2
import numpy as np
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv

# ── CONNECTION ───────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

np.random.seed(42)

# ── DATE RANGE ───────────────────────────────────────────────
START_DATE = date(2024, 1, 1)
END_DATE   = date(2026, 4, 30)

# ── HOTELS ───────────────────────────────────────────────────
# subject_property is our hotel — included so we can compare
# positioning_factor: multiplier vs subject base rate
#   < 1.0 = cheaper competitor
#   1.0   = parity
#   > 1.0 = more expensive competitor
HOTELS = [
    {
        "hotel_name":       "Hotel Lisboa Central",   # subject property
        "hotel_star_rating": 4,
        "positioning":       1.00,
        "noise_std":         0.03,   # low noise — revenue manager is disciplined
    },
    {
        "hotel_name":       "Estoril Palace Suites",
        "hotel_star_rating": 4,
        "positioning":       1.08,   # premium 4-star, prices slightly above
        "noise_std":         0.04,
    },
    {
        "hotel_name":       "Hotel Cascais Bay",
        "hotel_star_rating": 4,
        "positioning":       0.92,   # budget competitor, undercuts on price
        "noise_std":         0.06,   # more aggressive/erratic pricing
    },
    {
        "hotel_name":       "Lisbon Riviera Hotel",
        "hotel_star_rating": 3,
        "positioning":       0.78,   # 3-star, lower tier
        "noise_std":         0.08,   # least disciplined pricing
    },
    {
        "hotel_name":       "Grand Hotel Estoril",
        "hotel_star_rating": 5,
        "positioning":       1.45,   # 5-star luxury, much higher rates
        "noise_std":         0.03,   # very stable, brand-controlled
    },
]

# ── CHANNELS ─────────────────────────────────────────────────
# Direct is slightly cheaper than OTAs (loyalty incentive strategy)
# OTAs are at parity with each other
CHANNELS = {
    "direct":      0.96,   # 4% below OTA rate
    "booking_com": 1.00,   # reference rate
    "expedia":     1.01,   # very slight premium vs Booking.com
}

# ── ROOM TYPE PREMIUMS ───────────────────────────────────────
ROOM_TYPES = {
    "standard":  1.00,
    "superior":  1.20,
    "deluxe":    1.45,
    "suite":     2.00,
}

# ── SEASONAL BASE RATES (subject property standard room, weekday) ─────────
# Derived from budget_targets ADR values
# These are the floor — actual rates vary around these
SEASONAL_BASE = {
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

# ── EVENT UPLIFTS ────────────────────────────────────────────
# Mirrors events table — date ranges and uplift factors
# Applied to all hotels (market-wide demand) with slight variation per hotel
EVENTS = [
    ("2024-01-01", "2024-01-02", 0.55),
    ("2024-02-10", "2024-02-13", 0.20),
    ("2024-03-29", "2024-04-01", 0.45),
    ("2024-04-29", "2024-05-05", 0.35),
    ("2024-06-12", "2024-06-13", 0.30),
    ("2024-06-15", "2024-06-22", 0.60),
    ("2024-07-15", "2024-08-31", 0.40),
    ("2024-09-19", "2024-09-22", 0.90),
    ("2024-10-07", "2024-10-10", 0.35),
    ("2024-11-11", "2024-11-14", 1.20),
    ("2024-12-23", "2024-12-26", 0.40),
    ("2024-12-30", "2025-01-02", 0.55),
    ("2025-03-01", "2025-03-04", 0.20),
    ("2025-04-18", "2025-04-21", 0.45),
    ("2025-04-28", "2025-05-04", 0.35),
    ("2025-06-12", "2025-06-13", 0.30),
    ("2025-07-15", "2025-08-31", 0.40),
    ("2025-09-18", "2025-09-21", 0.90),
    ("2025-09-29", "2025-10-02", 0.35),
    ("2025-11-10", "2025-11-13", 1.20),
    ("2025-12-23", "2025-12-26", 0.40),
    ("2025-12-30", "2026-01-02", 0.55),
    ("2026-02-14", "2026-02-17", 0.20),
    ("2026-04-03", "2026-04-06", 0.45),
]

# Pre-parse event dates for fast lookup
PARSED_EVENTS = [
    (date.fromisoformat(s), date.fromisoformat(e), u)
    for s, e, u in EVENTS
]


def get_event_uplift(d):
    """Return the highest applicable event uplift for a given date."""
    uplift = 0.0
    for start, end, u in PARSED_EVENTS:
        if start <= d <= end:
            uplift = max(uplift, u)
    return uplift


def get_day_of_week_multiplier(d):
    """Weekends command a premium for leisure-oriented Estoril/Lisbon hotels."""
    if d.weekday() in (4, 5):   # Friday, Saturday
        return 1.10
    elif d.weekday() == 6:       # Sunday
        return 1.05
    return 1.00                  # Mon-Thu baseline


def compute_rate(base, positioning, room_multiplier,
                 channel_multiplier, event_uplift,
                 dow_multiplier, noise_std):
    """
    Compute a single rate with all multipliers applied.
    Adds Gaussian noise to simulate natural price variation.
    Rounds to nearest 0.50 (realistic hotel pricing).
    """
    rate = (base
            * positioning
            * room_multiplier
            * channel_multiplier
            * (1 + event_uplift)
            * dow_multiplier)

    # Add noise — competitors drift independently
    noise = np.random.normal(1.0, noise_std)
    rate *= max(noise, 0.85)  # floor at 85% to avoid unrealistic lows

    # Round to nearest 0.50
    rate = round(rate * 2) / 2

    # Hard floor: no room goes below €60
    return max(rate, 60.0)


def generate_competitor_rates(conn):
    with conn.cursor() as cur:
        inserted = 0
        batch = []
        BATCH_SIZE = 1000

        current = START_DATE
        while current <= END_DATE:
            base = SEASONAL_BASE.get((current.year, current.month), 130)
            event_uplift = get_event_uplift(current)
            dow = get_day_of_week_multiplier(current)

            for hotel in HOTELS:
                for channel, ch_mult in CHANNELS.items():
                    for room_type, rm_mult in ROOM_TYPES.items():

                        rate = compute_rate(
                            base=base,
                            positioning=hotel["positioning"],
                            room_multiplier=rm_mult,
                            channel_multiplier=ch_mult,
                            event_uplift=event_uplift,
                            dow_multiplier=dow,
                            noise_std=hotel["noise_std"],
                        )

                        batch.append((
                            current,
                            hotel["hotel_name"],
                            hotel["hotel_star_rating"],
                            channel,
                            room_type,
                            rate,
                        ))

                        if len(batch) >= BATCH_SIZE:
                            cur.executemany("""
                                INSERT INTO competitor_rates (
                                    stay_date, hotel_name, hotel_star_rating,
                                    channel, room_type, rate_per_night
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                            """, batch)
                            inserted += len(batch)
                            batch = []
                            print(f"  Inserted {inserted} rows... (up to {current})")

            current += timedelta(days=1)

        # Insert remaining batch
        if batch:
            cur.executemany("""
                INSERT INTO competitor_rates (
                    stay_date, hotel_name, hotel_star_rating,
                    channel, room_type, rate_per_night
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, batch)
            inserted += len(batch)

        conn.commit()
        print(f"\nDone. {inserted:,} competitor rate rows inserted.")


if __name__ == "__main__":
    conn = psycopg2.connect(DB_URL)
    try:
        generate_competitor_rates(conn)
    finally:
        conn.close()
