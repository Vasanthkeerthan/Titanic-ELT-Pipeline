# Titanic ELT pipeline

This project is the independent ELT implementation. It does not modify the
completed ETL project or write to the ETL `passengers` table. It uses the same
MySQL environment variable names and driver configuration.

## Project layout

```text
ELT/
  .venv/
  .vscode/settings.json
  sql/
    01_staging.sql
    02_transform.sql
    03_analytics.sql
    04_data_quality.sql
  .env
  .env.example
  .gitignore
  config.py
  elt_extract_load.py
  run_elt.py
  requirements.txt
  README_ELT.md
```

`.venv` is retained and hidden from the VS Code Explorer and search results.
Secrets in `.env`, virtual-environment files, Python caches, and generated
temporary files are ignored by Git.

## ETL and ELT

- **ETL** transforms data in Python before loading it to the destination.
- **ELT** loads source rows unchanged first, then performs staging, cleaning,
  feature engineering, analytics, and quality checks in SQL.

Python is used here only to extract the Seaborn dataset, add load metadata,
load the raw table, execute SQL scripts, and print SQL-computed check results.

## Layers

- `raw_titanic`: all 15 original source columns and only two metadata columns,
  `load_timestamp` and `batch_id` (17 columns total). Original NULLs are kept.
- `stg_titanic`: typed, snake_case source columns with normalized text and
  metadata retained for traceability.
- `clean_passengers`: SQL age and embarked imputation, encoded sex, age group,
  family size, alone indicator, and fare category. `deck` and `embark_town` are
  excluded.
- `vw_survival_by_class_sex`, `vw_survival_by_age_group`, and
  `vw_top3_fares_per_class`: SQL analytics views over clean passengers.
- `dq_results`: append-only current-run results with batch ID, check name,
  status, and timestamp.

### Safe raw refresh

Each run loads all source rows into a unique temporary table, then verifies
that it contains 891 rows and 17 columns. A single MySQL `RENAME TABLE`
statement atomically swaps the staged table into `raw_titanic`. A failed
extraction or pre-swap load leaves any existing raw table untouched. Repeated
runs replace the raw table instead of appending. No transformation writes to
the raw table.

## Transform rules

- Missing age is imputed with the mean for `passenger_class` and `sex`, with
  the overall non-NULL mean as a fallback.
- Missing embarked values use the most common non-NULL port; ties are broken
  alphabetically.
- `sex` is encoded male = 0 and female = 1.
- Age groups use 0–12 Child, 13–19 Teen, 20–59 Adult, and 60+ Senior.
- Family size is siblings/spouses + parents/children + 1; `is_alone` is 1 only
  for family size 1.
- Fare bands use `NTILE(4)` ordered by fare and then source business columns.
  Identical records have no source identifier to distinguish them; when an
  exact tie intersects an NTILE boundary, MySQL can assign identical records
  to adjacent bands. No artificial passenger identifier is added.
- The top-fares view uses `RANK()`, so ties at rank 3 may produce more than
  three rows per class.

## Duplicate check definition and limitation

`no_duplicate_passengers` is a record-profile check, not proof of passenger
identity. It groups raw rows by all 15 original business columns, excluding
only `load_timestamp` and `batch_id`. MySQL `GROUP BY` treats NULLs as equal
within a group, so repeated profiles containing missing values are counted.
The check passes only when no profile occurs more than once.

The Seaborn Titanic table has no unique passenger identifier. Therefore,
identical profiles may be legitimate different passengers or duplicated
records; SQL cannot establish which. This pipeline preserves every source row
and honestly reports `FAIL` if repeated profiles exist. It does not invent an
identity or remove rows to force a pass. Row-count equality is a separate
check, `raw_count_equals_clean_count`.

## Configure and run in Windows PowerShell

The project reads `DB_HOST`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` from its
local `.env`. For a separate setup, create it from the example and fill it in
locally; do not commit it:

```powershell
Set-Location "C:\Users\CH VASANTH KEERTHAN\OneDrive\Desktop\ELT"
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\run_elt.py
```

If dependencies are already installed in `.venv`, skip the install command.
The configured MySQL account must be able to create the database if needed,
create/replace `raw_titanic`, create staging/clean tables and views, and write
to `dq_results`. Credentials are never printed.

The runner executes extraction/loading, then the four SQL files in order. It
prints exactly six current-run checks as `[PASS]` or `[FAIL]`. Missing or
failed checks yield a nonzero process exit status. Previous check rows remain
in `dq_results`.

## Verify in MySQL Workbench

```sql
SHOW TABLES;

SHOW COLUMNS FROM raw_titanic;
SELECT COUNT(*) AS raw_rows FROM raw_titanic;
SELECT * FROM raw_titanic LIMIT 10;

SHOW COLUMNS FROM stg_titanic;
SELECT COUNT(*) AS staging_rows FROM stg_titanic;

SHOW COLUMNS FROM clean_passengers;
SELECT COUNT(*) AS clean_rows FROM clean_passengers;
SELECT * FROM clean_passengers LIMIT 10;

SHOW FULL TABLES WHERE Table_type = 'VIEW';
SELECT * FROM vw_survival_by_class_sex ORDER BY passenger_class, sex;
SELECT * FROM vw_survival_by_age_group ORDER BY age_group;
SELECT * FROM vw_top3_fares_per_class
ORDER BY passenger_class, fare_rank, fare DESC;

SELECT batch_id, check_name, status, checked_at
FROM dq_results
ORDER BY checked_at DESC
LIMIT 18;
```

For one run, use its UUID shown by the runner:

```sql
SELECT check_name, status, checked_at
FROM dq_results
WHERE batch_id = 'paste-the-run-uuid-here'
ORDER BY check_name;
```
