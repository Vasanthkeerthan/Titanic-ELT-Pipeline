DROP TABLE IF EXISTS clean_passengers;

CREATE TABLE clean_passengers AS
WITH passengers_with_age_stats AS (
    SELECT
        stg_titanic.*,
        AVG(age) OVER (
            PARTITION BY passenger_class, sex
        ) AS class_sex_average_age,
        AVG(age) OVER () AS overall_average_age
    FROM stg_titanic
),
passengers_with_imputed_values AS (
    SELECT
        passengers_with_age_stats.*,
        CAST(
            COALESCE(age, class_sex_average_age, overall_average_age)
            AS DECIMAL(5, 2)
        ) AS imputed_age,
        COALESCE(
            embarked,
            (
                SELECT embarked
                FROM stg_titanic
                WHERE embarked IS NOT NULL
                GROUP BY embarked
                ORDER BY COUNT(*) DESC, embarked ASC
                LIMIT 1
            )
        ) AS imputed_embarked
    FROM passengers_with_age_stats
),
passengers_with_fare_quartile AS (
    SELECT
        passengers_with_imputed_values.*,
        NTILE(4) OVER (
            ORDER BY
                fare ASC,
                passenger_class ASC,
                sex ASC,
                survived ASC,
                age ASC,
                siblings_spouses_aboard ASC,
                parents_children_aboard ASC,
                embarked ASC,
                class_name ASC,
                passenger_type ASC,
                is_adult_male ASC,
                deck ASC,
                embark_town ASC,
                alive ASC,
                source_is_alone ASC
        ) AS fare_quartile
    FROM passengers_with_imputed_values
),
passengers_with_family_size AS (
    SELECT
        passengers_with_fare_quartile.*,
        siblings_spouses_aboard + parents_children_aboard + 1 AS family_size
    FROM passengers_with_fare_quartile
)
SELECT
    survived,
    passenger_class,
    CAST(
        CASE sex
            WHEN 'male' THEN 0
            WHEN 'female' THEN 1
            ELSE NULL
        END
        AS UNSIGNED
    ) AS sex,
    imputed_age AS age,
    siblings_spouses_aboard,
    parents_children_aboard,
    fare,
    imputed_embarked AS embarked,
    class_name,
    passenger_type,
    is_adult_male,
    alive,
    source_is_alone,
    CASE
        WHEN imputed_age >= 0 AND imputed_age < 13 THEN 'Child'
        WHEN imputed_age >= 13 AND imputed_age < 20 THEN 'Teen'
        WHEN imputed_age >= 20 AND imputed_age < 60 THEN 'Adult'
        WHEN imputed_age >= 60 THEN 'Senior'
        ELSE NULL
    END AS age_group,
    family_size,
    CASE WHEN family_size = 1 THEN 1 ELSE 0 END AS is_alone,
    CASE fare_quartile
        WHEN 1 THEN 'Low'
        WHEN 2 THEN 'Medium'
        WHEN 3 THEN 'High'
        WHEN 4 THEN 'Premium'
        ELSE NULL
    END AS fare_category,
    load_timestamp,
    batch_id
FROM passengers_with_family_size;
