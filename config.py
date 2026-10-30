import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


load_dotenv(Path(__file__).resolve().with_name(".env"))


def create_db_engine() -> Engine:
    settings = {
        "DB_HOST": os.environ.get("DB_HOST", ""),
        "DB_USER": os.environ.get("DB_USER", ""),
        "DB_PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "DB_NAME": os.environ.get("DB_NAME", ""),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing MySQL settings: "
            f"{', '.join(missing)}. Set them in the project .env file."
        )

    server_url = URL.create(
        "mysql+mysqlconnector",
        username=settings["DB_USER"],
        password=settings["DB_PASSWORD"],
        host=settings["DB_HOST"],
    )
    bootstrap_engine = create_engine(server_url)
    try:
        with bootstrap_engine.connect() as connection:
            database_exists = connection.execute(
                text(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = :database_name"
                ),
                {"database_name": settings["DB_NAME"]},
            ).first()
            if database_exists is None:
                escaped_database = settings["DB_NAME"].replace("`", "``")
                connection.exec_driver_sql(
                    f"CREATE DATABASE IF NOT EXISTS `{escaped_database}`"
                )
    except SQLAlchemyError as exc:
        error_code = getattr(getattr(exc, "orig", None), "errno", None)
        if error_code == 1045:
            message = "MySQL rejected the configured username or password."
        elif error_code in {1044, 1227}:
            message = (
                f"The MySQL account lacks permission to create or access "
                f"database '{settings['DB_NAME']}'."
            )
        elif error_code in {2002, 2003}:
            message = (
                f"Could not reach MySQL at {settings['DB_HOST']}. Check that "
                "the MySQL service is running and the host is correct."
            )
        else:
            message = (
                f"Could not connect to MySQL or ensure database "
                f"'{settings['DB_NAME']}' exists: {exc}"
            )
        raise RuntimeError(message) from exc
    finally:
        bootstrap_engine.dispose()

    return create_engine(server_url.set(database=settings["DB_NAME"]))
