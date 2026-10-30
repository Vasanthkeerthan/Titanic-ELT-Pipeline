DROP TABLE IF EXISTS stg_titanic;

CREATE TABLE stg_titanic AS
SELECT
    CAST(survived AS UNSIGNED) AS survived,
    CAST(pclass AS UNSIGNED) AS passenger_class,
    LOWER(TRIM(sex)) AS sex,
    CAST(age AS DECIMAL(5, 2)) AS age,
    CAST(sibsp AS UNSIGNED) AS siblings_spouses_aboard,
    CAST(parch AS UNSIGNED) AS parents_children_aboard,
    CAST(fare AS DECIMAL(10, 4)) AS fare,
    LOWER(TRIM(embarked)) AS embarked,
    LOWER(TRIM(`class`)) AS class_name,
    LOWER(TRIM(who)) AS passenger_type,
    CAST(adult_male AS UNSIGNED) AS is_adult_male,
    LOWER(TRIM(deck)) AS deck,
    LOWER(TRIM(embark_town)) AS embark_town,
    LOWER(TRIM(alive)) AS alive,
    CAST(alone AS UNSIGNED) AS source_is_alone,
    load_timestamp,
    batch_id
FROM raw_titanic;
