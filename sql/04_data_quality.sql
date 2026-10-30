CREATE TABLE IF NOT EXISTS dq_results (
    result_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    batch_id CHAR(36) NULL,
    check_name VARCHAR(100) NOT NULL,
    status VARCHAR(4) NOT NULL,
    checked_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (result_id),
    INDEX idx_dq_results_batch_id (batch_id)
);

INSERT INTO dq_results (batch_id, check_name, status, checked_at)
SELECT
    :batch_id,
    'raw_count_equals_clean_count',
    IF(
        (SELECT COUNT(*) FROM raw_titanic WHERE batch_id = :batch_id) =
        (SELECT COUNT(*) FROM clean_passengers WHERE batch_id = :batch_id),
        'PASS',
        'FAIL'
    ),
    CURRENT_TIMESTAMP(6)
UNION ALL
SELECT
    :batch_id,
    'no_null_age',
    IF(
        NOT EXISTS (
            SELECT 1
            FROM clean_passengers
            WHERE batch_id = :batch_id AND age IS NULL
        ),
        'PASS',
        'FAIL'
    ),
    CURRENT_TIMESTAMP(6)
UNION ALL
SELECT
    :batch_id,
    'no_null_embarked',
    IF(
        NOT EXISTS (
            SELECT 1
            FROM clean_passengers
            WHERE batch_id = :batch_id AND embarked IS NULL
        ),
        'PASS',
        'FAIL'
    ),
    CURRENT_TIMESTAMP(6)
UNION ALL
SELECT
    :batch_id,
    'no_duplicate_passengers',
    IF(
        NOT EXISTS (
            SELECT 1
            FROM raw_titanic
            WHERE batch_id = :batch_id
            GROUP BY
                survived,
                pclass,
                sex,
                age,
                sibsp,
                parch,
                fare,
                embarked,
                `class`,
                who,
                adult_male,
                deck,
                embark_town,
                alive,
                alone
            HAVING COUNT(*) > 1
        ),
        'PASS',
        'FAIL'
    ),
    CURRENT_TIMESTAMP(6)
UNION ALL
SELECT
    :batch_id,
    'age_between_0_and_100',
    IF(
        NOT EXISTS (
            SELECT 1
            FROM clean_passengers
            WHERE batch_id = :batch_id AND (age < 0 OR age > 100)
        ),
        'PASS',
        'FAIL'
    ),
    CURRENT_TIMESTAMP(6)
UNION ALL
SELECT
    :batch_id,
    'sex_encoded_only_0_or_1',
    IF(
        NOT EXISTS (
            SELECT 1
            FROM clean_passengers
            WHERE batch_id = :batch_id
              AND (sex IS NULL OR sex NOT IN (0, 1))
        ),
        'PASS',
        'FAIL'
    ),
    CURRENT_TIMESTAMP(6);
