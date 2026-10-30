from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config import create_db_engine
from elt_extract_load import extract_and_load_raw


CHECK_NAMES = (
    "raw_count_equals_clean_count",
    "no_null_age",
    "no_null_embarked",
    "no_duplicate_passengers",
    "age_between_0_and_100",
    "sex_encoded_only_0_or_1",
)
SQL_FILES = (
    "01_staging.sql",
    "02_transform.sql",
    "03_analytics.sql",
    "04_data_quality.sql",
)


def split_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    start = 0
    index = 0
    quote: str | None = None
    line_comment = False
    block_comment = False

    while index < len(script):
        character = script[index]
        following = script[index + 1] if index + 1 < len(script) else ""

        if line_comment:
            if character in "\r\n":
                line_comment = False
        elif block_comment:
            if character == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote is not None:
            if character == "\\" and quote != "`":
                index += 1
            elif character == quote:
                if following == quote:
                    index += 1
                else:
                    quote = None
        elif character in ("'", '"', "`"):
            quote = character
        elif character == "#":
            line_comment = True
        elif character == "-" and following == "-" and (
            index + 2 == len(script) or script[index + 2].isspace()
        ):
            line_comment = True
            index += 1
        elif character == "/" and following == "*":
            block_comment = True
            index += 1
        elif character == ";":
            statement = script[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1
        index += 1

    if quote is not None:
        raise ValueError("SQL script contains an unterminated quoted value.")
    if block_comment:
        raise ValueError("SQL script contains an unterminated block comment.")

    remaining = script[start:].strip()
    if remaining:
        statements.append(remaining)
    return statements


def run_sql_file(
    engine: Engine,
    file_path: Path,
    parameters: dict[str, str] | None = None,
) -> None:
    if not file_path.is_file():
        raise FileNotFoundError(f"Required SQL file does not exist: {file_path}")

    statements = split_sql_statements(file_path.read_text(encoding="utf-8"))
    if not statements:
        raise RuntimeError(f"SQL file is empty: {file_path.name}")

    try:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement), parameters or {})
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed while executing {file_path.name}: {exc}") from exc


def ensure_dq_batch_column(engine: Engine) -> None:
    with engine.begin() as connection:
        columns = {
            row.column_name
            for row in connection.execute(
                text(
                    "SELECT COLUMN_NAME AS column_name "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'dq_results'"
                )
            )
        }
        if columns and "batch_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE dq_results ADD COLUMN batch_id CHAR(36) NULL"
            )


def fetch_current_checks(engine: Engine, batch_id: str) -> dict[str, str]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT check_name, status FROM dq_results "
                "WHERE batch_id = :batch_id"
            ),
            {"batch_id": batch_id},
        ).all()

    results: dict[str, str] = {}
    for check_name, status in rows:
        if check_name in results:
            raise RuntimeError(
                f"Data-quality check '{check_name}' was recorded more than once "
                f"for batch {batch_id}."
            )
        results[check_name] = status
    return results


def print_check_results(results: dict[str, str]) -> bool:
    all_passed = True
    for check_name in CHECK_NAMES:
        status = results.get(check_name)
        passed = status == "PASS"
        all_passed = all_passed and passed
        label = "PASS" if passed else "FAIL"
        detail = "" if status in {"PASS", "FAIL"} else " (missing or invalid result)"
        print(f"[{label}] {check_name}{detail}")

    unexpected = set(results) - set(CHECK_NAMES)
    for check_name in sorted(unexpected):
        print(f"[FAIL] Unexpected data-quality check: {check_name}")
        all_passed = False
    return all_passed


def run_pipeline() -> bool:
    batch_id = str(uuid4())
    engine = create_db_engine()
    try:
        print(f"Starting Titanic ELT pipeline (batch {batch_id})")
        extract_and_load_raw(engine, batch_id)

        sql_directory = Path(__file__).resolve().parent / "sql"
        for file_name in SQL_FILES:
            if file_name == "04_data_quality.sql":
                ensure_dq_batch_column(engine)
            run_sql_file(
                engine,
                sql_directory / file_name,
                {"batch_id": batch_id},
            )
            print(f"Executed sql\\{file_name}")

        results = fetch_current_checks(engine, batch_id)
        if len(results) != len(CHECK_NAMES):
            print(
                f"Expected {len(CHECK_NAMES)} current-run checks, "
                f"found {len(results)}."
            )
        all_passed = print_check_results(results)
        if len(results) != len(CHECK_NAMES):
            all_passed = False

        if all_passed:
            print("ELT pipeline completed successfully.")
        else:
            print("ELT pipeline failed: one or more quality checks failed.")
        return all_passed
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        successful = run_pipeline()
    except (FileNotFoundError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        print(f"ELT pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if successful else 1)
