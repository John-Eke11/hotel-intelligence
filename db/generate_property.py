"""
generate_property.py
Generates and inserts one row into the property table.
Run this first before any other generator.
"""

import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

# ── CONNECTION ──────────────────────────────────────────────
load_dotenv(find_dotenv())
DB_URL = os.environ["DATABASE_URL"]

# ── PROPERTY DATA ────────────────────────────────────────────
# Modelled on a 4-star independent hotel in Lisbon
# Comparable to Hotel Inglaterra (69 rooms) but slightly larger
PROPERTY = {
    "property_name": "Hotel Lisboa Central",
    "total_rooms":   100,
    "star_rating":   4,
    "city":          "Lisbon",
}

# ── INSERT ───────────────────────────────────────────────────
def generate_property(conn):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO property (property_name, total_rooms, star_rating, city)
            VALUES (%(property_name)s, %(total_rooms)s, %(star_rating)s, %(city)s)
            RETURNING property_id;
        """, PROPERTY)
        property_id = cur.fetchone()[0]
        conn.commit()
        print(f"Inserted property '{PROPERTY['property_name']}' with property_id = {property_id}")
        return property_id


if __name__ == "__main__":
    conn = psycopg2.connect(DB_URL)
    try:
        generate_property(conn)
    finally:
        conn.close()
