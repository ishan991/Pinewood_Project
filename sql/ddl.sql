CREATE SCHEMA IF NOT EXISTS pinewood;

SET search_path TO pinewood;


-- =========================================================
-- DIMENSION TABLES
-- =========================================================

-- Grain: One row per unique Pinewood community.
CREATE TABLE dim_community (
    community_key BIGINT PRIMARY KEY,
    community_id  VARCHAR(20) NOT NULL UNIQUE
);


-- Grain: One row per unique employee.
CREATE TABLE dim_employee (
    employee_key BIGINT PRIMARY KEY,
    employee_id  VARCHAR(30) NOT NULL UNIQUE,
    role         VARCHAR(100) NOT NULL
);


-- Grain: One row per unique resident.
CREATE TABLE dim_residents (
    resident_key BIGINT PRIMARY KEY,
    resident_id  VARCHAR(30) NOT NULL UNIQUE,
    first_name   VARCHAR(100),
    last_name    VARCHAR(100),
    dob          DATE,
    gender       VARCHAR(30)
);


-- Grain: One row per unique physical unit.
CREATE TABLE dim_unit (
    unit_key  BIGINT PRIMARY KEY,
    unit_id   VARCHAR(30) NOT NULL UNIQUE,
    unit_type VARCHAR(100)
);


-- Grain: One row per calendar date.
CREATE TABLE dim_date (
    date       DATE PRIMARY KEY,
    year       SMALLINT NOT NULL,
    month      SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name VARCHAR(20) NOT NULL,
    day        SMALLINT NOT NULL CHECK (day BETWEEN 1 AND 31)
);


-- Grain: One row per standardized care level.
CREATE TABLE dim_care_level (
    care_level VARCHAR(50) PRIMARY KEY
);


INSERT INTO dim_care_level (care_level)
VALUES
    ('Independent Living'),
    ('Assisted Living'),
    ('Memory Care');


-- =========================================================
-- FACT TABLES
-- =========================================================

-- Grain: One row per employee shift, identified by shift_id.
CREATE TABLE fact_adp_shifts (
    shift_id             VARCHAR(30) PRIMARY KEY,
    employee_key         BIGINT NOT NULL,
    community_key        BIGINT NOT NULL,
    shift_date           DATE NOT NULL,
    hours_worked         NUMERIC(8, 2) NOT NULL,
    standard_hourly_rate NUMERIC(10, 2) NOT NULL,
    total_labor_cost     NUMERIC(14, 2) NOT NULL,

    CONSTRAINT fk_shift_employee
        FOREIGN KEY (employee_key)
        REFERENCES dim_employee (employee_key),

    CONSTRAINT fk_shift_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_shift_date
        FOREIGN KEY (shift_date)
        REFERENCES dim_date (date)
);


-- Grain: One row per resident care-level change on a specific date.
CREATE TABLE fact_care_history (
    resident_key   BIGINT NOT NULL,
    change_date    DATE NOT NULL,
    previous_level VARCHAR(50),
    new_level      VARCHAR(50) NOT NULL,
    reason         VARCHAR(200) NOT NULL,

    CONSTRAINT pk_fact_care_history
        PRIMARY KEY (resident_key, change_date),

    CONSTRAINT fk_care_history_resident
        FOREIGN KEY (resident_key)
        REFERENCES dim_residents (resident_key),

    CONSTRAINT fk_care_history_date
        FOREIGN KEY (change_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_care_history_new_level
        FOREIGN KEY (new_level)
        REFERENCES dim_care_level (care_level)
);


-- Grain: One row per Google Business Profile review.
CREATE TABLE fact_gbp_reviews (
    review_id     VARCHAR(30) PRIMARY KEY,
    community_key BIGINT NOT NULL,
    review_date   DATE NOT NULL,
    rating        SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text   TEXT,
    response_text TEXT,
    responded_at  DATE,

    CONSTRAINT fk_review_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_review_date
        FOREIGN KEY (review_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_review_response_date
        FOREIGN KEY (responded_at)
        REFERENCES dim_date (date),

    CONSTRAINT chk_review_response_order
        CHECK (
            responded_at IS NULL
            OR responded_at >= review_date
        )
);


-- Grain: One row per lead record; intended as one row per unique lead_id, subject to the HL385264 duplication anomaly.
CREATE TABLE fact_hubspot_leads (
    lead_id       VARCHAR(30) NOT NULL,
    community_key BIGINT NOT NULL,
    lead_source   VARCHAR(100) NOT NULL,
    created_date  DATE NOT NULL,
    tour_date     DATE,
    deposit_date  DATE,
    move_in_date  DATE,
    status        VARCHAR(20) NOT NULL,
    lost_reason   VARCHAR(200),

    CONSTRAINT fk_lead_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_lead_created_date
        FOREIGN KEY (created_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_lead_tour_date
        FOREIGN KEY (tour_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_lead_deposit_date
        FOREIGN KEY (deposit_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_lead_move_in_date
        FOREIGN KEY (move_in_date)
        REFERENCES dim_date (date),

    CONSTRAINT chk_lead_status
        CHECK (status IN ('Won', 'Lost', 'Open')),

    CONSTRAINT chk_lead_tour_after_creation
        CHECK (
            tour_date IS NULL
            OR tour_date >= created_date
        ),

    CONSTRAINT chk_lead_deposit_after_creation
        CHECK (
            deposit_date IS NULL
            OR deposit_date >= created_date
        ),

    CONSTRAINT chk_lead_move_in_after_creation
        CHECK (
            move_in_date IS NULL
            OR move_in_date >= created_date
        )
);


-- Grain: One row per reported resident incident.
CREATE TABLE fact_incidents (
    incident_id   VARCHAR(30) PRIMARY KEY,
    resident_key  BIGINT NOT NULL,
    community_key BIGINT NOT NULL,
    incident_date DATE NOT NULL,
    incident_type VARCHAR(100) NOT NULL,
    severity      SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
    reported_by   VARCHAR(30) NOT NULL,

    CONSTRAINT fk_incident_resident
        FOREIGN KEY (resident_key)
        REFERENCES dim_residents (resident_key),

    CONSTRAINT fk_incident_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_incident_date
        FOREIGN KEY (incident_date)
        REFERENCES dim_date (date)
);


-- Grain: One row per resident lease for a unit.
CREATE TABLE fact_leases (
    lease_id        VARCHAR(30) PRIMARY KEY,
    resident_key    BIGINT NOT NULL,
    unit_key        BIGINT NOT NULL,
    community_key   BIGINT NOT NULL,
    move_in_date    DATE NOT NULL,
    move_out_date   DATE,
    move_out_reason VARCHAR(200),
    monthly_rate    NUMERIC(12, 2),

    CONSTRAINT fk_lease_resident
        FOREIGN KEY (resident_key)
        REFERENCES dim_residents (resident_key),

    CONSTRAINT fk_lease_unit
        FOREIGN KEY (unit_key)
        REFERENCES dim_unit (unit_key),

    CONSTRAINT fk_lease_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_lease_move_in_date
        FOREIGN KEY (move_in_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_lease_move_out_date
        FOREIGN KEY (move_out_date)
        REFERENCES dim_date (date),

    CONSTRAINT chk_lease_date_order
        CHECK (
            move_out_date IS NULL
            OR move_out_date >= move_in_date
        ),

    CONSTRAINT chk_lease_monthly_rate
        CHECK (
            monthly_rate IS NULL
            OR monthly_rate >= 0
        )
);


-- Grain: One row per resident, community, and monthly snapshot.
CREATE TABLE fact_residents (
    resident_key              BIGINT NOT NULL,
    community_key             BIGINT NOT NULL,
    admit_date                DATE NOT NULL,
    discharge_date            DATE,
    care_level                VARCHAR(50) NOT NULL,
    acuity_score              NUMERIC(8, 2),
    mobility_status           VARCHAR(100),
    status                    VARCHAR(50) NOT NULL,
    discharged_resident_count INTEGER NOT NULL DEFAULT 0,
    last_date                 DATE NOT NULL,

    CONSTRAINT pk_fact_residents
        PRIMARY KEY (resident_key, community_key, last_date),

    CONSTRAINT fk_fact_resident
        FOREIGN KEY (resident_key)
        REFERENCES dim_residents (resident_key),

    CONSTRAINT fk_resident_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_resident_care_level
        FOREIGN KEY (care_level)
        REFERENCES dim_care_level (care_level),

    CONSTRAINT fk_resident_admit_date
        FOREIGN KEY (admit_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_resident_discharge_date
        FOREIGN KEY (discharge_date)
        REFERENCES dim_date (date),

    CONSTRAINT fk_resident_snapshot_date
        FOREIGN KEY (last_date)
        REFERENCES dim_date (date),

    CONSTRAINT chk_resident_date_order
        CHECK (
            discharge_date IS NULL
            OR discharge_date >= admit_date
        ),

    CONSTRAINT chk_discharged_resident_count
        CHECK (discharged_resident_count IN (0, 1))
);


-- Grain: One row per unit, community, and monthly snapshot.
CREATE TABLE fact_units (
    unit_key      BIGINT NOT NULL,
    community_key BIGINT NOT NULL,
    unit_type     VARCHAR(100) NOT NULL,
    monthly_rent  NUMERIC(12, 2),
    snapshot_date DATE NOT NULL,

    CONSTRAINT pk_fact_units
        PRIMARY KEY (unit_key, community_key, snapshot_date),

    CONSTRAINT fk_fact_unit
        FOREIGN KEY (unit_key)
        REFERENCES dim_unit (unit_key),

    CONSTRAINT fk_unit_community
        FOREIGN KEY (community_key)
        REFERENCES dim_community (community_key),

    CONSTRAINT fk_unit_snapshot_date
        FOREIGN KEY (snapshot_date)
        REFERENCES dim_date (date),

    CONSTRAINT chk_unit_monthly_rent
        CHECK (
            monthly_rent IS NULL
            OR monthly_rent >= 0
        )
);


