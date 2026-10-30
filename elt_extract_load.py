from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import seaborn as sns
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


EXPECTED_COLUMNS = (
    "survived",
    "pclass",
    "sex",
    "age",
    "sibsp",
    "parch",
    "fare",
    "embarked",
    "class",
    "who",
    "adult_male",
    "deck",
    "embark_town",
    "alive",
    "alone",
)
EXPECTED_ROWS = 891


def extract_and_load_raw(engine: Engine, batch_id: str) -> int:
    try:
        UUID(batch_id)
    except ValueError as exc:
        raise ValueError("batch_id must be a valid UUID.") from exc

    try:
        data = sns.load_dataset("titanic")
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            "Could not load the Seaborn Titanic dataset. Check the internet "
            "connection and try again."
        ) from exc

    if tuple(data.columns) != EXPECTED_COLUMNS:
        raise RuntimeError(
            "The Seaborn Titanic dataset did not contain the expected 15 "
            "original columns; refusing to load a changed source schema."
        )
    if len(data) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_ROWS} Titanic rows, but extracted {len(data)}."
        )

    data["load_timestamp"] = datetime.now(timezone.utc).replace(tzinfo=None)
    data["batch_id"] = batch_id

    suffix = batch_id.replace("-", "")
    staging_table = f"raw_titanic_load_{suffix}"
    backup_table = f"raw_titanic_previous_{suffix}"
    raw_replaced = False

    try:
        data.to_sql(
            staging_table,
            con=engine,
            if_exists="fail",
            index=False,
            chunksize=500,
            method="multi",
        )
        with engine.connect() as connection:
            loaded_rows = connection.execute(
                text(f"SELECT COUNT(*) FROM `{staging_table}`")
            ).scalar_one()
            loaded_columns = connection.execute(
                text(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name"
                ),
                {"table_name": staging_table},
            ).scalar_one()

        if loaded_rows != EXPECTED_ROWS or loaded_columns != len(EXPECTED_COLUMNS) + 2:
            raise RuntimeError(
                "The raw staging table did not contain the expected 891 rows "
                "and 17 columns; raw_titanic was not replaced."
            )

        with engine.begin() as connection:
            raw_exists = connection.execute(
                text(
                    "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_titanic'"
                )
            ).first()
            if raw_exists:
                connection.exec_driver_sql(
                    f"RENAME TABLE `raw_titanic` TO `{backup_table}`, "
                    f"`{staging_table}` TO `raw_titanic`"
                )
            else:
                connection.exec_driver_sql(
                    f"RENAME TABLE `{staging_table}` TO `raw_titanic`"
                )
            raw_replaced = True

        if raw_exists:
            with engine.begin() as connection:
                connection.exec_driver_sql(f"DROP TABLE `{backup_table}`")

        print(
            f"Loaded {loaded_rows} original rows and 17 columns into "
            f"'raw_titanic' (batch {batch_id})."
        )
        return int(loaded_rows)
    except (SQLAlchemyError, RuntimeError) as exc:
        if raw_replaced:
            message = (
                "The raw_titanic refresh was committed, but a follow-up "
                "operation failed."
            )
        else:
            message = (
                "Could not load the raw Titanic dataset; the existing "
                "raw_titanic table was left unchanged."
            )
        raise RuntimeError(f"{message} {exc}") from exc
    finally:
        if not raw_replaced:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    f"DROP TABLE IF EXISTS `{staging_table}`"
                )
