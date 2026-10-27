-- mart.dim_date: one row per calendar day (smart key YYYYMMDD), static.
-- Carries the DST attributes that distinguish days; the UTC/local distinction
-- itself lives in the fact keys (date_sk_utc, date_sk_local), not here, because a
-- calendar day holds the same date in both zones (DESIGN.md 5.2, PLANNING_LOG 2026-10-27).

CREATE TABLE IF NOT EXISTS mart.dim_date (
    date_sk                  INTEGER PRIMARY KEY,           -- YYYYMMDD
    full_date                DATE        NOT NULL UNIQUE,
    day_of_month             SMALLINT    NOT NULL,
    day_of_week_num          SMALLINT    NOT NULL CHECK (day_of_week_num BETWEEN 1 AND 7),
    day_name_en              VARCHAR(10) NOT NULL,
    day_name_hu              VARCHAR(10) NOT NULL,
    iso_week_year            SMALLINT    NOT NULL,
    week_of_year             SMALLINT    NOT NULL,
    month_num                SMALLINT    NOT NULL,
    month_name_en            VARCHAR(10) NOT NULL,
    month_name_hu            VARCHAR(12) NOT NULL,
    quarter                  SMALLINT    NOT NULL,
    year                     SMALLINT    NOT NULL,
    is_weekend               BOOLEAN     NOT NULL,
    is_holiday_hu            BOOLEAN     NOT NULL,
    season                   VARCHAR(10) NOT NULL,
    is_dst_local             BOOLEAN     NOT NULL,
    utc_offset_minutes_local SMALLINT    NOT NULL,
    is_dst_switch_day        BOOLEAN     NOT NULL
);

-- Gregorian Easter Sunday (Anonymous Gregorian algorithm), used for the movable
-- Hungarian public holidays.
CREATE OR REPLACE FUNCTION mart.easter_sunday(p_year int)
RETURNS date LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    a int; b int; c int; d int; e int; f int; g int;
    h int; i int; k int; l int; m int; mo int; da int;
BEGIN
    a := p_year % 19;
    b := p_year / 100;
    c := p_year % 100;
    d := b / 4;
    e := b % 4;
    f := (b + 8) / 25;
    g := (b - f + 1) / 3;
    h := (19 * a + b - d - g + 15) % 30;
    i := c / 4;
    k := c % 4;
    l := (32 + 2 * e + 2 * i - h - k) % 7;
    m := (a + 11 * h + 22 * l) / 451;
    mo := (h + l - 7 * m + 114) / 31;
    da := ((h + l - 7 * m + 114) % 31) + 1;
    RETURN make_date(p_year, mo, da);
END;
$$;

-- Europe/Budapest UTC offset in minutes at local noon of the given day
-- (60 in winter / CET, 120 in summer / CEST).
CREATE OR REPLACE FUNCTION mart.budapest_offset_minutes(p_day date)
RETURNS int LANGUAGE sql STABLE AS $$
    SELECT (EXTRACT(EPOCH FROM (
        (p_day + time '12:00')
        - ((p_day + time '12:00') AT TIME ZONE 'Europe/Budapest' AT TIME ZONE 'UTC')
    )) / 60)::int;
$$;

CREATE OR REPLACE FUNCTION mart.is_hungarian_holiday(p_day date)
RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT
        to_char(p_day, 'MM-DD') IN
            ('01-01','03-15','05-01','08-20','10-23','11-01','12-25','12-26')
        OR (to_char(p_day, 'MM-DD') = '12-24' AND EXTRACT(year FROM p_day) >= 2024)
        OR p_day = mart.easter_sunday(EXTRACT(year FROM p_day)::int) - 2   -- Good Friday
        OR p_day = mart.easter_sunday(EXTRACT(year FROM p_day)::int)       -- Easter Sunday
        OR p_day = mart.easter_sunday(EXTRACT(year FROM p_day)::int) + 1   -- Easter Monday
        OR p_day = mart.easter_sunday(EXTRACT(year FROM p_day)::int) + 49  -- Whit Sunday
        OR p_day = mart.easter_sunday(EXTRACT(year FROM p_day)::int) + 50; -- Whit Monday
$$;

-- Generates the calendar once; safe to re-run (ON CONFLICT DO NOTHING).
CREATE OR REPLACE FUNCTION mart.load_dim_date(
    p_from date DEFAULT '2020-01-01',
    p_to   date DEFAULT '2035-12-31'
)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_count bigint;
BEGIN
    INSERT INTO mart.dim_date (
        date_sk, full_date, day_of_month, day_of_week_num, day_name_en, day_name_hu,
        iso_week_year, week_of_year, month_num, month_name_en, month_name_hu,
        quarter, year, is_weekend, is_holiday_hu, season,
        is_dst_local, utc_offset_minutes_local, is_dst_switch_day
    )
    SELECT
        to_char(d, 'YYYYMMDD')::int,
        d::date,
        EXTRACT(day     FROM d)::smallint,
        EXTRACT(isodow  FROM d)::smallint,
        trim(to_char(d, 'Day')),
        (ARRAY['Hétfő','Kedd','Szerda','Csütörtök','Péntek','Szombat','Vasárnap'])
            [EXTRACT(isodow FROM d)::int],
        EXTRACT(isoyear FROM d)::smallint,
        EXTRACT(week    FROM d)::smallint,
        EXTRACT(month   FROM d)::smallint,
        trim(to_char(d, 'Month')),
        (ARRAY['Január','Február','Március','Április','Május','Június',
               'Július','Augusztus','Szeptember','Október','November','December'])
            [EXTRACT(month FROM d)::int],
        EXTRACT(quarter FROM d)::smallint,
        EXTRACT(year    FROM d)::smallint,
        EXTRACT(isodow  FROM d) IN (6, 7),
        mart.is_hungarian_holiday(d::date),
        CASE EXTRACT(month FROM d)::int
            WHEN 12 THEN 'winter' WHEN 1 THEN 'winter' WHEN 2 THEN 'winter'
            WHEN 3  THEN 'spring' WHEN 4 THEN 'spring' WHEN 5 THEN 'spring'
            WHEN 6  THEN 'summer' WHEN 7 THEN 'summer' WHEN 8 THEN 'summer'
            ELSE 'autumn'
        END,
        mart.budapest_offset_minutes(d::date) = 120,
        mart.budapest_offset_minutes(d::date),
        mart.budapest_offset_minutes(d::date) <> mart.budapest_offset_minutes((d - interval '1 day')::date)
    FROM generate_series(p_from::timestamp, p_to::timestamp, interval '1 day') AS g(d)
    ON CONFLICT (date_sk) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;
