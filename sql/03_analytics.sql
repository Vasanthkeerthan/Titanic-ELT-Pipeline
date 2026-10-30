CREATE OR REPLACE VIEW vw_survival_by_class_sex AS
SELECT
    passenger_class,
    sex,
    COUNT(*) AS total_passengers,
    SUM(CASE WHEN survived = 1 THEN 1 ELSE 0 END) AS number_survived,
    ROUND(
        100.0 * SUM(CASE WHEN survived = 1 THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS survival_rate_percent
FROM clean_passengers
GROUP BY passenger_class, sex;

CREATE OR REPLACE VIEW vw_survival_by_age_group AS
SELECT
    age_group,
    COUNT(*) AS total_passengers,
    SUM(CASE WHEN survived = 1 THEN 1 ELSE 0 END) AS number_survived,
    ROUND(
        100.0 * SUM(CASE WHEN survived = 1 THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS survival_rate_percent
FROM clean_passengers
GROUP BY age_group;

CREATE OR REPLACE VIEW vw_top3_fares_per_class AS
SELECT
    passenger_class,
    fare,
    survived,
    sex,
    fare_rank
FROM (
    SELECT
        passenger_class,
        fare,
        survived,
        sex,
        RANK() OVER (
            PARTITION BY passenger_class
            ORDER BY fare DESC
        ) AS fare_rank
    FROM clean_passengers
) AS ranked_fares
WHERE fare_rank <= 3;
