-- ============================================
-- ATLAS Prototype — PostgreSQL Schema
-- 6 tables, constraints, foreign keys
-- ============================================

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS reservations CASCADE;
DROP TABLE IF EXISTS event_bookings CASCADE;
DROP TABLE IF EXISTS budget_targets CASCADE;
DROP TABLE IF EXISTS competitor_rates CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS property CASCADE;


-- ============================================
-- 1. PROPERTY
-- One row per hotel. V0 has one property.
-- ============================================
CREATE TABLE property (
    property_id    SERIAL PRIMARY KEY,
    property_name  VARCHAR(100) NOT NULL,
    total_rooms    INTEGER NOT NULL CHECK (total_rooms > 0),
    star_rating    INTEGER NOT NULL CHECK (star_rating BETWEEN 1 AND 5),
    city           VARCHAR(100) NOT NULL
);


-- ============================================
-- 2. EVENTS
-- External demand drivers (Iron Man, congresses).
-- Not owned by any property.
-- ============================================
CREATE TABLE events (
    event_id               SERIAL PRIMARY KEY,
    event_name             VARCHAR(200) NOT NULL,
    event_start_date       DATE NOT NULL,
    event_end_date         DATE NOT NULL,
    event_type             VARCHAR(50) NOT NULL CHECK (event_type IN ('sporting', 'congress', 'festival', 'holiday')),
    historical_rate_uplift DECIMAL(5,2) NOT NULL CHECK (historical_rate_uplift >= 0),
    is_recurring           BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_event_dates CHECK (event_end_date >= event_start_date)
);


-- ============================================
-- 3. EVENT_BOOKINGS
-- Group business hosted at the property.
-- ============================================
CREATE TABLE event_bookings (
    event_booking_id       SERIAL PRIMARY KEY,
    property_id            INTEGER NOT NULL REFERENCES property(property_id),
    booking_date           DATE NOT NULL,
    client_name            VARCHAR(200) NOT NULL,
    event_name             VARCHAR(200) NOT NULL,
    event_type             VARCHAR(50) NOT NULL CHECK (event_type IN ('meeting', 'conference', 'wedding', 'dinner')),
    num_rooms              INTEGER NOT NULL CHECK (num_rooms >= 0),
    group_rate_per_night   DECIMAL(10,2) NOT NULL CHECK (group_rate_per_night >= 0),
    num_nights             INTEGER NOT NULL CHECK (num_nights > 0),
    associated_room_revenue DECIMAL(10,2) NOT NULL CHECK (associated_room_revenue >= 0),
    space_revenue          DECIMAL(10,2) NOT NULL CHECK (space_revenue >= 0),
    catering_revenue       DECIMAL(10,2) NOT NULL CHECK (catering_revenue >= 0),
    av_revenue             DECIMAL(10,2) NOT NULL CHECK (av_revenue >= 0),
    total_event_revenue    DECIMAL(10,2) NOT NULL CHECK (total_event_revenue >= 0),

    CONSTRAINT chk_associated_room_revenue CHECK (
        associated_room_revenue = num_rooms * group_rate_per_night * num_nights
    ),
    CONSTRAINT chk_total_event_revenue CHECK (
        total_event_revenue = space_revenue + catering_revenue + av_revenue
    )
);


-- ============================================
-- 4. RESERVATIONS
-- Individual room bookings from PMS.
-- ============================================
CREATE TABLE reservations (
    booking_id         SERIAL PRIMARY KEY,
    property_id        INTEGER NOT NULL REFERENCES property(property_id),
    guest_id           INTEGER NOT NULL,
    event_booking_id   INTEGER REFERENCES event_bookings(event_booking_id),
    booking_date       DATE NOT NULL,
    check_in_date      DATE NOT NULL,
    check_out_date     DATE NOT NULL,
    length_of_stay     INTEGER NOT NULL CHECK (length_of_stay > 0),
    lead_time_days     INTEGER NOT NULL CHECK (lead_time_days >= 0),
    guest_country      VARCHAR(100),
    guest_segment      VARCHAR(50) NOT NULL CHECK (guest_segment IN ('leisure', 'corporate', 'group')),
    booking_channel    VARCHAR(50) NOT NULL CHECK (booking_channel IN ('direct', 'booking_com', 'expedia', 'corporate_account', 'travel_agent')),
    room_type          VARCHAR(50) NOT NULL CHECK (room_type IN ('standard', 'superior', 'deluxe', 'suite')),
    commission_rate    DECIMAL(4,2) NOT NULL CHECK (commission_rate BETWEEN 0 AND 1),
    rate_per_night     DECIMAL(10,2) NOT NULL CHECK (rate_per_night >= 0),
    net_rate_per_night DECIMAL(10,2) NOT NULL CHECK (net_rate_per_night >= 0),
    total_room_revenue DECIMAL(10,2) NOT NULL CHECK (total_room_revenue >= 0),
    fnb_revenue        DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (fnb_revenue >= 0),
    spa_revenue        DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (spa_revenue >= 0),
    total_revenue      DECIMAL(10,2) NOT NULL CHECK (total_revenue >= 0),
    booking_status     VARCHAR(50) NOT NULL CHECK (booking_status IN ('confirmed', 'checked_out', 'cancelled', 'no_show')),

    CONSTRAINT chk_dates CHECK (check_out_date > check_in_date),
    CONSTRAINT chk_booking_before_checkin CHECK (booking_date <= check_in_date),
    CONSTRAINT chk_length_of_stay CHECK (length_of_stay = check_out_date - check_in_date),
    CONSTRAINT chk_lead_time CHECK (lead_time_days = check_in_date - booking_date),
    CONSTRAINT chk_net_rate CHECK (net_rate_per_night = ROUND(rate_per_night * (1 - commission_rate), 2)),
    CONSTRAINT chk_total_room_revenue CHECK (
        (booking_status IN ('cancelled', 'no_show') AND total_room_revenue = 0)
        OR (booking_status NOT IN ('cancelled', 'no_show') AND total_room_revenue = rate_per_night * length_of_stay)
    ),
    CONSTRAINT chk_total_revenue CHECK (
        (booking_status IN ('cancelled', 'no_show') AND total_revenue = 0)
        OR (booking_status NOT IN ('cancelled', 'no_show') AND total_revenue = total_room_revenue + fnb_revenue + spa_revenue)
    ),
    CONSTRAINT chk_cancelled_no_revenue CHECK (
        (booking_status NOT IN ('cancelled', 'no_show'))
        OR (fnb_revenue = 0 AND spa_revenue = 0 AND total_room_revenue = 0 AND total_revenue = 0)
    )
);


-- ============================================
-- 5. COMPETITOR_RATES
-- Historical rates from rate shopper.
-- ============================================
CREATE TABLE competitor_rates (
    rate_id          SERIAL PRIMARY KEY,
    stay_date        DATE NOT NULL,
    hotel_name       VARCHAR(100) NOT NULL,
    hotel_star_rating INTEGER NOT NULL CHECK (hotel_star_rating BETWEEN 1 AND 5),
    channel          VARCHAR(50) NOT NULL CHECK (channel IN ('direct', 'booking_com', 'expedia')),
    room_type        VARCHAR(50) NOT NULL CHECK (room_type IN ('standard', 'superior', 'deluxe', 'suite')),
    rate_per_night   DECIMAL(10,2) NOT NULL CHECK (rate_per_night >= 0),

    CONSTRAINT uq_competitor_rate UNIQUE (stay_date, hotel_name, channel, room_type)
);


-- ============================================
-- 6. BUDGET_TARGETS
-- Monthly targets set by management.
-- ============================================
CREATE TABLE budget_targets (
    budget_id        SERIAL PRIMARY KEY,
    property_id      INTEGER NOT NULL REFERENCES property(property_id),
    month            DATE NOT NULL,
    target_occupancy DECIMAL(4,2) NOT NULL CHECK (target_occupancy BETWEEN 0 AND 1),
    target_adr       DECIMAL(10,2) NOT NULL CHECK (target_adr >= 0),
    target_fnb_revenue  DECIMAL(10,2) NOT NULL CHECK (target_fnb_revenue >= 0),
    target_spa_revenue  DECIMAL(10,2) NOT NULL CHECK (target_spa_revenue >= 0),

    CONSTRAINT chk_month_first_day CHECK (EXTRACT(DAY FROM month) = 1),
    CONSTRAINT uq_property_month UNIQUE (property_id, month)
);
