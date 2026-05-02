"""
generate_reservations.py
Generates individual room bookings for 16 months (Jan 2024 - Apr 2026).

Statistical parameters grounded in Kaggle Portuguese hotel booking dataset
(Antonio Periáñez, ~119K real bookings from two Portuguese hotels).

Volume:    ~13,600 bookings across 16 months
Segments:  55% leisure, 30% corporate, 15% group
Channels:  vary by segment (see CHANNEL_DIST below)
Lead time: vary by segment (leisure longer, corporate shorter)
LOS:       vary by segment
Rates:     derived from seasonal base rates + room type premium + noise
F&B/Spa:   vary by segment with Gaussian noise

Constraints respected:
- length_of_stay = check_out - check_in
- lead_time_days = check_in - booking_date
- net_rate_per_night = rate_per_night * (1 - commission_rate)
- total_room_revenue = rate_per_night * length_of_stay (0 if cancelled/no_show)
- total_revenue = total_room_revenue + fnb + spa (0 if cancelled/no_show)
- cancelled/no_show: all revenue fields = 0
- group bookings link to event_bookings via event_booking_id

Run after generate_event_bookings.py.
"""

import os
import psycopg2
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import random
from dotenv import load_dotenv, find_dotenv

# ── CONNECTION ───────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

np.random.seed(7)
random.seed(7)

PROPERTY_ID  = 1
TOTAL_ROOMS  = 100
START_DATE   = date(2024, 1, 1)
END_DATE     = date(2026, 4, 30)

# ── SEASONAL BASE RATES (standard room, subject property) ────
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

# ── SEASONAL OCCUPANCY TARGETS ───────────────────────────────
SEASONAL_OCC = {
    (2024,  1): 0.57, (2024,  2): 0.58, (2024,  3): 0.65,
    (2024,  4): 0.72, (2024,  5): 0.78, (2024,  6): 0.82,
    (2024,  7): 0.90, (2024,  8): 0.91, (2024,  9): 0.80,
    (2024, 10): 0.70, (2024, 11): 0.73, (2024, 12): 0.60,
    (2025,  1): 0.58, (2025,  2): 0.59, (2025,  3): 0.66,
    (2025,  4): 0.74, (2025,  5): 0.79, (2025,  6): 0.83,
    (2025,  7): 0.91, (2025,  8): 0.92, (2025,  9): 0.81,
    (2025, 10): 0.71, (2025, 11): 0.74, (2025, 12): 0.61,
    (2026,  1): 0.59, (2026,  2): 0.60, (2026,  3): 0.67,
    (2026,  4): 0.75,
}

# ── EVENT UPLIFTS ────────────────────────────────────────────
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
PARSED_EVENTS = [
    (date.fromisoformat(s), date.fromisoformat(e), u)
    for s, e, u in EVENTS
]

def get_event_uplift(d):
    for start, end, u in PARSED_EVENTS:
        if start <= d <= end:
            return u
    return 0.0

def get_dow_multiplier(d):
    if d.weekday() in (4, 5):
        return 1.10
    elif d.weekday() == 6:
        return 1.05
    return 1.00

# ── SEGMENT CONFIG ───────────────────────────────────────────
SEGMENTS = ["leisure", "corporate", "group"]
SEGMENT_WEIGHTS = [0.55, 0.30, 0.15]

CHANNEL_DIST = {
    "leisure":   {
        "channels": ["direct", "booking_com", "expedia", "travel_agent"],
        "weights":  [0.40, 0.35, 0.15, 0.10],
    },
    "corporate": {
        "channels": ["corporate_account", "direct", "booking_com"],
        "weights":  [0.60, 0.25, 0.15],
    },
    "group": {
        "channels": ["direct"],
        "weights":  [1.00],
    },
}

COMMISSION = {
    "direct":            0.00,
    "booking_com":       0.18,
    "expedia":           0.17,
    "corporate_account": 0.00,
    "travel_agent":      0.12,
}

ROOM_TYPES = ["standard", "superior", "deluxe", "suite"]
ROOM_WEIGHTS = [0.45, 0.30, 0.18, 0.07]

ROOM_MULTIPLIER = {
    "standard":  1.00,
    "superior":  1.20,
    "deluxe":    1.45,
    "suite":     2.00,
}

# Lead time params (mean, std) in days by segment
LEAD_TIME_PARAMS = {
    "leisure":   (45, 30),
    "corporate": (14, 10),
    "group":     (60, 20),
}

# Length of stay params (mean, std) in nights by segment
LOS_PARAMS = {
    "leisure":   (3.2, 1.5),
    "corporate": (1.8, 0.8),
    "group":     (2.5, 1.0),
}

# F&B per occupied room night by segment (mean, std)
FNB_PARAMS = {
    "leisure":   (22, 6),
    "corporate": (18, 5),
    "group":     (15, 4),
}

# Spa per occupied room night by segment (mean, std)
SPA_PARAMS = {
    "leisure":   (12, 5),
    "corporate": (6,  3),
    "group":     (4,  2),
}

# Cancellation/no-show rate by channel
CANCEL_RATE = {
    "direct":            0.05,
    "booking_com":       0.18,
    "expedia":           0.16,
    "corporate_account": 0.04,
    "travel_agent":      0.08,
}

# Guest countries (weighted by typical Lisbon tourism mix from Turismo de Portugal)
GUEST_COUNTRIES = ["Portugal", "UK", "Spain", "France", "Germany",
                   "USA", "Brazil", "Netherlands", "Italy", "Belgium"]
COUNTRY_WEIGHTS  = [0.20, 0.15, 0.12, 0.10, 0.08, 0.08, 0.07, 0.06, 0.05, 0.09]


def sample_los(segment):
    mean, std = LOS_PARAMS[segment]
    los = int(round(np.random.normal(mean, std)))
    return max(los, 1)


def sample_lead_time(segment):
    mean, std = LEAD_TIME_PARAMS[segment]
    lt = int(round(abs(np.random.normal(mean, std))))
    return max(lt, 0)


def sample_rate(check_in, room_type, segment):
    base = SEASONAL_BAR.get((check_in.year, check_in.month), 130)
    event_uplift = get_event_uplift(check_in)
    dow = get_dow_multiplier(check_in)
    rm_mult = ROOM_MULTIPLIER[room_type]

    # Corporate gets slight discount vs leisure
    seg_mult = 0.90 if segment == "corporate" else 1.00
    # Group gets group discount
    seg_mult = 0.85 if segment == "group" else seg_mult

    rate = base * rm_mult * seg_mult * (1 + event_uplift) * dow
    noise = np.random.normal(1.0, 0.04)
    rate *= max(noise, 0.85)
    rate = round(rate * 2) / 2  # round to nearest 0.50
    return max(rate, 60.0)


def sample_ancillary(segment, los, status):
    if status in ("cancelled", "no_show"):
        return 0.0, 0.0

    fnb_mean, fnb_std = FNB_PARAMS[segment]
    spa_mean, spa_std = SPA_PARAMS[segment]

    fnb = max(0, np.random.normal(fnb_mean, fnb_std)) * los
    spa = max(0, np.random.normal(spa_mean, spa_std)) * los

    # Spa: not every guest uses it — 40% leisure, 20% corporate, 10% group
    spa_probability = {"leisure": 0.40, "corporate": 0.20, "group": 0.10}
    if random.random() > spa_probability[segment]:
        spa = 0.0

    return round(fnb, 2), round(spa, 2)


def generate_reservations(conn, event_booking_ids):
    """
    event_booking_ids: list of event_booking_id integers returned by
    generate_event_bookings — used to link group room blocks.
    """
    with conn.cursor() as cur:
        inserted  = 0
        batch     = []
        BATCH_SIZE = 500

        # We iterate day by day and decide how many check-ins occur each day
        current = START_DATE
        guest_id_counter = 1
        # Track room nights used per day to respect occupancy
        rooms_used = {}  # date -> int

        def rooms_on_date(d):
            return rooms_used.get(d, 0)

        def add_rooms(check_in, check_out, count):
            d = check_in
            while d < check_out:
                rooms_used[d] = rooms_used.get(d, 0) + count
                d += timedelta(days=1)

        # Pre-assign group bookings to event_booking_ids
        # Each event_booking generates one "master" reservation
        # for its room block — we handle these first
        group_event_ids_queue = list(event_booking_ids)

        while current <= END_DATE:
            occ_target = SEASONAL_OCC.get((current.year, current.month), 0.70)

            # How many rooms are already occupied on this date
            already_occupied = rooms_on_date(current)
            capacity = TOTAL_ROOMS - already_occupied

            # Expected new check-ins today based on avg LOS
            # With avg LOS of 2.5, ~1/2.5 = 40% of occupied rooms check in each day
            avg_los = 2.5
            target_occupied_today = int(TOTAL_ROOMS * occ_target)
            expected_checkins = max(0, int(
                (target_occupied_today - already_occupied) + target_occupied_today / avg_los
            ))
            # Add some daily noise
            expected_checkins = max(0, int(np.random.normal(expected_checkins, expected_checkins * 0.15)))
            expected_checkins = min(expected_checkins, capacity)

            for _ in range(expected_checkins):
                # Sample segment
                segment = random.choices(SEGMENTS, weights=SEGMENT_WEIGHTS)[0]

                # Sample channel
                ch_cfg  = CHANNEL_DIST[segment]
                channel = random.choices(ch_cfg["channels"], weights=ch_cfg["weights"])[0]

                # Sample room type
                room_type = random.choices(ROOM_TYPES, weights=ROOM_WEIGHTS)[0]

                # Lead time and booking date
                lead_time = sample_lead_time(segment)
                booking_date = current - timedelta(days=lead_time)
                if booking_date < date(2023, 1, 1):
                    booking_date = date(2023, 1, 1)

                # Length of stay
                los = sample_los(segment)
                check_out = current + timedelta(days=los)

                # Check we don't exceed capacity significantly
                future_rooms = rooms_on_date(current)
                if future_rooms >= TOTAL_ROOMS:
                    continue

                # Rate
                rate = sample_rate(current, room_type, segment)
                commission = COMMISSION[channel]
                net_rate   = float(
                    (Decimal(str(rate)) * (Decimal('1') - Decimal(str(commission))))
                    .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                )

                # Booking status
                cancel_prob = CANCEL_RATE[channel]
                rand = random.random()
                if rand < cancel_prob * 0.7:
                    status = "cancelled"
                elif rand < cancel_prob:
                    status = "no_show"
                else:
                    status = "checked_out"

                # Revenue
                if status in ("cancelled", "no_show"):
                    total_room = 0.0
                    fnb        = 0.0
                    spa        = 0.0
                    total_rev  = 0.0
                else:
                    total_room = round(rate * los, 2)
                    fnb, spa   = sample_ancillary(segment, los, status)
                    total_rev  = round(total_room + fnb + spa, 2)
                    add_rooms(current, check_out, 1)

                # Guest country
                country = random.choices(GUEST_COUNTRIES, weights=COUNTRY_WEIGHTS)[0]

                # Event booking link for group segment
                event_booking_id = None
                if segment == "group" and group_event_ids_queue:
                    event_booking_id = group_event_ids_queue[0]
                    # Each event booking id used for avg 8-15 reservations
                    if random.random() < 0.12:  # ~1/8 chance of cycling to next event
                        group_event_ids_queue.pop(0)
                        if group_event_ids_queue:
                            event_booking_id = group_event_ids_queue[0]

                guest_id = guest_id_counter
                guest_id_counter += 1
                # 15% chance of repeat guest
                if random.random() < 0.15 and guest_id_counter > 100:
                    guest_id = random.randint(1, guest_id_counter - 1)

                batch.append((
                    PROPERTY_ID,
                    guest_id,
                    event_booking_id,
                    booking_date,
                    current,           # check_in_date
                    check_out,         # check_out_date
                    los,               # length_of_stay
                    lead_time,         # lead_time_days
                    country,
                    segment,
                    channel,
                    room_type,
                    commission,
                    rate,
                    net_rate,
                    total_room,
                    fnb,
                    spa,
                    total_rev,
                    status,
                ))

                if len(batch) >= BATCH_SIZE:
                    cur.executemany("""
                        INSERT INTO reservations (
                            property_id, guest_id, event_booking_id,
                            booking_date, check_in_date, check_out_date,
                            length_of_stay, lead_time_days,
                            guest_country, guest_segment, booking_channel,
                            room_type, commission_rate, rate_per_night,
                            net_rate_per_night, total_room_revenue,
                            fnb_revenue, spa_revenue, total_revenue,
                            booking_status
                        ) VALUES (
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                        )
                    """, batch)
                    inserted += len(batch)
                    batch = []
                    print(f"  Inserted {inserted:,} reservations... (check-ins up to {current})")

            current += timedelta(days=1)

        # Insert remaining
        if batch:
            cur.executemany("""
                INSERT INTO reservations (
                    property_id, guest_id, event_booking_id,
                    booking_date, check_in_date, check_out_date,
                    length_of_stay, lead_time_days,
                    guest_country, guest_segment, booking_channel,
                    room_type, commission_rate, rate_per_night,
                    net_rate_per_night, total_room_revenue,
                    fnb_revenue, spa_revenue, total_revenue,
                    booking_status
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
            """, batch)
            inserted += len(batch)

        conn.commit()
        print(f"\nDone. {inserted:,} reservations inserted.")


if __name__ == "__main__":
    # event_booking_ids must be fetched from the database
    # after generate_event_bookings.py has been run
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT event_booking_id FROM event_bookings ORDER BY event_booking_id")
            event_booking_ids = [row[0] for row in cur.fetchall()]

        print(f"Found {len(event_booking_ids)} event bookings to link.")
        generate_reservations(conn, event_booking_ids)
    finally:
        conn.close()
