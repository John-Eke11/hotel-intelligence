"""NL-to-SQL agent using a local Ollama model."""

import json
import os
import re
from datetime import date

import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

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

  Pace / Pickup    = rooms booked FOR a future stay date as of today,
                     compared to the same forward window at the same point last year
                     -- "booked for" means: check_in_date >= target_date
                     -- "as of today" means: booking_date <= CURRENT_DATE
                     -- "same point last year" means: booking_date <= CURRENT_DATE - INTERVAL '1 year'
                     -- Standard pickup query structure:
                       SELECT
                         check_in_date,
                         COUNT(*) FILTER (WHERE booking_date <= CURRENT_DATE)
                           AS bookings_on_books_this_year,
                         SUM(length_of_stay) FILTER (WHERE booking_date <= CURRENT_DATE)
                           AS room_nights_on_books_this_year,
                         COUNT(*) FILTER (WHERE booking_date <= CURRENT_DATE - INTERVAL '1 year'
                                          AND check_in_date BETWEEN
                                            from_date + INTERVAL '1 year'
                                            AND to_date + INTERVAL '1 year')
                           AS bookings_same_point_last_year
                       FROM reservations
                       WHERE property_id = {property_id}
                         AND booking_status IN ('confirmed', 'checked_out')
                         AND check_in_date >= CURRENT_DATE
                         AND check_in_date < to_date
                       GROUP BY check_in_date
                       ORDER BY check_in_date
                     -- NOTE: cancelled/no_show excluded from pace — they do not represent demand on books

  ARI (Average Rate Index) = property_avg_rate / comp_set_avg_rate
                     -- property_avg_rate: AVG(r.rate_per_night) for checked_out reservations
                     --   in the period, filtered by matching room_type and channel if specified
                     -- comp_set_avg_rate: AVG(cr.rate_per_night) FROM competitor_rates
                     --   for the same stay_date range
                     -- Default comparison: blended average across all competitors, all channels,
                     --   matching room_type only — do not filter by hotel_name unless asked
                     -- ARI > 1.0 means property is pricing above the comp set average
                     -- ARI < 1.0 means property is pricing below the comp set average
                     -- Standard ARI query structure:
                       SELECT
                         ROUND(AVG(r.rate_per_night) /
                           NULLIF((SELECT AVG(cr.rate_per_night)
                                   FROM competitor_rates cr
                                   WHERE cr.stay_date >= from_date
                                     AND cr.stay_date < to_date
                                     AND cr.room_type = r.room_type), 0), 4) AS ari
                       FROM reservations r
                       WHERE r.property_id = {property_id}
                         AND r.booking_status = 'checked_out'
                         AND r.check_in_date >= from_date
                         AND r.check_in_date < to_date
                     -- For a blended ARI across all room types, remove the room_type join condition

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

Q: What is our ADR and RevPAR year to date?
A:
SELECT
  ROUND(SUM(r.total_room_revenue) / NULLIF(SUM(r.length_of_stay), 0), 2)                  AS adr,
  ROUND(SUM(r.total_room_revenue) / NULLIF(
    MAX(p.total_rooms) * (CURRENT_DATE - DATE_TRUNC('year', CURRENT_DATE)::date), 0), 2)  AS revpar
FROM reservations r
JOIN property p ON p.property_id = r.property_id
WHERE r.property_id = {property_id}
  AND r.booking_status = 'checked_out'
  AND r.check_in_date >= DATE_TRUNC('year', CURRENT_DATE)::date
  AND r.check_in_date <  CURRENT_DATE;

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

Q: How are we tracking against budget this month?
A:
WITH actuals AS (
  SELECT
    DATE_TRUNC('month', r.check_in_date)::date        AS month,
    SUM(r.total_revenue)                               AS reservation_revenue
  FROM reservations r
  WHERE r.property_id = {property_id}
    AND r.booking_status = 'checked_out'
    AND r.check_in_date >= DATE_TRUNC('month', CURRENT_DATE)::date
    AND r.check_in_date <  (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')::date
  GROUP BY 1
),
event_actuals AS (
  SELECT COALESCE(SUM(total_event_revenue), 0) AS event_revenue
  FROM event_bookings
  WHERE property_id = {property_id}
    AND booking_date >= DATE_TRUNC('month', CURRENT_DATE)::date
    AND booking_date <  (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')::date
)
SELECT
  TO_CHAR(bt.month, 'YYYY-MM')                                                      AS month,
  ROUND(COALESCE(a.reservation_revenue, 0) + COALESCE(ea.event_revenue, 0), 2)      AS actual_revenue,
  ROUND((bt.target_occupancy
         * MAX(p.total_rooms)
         * ((bt.month + INTERVAL '1 month')::date - bt.month)
         * bt.target_adr
         + bt.target_fnb_revenue
         + bt.target_spa_revenue)::numeric, 2)                                       AS target_revenue
FROM budget_targets bt
JOIN property p ON p.property_id = bt.property_id
LEFT JOIN actuals a ON a.month = bt.month
CROSS JOIN event_actuals ea
WHERE bt.property_id = {property_id}
  AND bt.month = DATE_TRUNC('month', CURRENT_DATE)::date
GROUP BY bt.month, bt.target_occupancy, bt.target_adr,
         bt.target_fnb_revenue, bt.target_spa_revenue,
         a.reservation_revenue, ea.event_revenue;

Q: What is the average length of stay for corporate guests?
A:
-- guest_segment = 'corporate' identifies corporate guests. Do NOT use booking_channel for this.
SELECT
  ROUND(AVG(length_of_stay)::numeric, 2) AS avg_length_of_stay
FROM reservations
WHERE property_id = {property_id}
  AND booking_status = 'checked_out'
  AND guest_segment = 'corporate';

Q: Which room type performs best during events?
A:
-- room_type lives in reservations (r), NOT in events (e).
-- Join reservations to events via date overlap, then group by r.room_type.
SELECT
  r.room_type,
  COUNT(*)                                      AS bookings,
  SUM(r.length_of_stay)                         AS room_nights,
  ROUND(SUM(r.total_revenue)::numeric, 2)       AS total_revenue,
  ROUND(AVG(r.rate_per_night)::numeric, 2)      AS avg_rate
FROM reservations r
JOIN events e ON r.check_in_date BETWEEN e.event_start_date AND e.event_end_date
WHERE r.property_id = {property_id}
  AND r.booking_status = 'checked_out'
GROUP BY r.room_type
ORDER BY total_revenue DESC;

Q: How was our channel performance last month compared to the same time last year?
A:
-- Column is booking_channel (NOT channel). Use CTEs for YoY comparison.
WITH last_month AS (
  SELECT
    booking_channel,
    SUM(total_revenue)::float  AS revenue,
    COUNT(*)                   AS bookings
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
    SUM(total_revenue)::float  AS revenue,
    COUNT(*)                   AS bookings
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

Q: How did our rates compare to competitors during Web Summit?
A:
SELECT
  cr.stay_date,
  cr.hotel_name,
  cr.room_type,
  cr.channel,
  cr.rate_per_night
FROM competitor_rates cr
JOIN events e ON cr.stay_date BETWEEN e.event_start_date AND e.event_end_date
WHERE e.event_name ILIKE '%Web Summit%'
ORDER BY cr.stay_date, cr.hotel_name;


Q: What was our Net RevPAR last month?
A:
SELECT
  ROUND(
    SUM(r.net_rate_per_night * r.length_of_stay) /
    NULLIF(
      MAX(p.total_rooms) * (
        DATE_TRUNC('month', CURRENT_DATE)::date -
        DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
      ), 0
    ), 2
  ) AS net_revpar
FROM reservations r
JOIN property p ON p.property_id = r.property_id
WHERE r.property_id = {property_id}
  AND r.booking_status = 'checked_out'
  AND r.check_in_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
  AND r.check_in_date <  DATE_TRUNC('month', CURRENT_DATE)::date;

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

Q: What was our cancellation and no-show rate last month?
A:
-- Period filter uses booking_date (when the booking was made), not check_in_date.
-- Denominator includes ALL booking statuses — never pre-filter before counting.
SELECT
  COUNT(*)                                                             AS total_bookings,
  COUNT(*) FILTER (WHERE booking_status = 'cancelled')                AS cancellations,
  COUNT(*) FILTER (WHERE booking_status = 'no_show')                  AS no_shows,
  ROUND(
    COUNT(*) FILTER (WHERE booking_status = 'cancelled')::numeric /
    NULLIF(COUNT(*), 0), 4
  )                                                                    AS cancellation_rate,
  ROUND(
    COUNT(*) FILTER (WHERE booking_status = 'no_show')::numeric /
    NULLIF(COUNT(*), 0), 4
  )                                                                    AS no_show_rate
FROM reservations
WHERE property_id = {property_id}
  AND booking_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')::date
  AND booking_date <  DATE_TRUNC('month', CURRENT_DATE)::date;

Q: How does our current rate compare to the comp set this month (ARI)?
A:
-- ARI = property avg rate / comp set avg rate.
-- Blended across all room types and channels unless asked to filter.
-- comp set avg uses stay_date; property avg uses check_in_date (check_in_date limitation applies).
-- ARI > 1.0 = pricing above comp set; ARI < 1.0 = pricing below.
WITH property_rate AS (
  SELECT
    AVG(r.rate_per_night) AS avg_rate
  FROM reservations r
  WHERE r.property_id = {property_id}
    AND r.booking_status = 'checked_out'
    AND r.check_in_date >= DATE_TRUNC('month', CURRENT_DATE)::date
    AND r.check_in_date <  (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')::date
),
comp_rate AS (
  SELECT
    AVG(cr.rate_per_night) AS avg_rate
  FROM competitor_rates cr
  WHERE cr.stay_date >= DATE_TRUNC('month', CURRENT_DATE)::date
    AND cr.stay_date <  (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')::date
)
SELECT
  ROUND(pr.avg_rate, 2)                              AS property_avg_rate,
  ROUND(cr.avg_rate, 2)                              AS comp_set_avg_rate,
  ROUND(pr.avg_rate / NULLIF(cr.avg_rate, 0), 4)    AS ari
FROM property_rate pr
CROSS JOIN comp_rate cr;

Q: What is our booking pace for the next 30 days compared to the same point last year?
A:
-- Pace compares room-nights currently on the books for a future window
-- against room-nights that were on the books at the equivalent point last year.
-- This year:  check_in_date in [today, today+30), booking_date <= today, status confirmed/checked_out
-- Last year:  check_in_date in [today-1yr, today-1yr+30), booking_date <= today-1yr, status checked_out only
--             (no confirmed bookings exist in the past by definition)
WITH this_year AS (
  SELECT
    check_in_date,
    COUNT(*)              AS bookings,
    SUM(length_of_stay)   AS room_nights_on_books
  FROM reservations
  WHERE property_id = {property_id}
    AND booking_status IN ('confirmed', 'checked_out')
    AND check_in_date >= CURRENT_DATE
    AND check_in_date <  CURRENT_DATE + INTERVAL '30 days'
    AND booking_date  <= CURRENT_DATE
  GROUP BY check_in_date
),
last_year AS (
  SELECT
    check_in_date + INTERVAL '1 year'   AS check_in_date,   -- shift to this year for alignment
    COUNT(*)                            AS bookings,
    SUM(length_of_stay)                 AS room_nights_on_books
  FROM reservations
  WHERE property_id = {property_id}
    AND booking_status = 'checked_out'
    AND check_in_date >= CURRENT_DATE - INTERVAL '1 year'
    AND check_in_date <  CURRENT_DATE - INTERVAL '1 year' + INTERVAL '30 days'
    AND booking_date  <= CURRENT_DATE - INTERVAL '1 year'
  GROUP BY check_in_date
)
SELECT
  COALESCE(ty.check_in_date, ly.check_in_date)       AS stay_date,
  COALESCE(ty.room_nights_on_books, 0)                AS room_nights_ty,
  COALESCE(ly.room_nights_on_books, 0)                AS room_nights_ly,
  COALESCE(ty.room_nights_on_books, 0) -
    COALESCE(ly.room_nights_on_books, 0)              AS pickup_variance,
  ROUND(
    (COALESCE(ty.room_nights_on_books, 0) -
     COALESCE(ly.room_nights_on_books, 0))::numeric /
    NULLIF(ly.room_nights_on_books, 0) * 100, 1
  )                                                   AS variance_pct
FROM this_year ty
FULL OUTER JOIN last_year ly USING (check_in_date)
ORDER BY stay_date;
"""

_SQL_SYSTEM = """\
You are an expert PostgreSQL analyst for a hotel revenue management system. /no_think
Today's date is {today}.
Convert the user's question into a single valid SQL statement.
{schema}

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
- Always write MAX(p.total_rooms) when using property.total_rooms alongside aggregate functions — never use bare p.total_rooms in an aggregate query. Only reference p.total_rooms in queries that JOIN the property table.
- For KPIs requiring multiple steps (pace, ARI, budget variance, TRevPAR), always use CTEs. Never inline subqueries where a CTE was shown in the examples.
- Output ONLY the raw SQL — no explanation, no markdown, no code fences.
- Add LIMIT 50 to row-level queries; aggregates do not need a limit.
- Use only SELECT statements.
"""

_SUMMARY_SYSTEM = """\
You are a hotel revenue analyst assistant. /no_think Today's date is {today}.
Given a user's question and query results, write a clear answer analyzing the data and the implications.
Be specific: include key numbers, percentages, or rankings from the data.
Do not repeat raw data row-by-row. Do not mention SQL.
"""


def _call_ollama(messages: list[dict]) -> str:
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False, "think": False},
        timeout=180,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"]
    return _strip_thinking(content).strip()


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> blocks emitted by Qwen3 in thinking mode."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


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

    # SELECT embedded in explanation text
    sql_start = re.search(r"\bSELECT\b", text, re.IGNORECASE)
    if sql_start:
        candidate = text[sql_start.start():]
        last_semi = candidate.rfind(";")
        if last_semi != -1:
            return candidate[: last_semi + 1].strip()
        return candidate.strip()

    # WITH CTE — require the full CTE pattern (WITH <name> AS () to avoid
    # matching ordinary English sentences that start with "with"
    cte_start = re.search(r"\bWITH\s+\w+\s+AS\s*\(", text, re.IGNORECASE)
    if cte_start:
        candidate = text[cte_start.start():]
        last_semi = candidate.rfind(";")
        if last_semi != -1:
            return candidate[: last_semi + 1].strip()
        return candidate.strip()

    return None


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
You are a hotel revenue intelligence assistant for Hotel Lisboa Central. /no_think Today's date is {today}.
You have access to a PostgreSQL database and deep hospitality industry knowledge.

════ STEP 1 — DECIDE ════
Answer directly (ANSWER:) when the question:
  - Asks for a definition or explanation (e.g. "what is RevPAR?", "explain ADR")
  - Asks for your opinion, recommendation, or analysis of data already in the conversation
  - Asks about industry benchmarks, best practices, or general hospitality knowledge
  - Is a follow-up that can be answered from results already shown in the conversation
  - Asks about the current date, month, or year

Query the database (SQL) when the question:
  - Asks for specific numbers, metrics, or trends from this hotel's data
  - Asks about actual performance (occupancy, revenue, ADR, bookings, etc.)
  - Requires fresh data not already shown in the conversation

════ STEP 2 — OUTPUT ════
- Direct answer: start with "ANSWER: " followed immediately by your response.
- Database query: output ONLY the raw SQL (SELECT or WITH) — no labels, no explanation, no code fences.

Examples of DIRECT answers (no SQL needed):
  Q: What is RevPAR?
  ANSWER: RevPAR (Revenue Per Available Room) is total room revenue divided by total available rooms...

  Q: What month is it?
  ANSWER: Today is {today}, so the current month is...

  Q: Is that occupancy good or bad?
  ANSWER: Based on the data we just looked at, an occupancy of X% for a 4-star Lisbon hotel in [month]...

  Q: What drives demand in Lisbon in summer?
  ANSWER: Lisbon's summer demand is primarily driven by leisure tourism from the UK, Spain, and Germany...

════ DATABASE SCHEMA & SQL RULES (only apply when generating SQL) ════

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
- For multi-step KPIs use CTEs, not inline subqueries.
- Every column referenced in a JOIN condition must be explicitly selected in the CTE — never reference a column in ON/WHERE that was not included in the CTE's SELECT list.
- CTEs that are joined by stay_date or check_in_date MUST include that date column in their SELECT. CTEs that are CROSS JOINed (single aggregate row) must NOT include date columns.
- Add LIMIT 50 to row-level queries; aggregates do not need a limit.

"""

_CONTEXTUAL_SUMMARY_SYSTEM = """\
You are a hotel revenue intelligence assistant for Hotel Lisboa Central. /no_think Today's date is {today}.
Given a user's question and the database results that answered it, write a thorough analysis as an experienced revenue manager would.
- Output ONLY natural language text. Never generate SQL queries.
- Lead with the direct answer to the question (key number, trend, or finding).
- Follow with analysis: what does this mean for the business? Is it good or bad? What might be driving it?
- IF relevant: compare to industry benchmarks, highlight outliers, or flag revenue opportunities.
- Your analysis should be easy to scan with a clear recommendation and not overwhelm the user with too much text unless requested.
- Humanize your analysis using natural language so it's easy to understand.
- Reference earlier conversation context when relevant (comparisons, trends, follow-ups).
- Do not repeat raw data row-by-row. Do not mention SQL.
"""


def generate_sql_or_answer(messages: list[dict], property_id: int = 1) -> tuple[str, bool]:
    """
    Takes the full conversation as Ollama-format messages (role + content strings).
    Returns (content, is_sql):
      is_sql=True  → content is a SQL query ready to execute
      is_sql=False → content is a direct text answer
    """
    system = _ROUTER_SYSTEM.format(
        schema=_SCHEMA,
        kpi_formulas=_KPI_FORMULAS.format(property_id=property_id),
        few_shot_examples=_FEW_SHOT_EXAMPLES.format(property_id=property_id),
        property_id=property_id,
        today=date.today().isoformat(),
    )
    full_messages = [{"role": "system", "content": system}] + messages
    raw = _call_ollama(full_messages)

    # Direct answer — check before anything else
    if "ANSWER:" in raw.upper():
        idx = raw.upper().find("ANSWER:")
        return raw[idx + 7:].strip(), False

    # Try to extract SQL from the response (handles clean SQL, code fences,
    # Q:/A: wrappers, and SQL embedded inside explanations)
    sql = _extract_sql(raw)
    if sql:
        return sql, True

    # Fallback: treat as a direct answer
    return raw.strip(), False


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
                "Provide a thorough revenue management analysis of these results. Do not generate SQL."
            ),
        },
    ]
    return _call_ollama(full_messages)
