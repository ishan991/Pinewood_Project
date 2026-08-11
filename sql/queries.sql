-- =========================================================
-- Pinewood Project: Business Analysis Queries
-- =========================================================
-- 1. Monthly occupancy rate by community
-- 2. Top three move-out reasons by community for Jan-Jun 2025
-- 3. Incident rate per 100 resident-days by community and care level

-- =========================================================

SET search_path TO pinewood;


-- =========================================================
-- 1. Monthly occupancy rate by community
-- =========================================================
-- A unit is occupied when at least one lease is active on the unit
-- snapshot date. DISTINCT prevents overlapping leases from counting
-- the same occupied unit more than once.

SELECT
    c.community_id,
    u.snapshot_date,
    COUNT(DISTINCT u.unit_key) AS total_units,
    COUNT(DISTINCT l.unit_key) AS occupied_units,
    ROUND(
        COUNT(DISTINCT l.unit_key) * 100.0
        / NULLIF(COUNT(DISTINCT u.unit_key), 0),
        2
    ) AS occupancy_rate_percent
FROM fact_units AS u
JOIN dim_community AS c
    ON c.community_key = u.community_key
LEFT JOIN fact_leases AS l
    ON l.unit_key = u.unit_key
    AND l.community_key = u.community_key
    AND l.move_in_date <= u.snapshot_date
    AND (
        l.move_out_date IS NULL
        OR l.move_out_date >= u.snapshot_date
    )
GROUP BY
    c.community_id,
    u.snapshot_date
ORDER BY
    u.snapshot_date,
    c.community_id;


-- =========================================================
-- 2. Top three move-out reasons by community
-- =========================================================
-- The percentage is calculated against all move-outs in the same
-- community during the six-month dataset period. Ranking is applied
-- only after every reason has contributed to the community total.

WITH ranked_reasons AS (
    SELECT
        l.community_key,
        l.move_out_reason,
        COUNT(DISTINCT l.lease_id) AS move_outs,
        ROUND(
            COUNT(DISTINCT l.lease_id) * 100.0
            / SUM(COUNT(DISTINCT l.lease_id)) OVER (
                PARTITION BY l.community_key
            ),
            2
        ) AS move_out_percentage,
        ROW_NUMBER() OVER (
            PARTITION BY l.community_key
            ORDER BY
                COUNT(DISTINCT l.lease_id) DESC,
                l.move_out_reason
        ) AS reason_rank
    FROM fact_leases AS l
    WHERE l.move_out_date >= DATE '2025-01-01'
      AND l.move_out_date < DATE '2025-07-01'
      AND l.move_out_reason IS NOT NULL
      AND l.move_out_reason <> 'N/A'
    GROUP BY
        l.community_key,
        l.move_out_reason
)

SELECT
    c.community_id,
    r.move_out_reason,
    r.move_outs,
    r.move_out_percentage
FROM ranked_reasons AS r
JOIN dim_community AS c
    ON c.community_key = r.community_key
WHERE r.reason_rank <= 3
ORDER BY
    c.community_id,
    r.reason_rank;


-- =========================================================
-- 3. Incident rate per 100 resident-days by community and care level
-- =========================================================
-- Resident-days equal the distinct active-resident census for each
-- monthly snapshot multiplied by the number of days in that month.
-- Each incident receives the resident's care level from the matching
-- resident snapshot month.

WITH monthly_resident_days AS (
    SELECT
        community_key,
        care_level,
        last_date,
        COUNT(DISTINCT resident_key)
            * EXTRACT(DAY FROM last_date) AS resident_days
    FROM fact_residents
    WHERE status = 'Active'
    GROUP BY
        community_key,
        care_level,
        last_date
),

resident_days AS (
    SELECT
        community_key,
        care_level,
        SUM(resident_days) AS total_resident_days
    FROM monthly_resident_days
    GROUP BY
        community_key,
        care_level
),

incidents AS (
    SELECT
        i.community_key,
        r.care_level,
        COUNT(DISTINCT i.incident_id) AS total_incidents
    FROM fact_incidents AS i
    JOIN fact_residents AS r
        ON r.resident_key = i.resident_key
        AND r.community_key = i.community_key
        AND DATE_TRUNC('month', i.incident_date)
            = DATE_TRUNC('month', r.last_date)
    GROUP BY
        i.community_key,
        r.care_level
)

SELECT
    c.community_id,
    rd.care_level,
    COALESCE(i.total_incidents, 0) AS total_incidents,
    rd.total_resident_days,
    ROUND(
        COALESCE(i.total_incidents, 0) * 100.0
        / NULLIF(rd.total_resident_days, 0),
        2
    ) AS incidents_per_100_resident_days
FROM resident_days AS rd
JOIN dim_community AS c
    ON c.community_key = rd.community_key
LEFT JOIN incidents AS i
    ON i.community_key = rd.community_key
    AND i.care_level = rd.care_level
ORDER BY
    c.community_id,
    rd.care_level;
