# Data quality and SQL verification

The pipeline records six checks per batch in `dq_results`. The runner creates a UUID `batch_id`, passes it to `sql/04_data_quality.sql`, fetches the results for that run, and exits nonzero if a check is missing, invalid, duplicated, or failed.

| Check | Rule |
|---|---|
| `raw_count_equals_clean_count` | Raw and clean rows for this batch have equal counts. |
| `no_null_age` | No clean row for this batch has a NULL age after SQL imputation. |
| `no_null_embarked` | No clean row for this batch has a NULL embarked value after SQL imputation. |
| `no_duplicate_passengers` | No all-15-column raw source profile occurs more than once in this batch. This does not establish passenger identity. |
| `age_between_0_and_100` | No non-NULL clean age is below 0 or above 100. NULLs are checked separately by `no_null_age`. |
| `sex_encoded_only_0_or_1` | Every clean sex value is 0 or 1, with NULL treated as a failure. |

## Run-scoped results

Get the latest recorded batch IDs, then substitute one UUID below:

```sql
SELECT batch_id, MAX(checked_at) AS latest_check
FROM dq_results
GROUP BY batch_id
ORDER BY latest_check DESC
LIMIT 5;

SELECT check_name, status, checked_at
FROM dq_results
WHERE batch_id = 'paste-a-batch-uuid-here'
ORDER BY check_name;
```

## Verification queries

### Row and column counts

```sql
SELECT 'raw_titanic' AS object_name, COUNT(*) AS row_count
FROM raw_titanic
UNION ALL
SELECT 'stg_titanic', COUNT(*) FROM stg_titanic
UNION ALL
SELECT 'clean_passengers', COUNT(*) FROM clean_passengers;

SELECT TABLE_NAME, COUNT(*) AS column_count
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('raw_titanic', 'stg_titanic', 'clean_passengers')
GROUP BY TABLE_NAME
ORDER BY TABLE_NAME;
```

The expected raw schema has 17 columns: the 15 source columns and two load metadata columns. The SQL-created staging and clean schemas have 17 and 19 columns respectively. Inspect their definitions with:

```sql
SHOW COLUMNS FROM raw_titanic;
SHOW COLUMNS FROM stg_titanic;
SHOW COLUMNS FROM clean_passengers;
```

### NULLs in raw source columns

```sql
SELECT
    SUM(survived IS NULL) AS survived_nulls,
    SUM(pclass IS NULL) AS pclass_nulls,
    SUM(sex IS NULL) AS sex_nulls,
    SUM(age IS NULL) AS age_nulls,
    SUM(sibsp IS NULL) AS sibsp_nulls,
    SUM(parch IS NULL) AS parch_nulls,
    SUM(fare IS NULL) AS fare_nulls,
    SUM(embarked IS NULL) AS embarked_nulls,
    SUM(`class` IS NULL) AS class_nulls,
    SUM(who IS NULL) AS who_nulls,
    SUM(adult_male IS NULL) AS adult_male_nulls,
    SUM(deck IS NULL) AS deck_nulls,
    SUM(embark_town IS NULL) AS embark_town_nulls,
    SUM(alive IS NULL) AS alive_nulls,
    SUM(alone IS NULL) AS alone_nulls
FROM raw_titanic;
```

### Duplicate source profiles

This matches the pipeline's duplicate-profile definition. It does not claim that repeated profiles are duplicate people.

```sql
SELECT COUNT(*) AS repeated_profile_groups
FROM (
    SELECT survived, pclass, sex, age, sibsp, parch, fare, embarked,
           `class`, who, adult_male, deck, embark_town, alive, alone
    FROM raw_titanic
    GROUP BY survived, pclass, sex, age, sibsp, parch, fare, embarked,
             `class`, who, adult_male, deck, embark_town, alive, alone
    HAVING COUNT(*) > 1
) AS duplicate_profiles;
```

### Raw-to-clean count and batch lineage

```sql
SELECT
    r.batch_id,
    r.raw_rows,
    COALESCE(c.clean_rows, 0) AS clean_rows
FROM (
    SELECT batch_id, COUNT(*) AS raw_rows
    FROM raw_titanic
    GROUP BY batch_id
) AS r
LEFT JOIN (
    SELECT batch_id, COUNT(*) AS clean_rows
    FROM clean_passengers
    GROUP BY batch_id
) AS c ON c.batch_id = r.batch_id;
```

For exact row counts by batch, use:

```sql
SELECT batch_id, COUNT(*) AS raw_rows
FROM raw_titanic
GROUP BY batch_id;

SELECT batch_id, COUNT(*) AS clean_rows
FROM clean_passengers
GROUP BY batch_id;
```

## Interpretation notes

- `raw_titanic` is replaced on each successful load; its batch ID identifies that snapshot. `dq_results` is append-only across runs.
- SQL `GROUP BY` groups NULL source values together for the duplicate-profile check.
- There is no unique passenger key in the source. Do not equate equal profiles with confirmed duplicate passengers.
- Analytics are views over `clean_passengers`; they are not persisted final aggregate tables.
