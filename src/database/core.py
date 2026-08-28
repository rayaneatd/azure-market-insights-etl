"""
Core database utilities: raw SQL execution, and reading/writing Polars
DataFrames against Postgres.

Read path uses a pooled psycopg connection directly (DBAPI2 connections
are supported natively by pl.read_database).

Write path uses the ADBC engine with a connection URI, since
"pl.write_database" doen't accept a raw DBAPI2 connection; Only a
SQLAlchemy/ADBC connection or a URI string. Using ADBC (instead of the
default "sqlalchemy" engine) avoids pulling in Pandas as a dependency,
keeping the write path consistent with the rest of the Polars/Arrow stack.
"""

import os
import re
from enum import Enum
from typing import Any, Literal, Mapping, Sequence
from urllib.parse import quote_plus

import polars as pl
from psycopg import sql
from psycopg_pool import ConnectionPool

from src.config import (
    DEV_POSTGRES_DB,
    DEV_POSTGRES_HOST,
    DEV_POSTGRES_PASSWORD,
    DEV_POSTGRES_PORT,
    DEV_POSTGRES_USER,
    IS_DEV,
    IS_PROD,
    PROD_POSTGRES_DB,
    PROD_POSTGRES_HOST,
    PROD_POSTGRES_PASSWORD,
    PROD_POSTGRES_PORT,
    PROD_POSTGRES_USER,
)
from src.utils.alerting import AlertLevel, log_to_discord

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DatabaseSchema(Enum):
    LOGS = "logs"
    ANALYTICS = "public"


def _get_schema_name(schema: DatabaseSchema | str) -> str:
    return schema.value if isinstance(schema, Enum) else schema


def _validate_identifier(name: str, kind: str) -> str:
    """
    Fails fast on an unsafe/unexpected schema or table name instead of
    letting a malformed one reach the database as a raw string (relevant
    for the ADBC write path, which has no equivalent to psycopg's
    ``sql.Identifier`` quoting).

    Args:
        name: The identifier to validate.
        kind: Human-readable label used in the error message (e.g. "schema", "table").

    Raises:
        ValueError: If ``name`` is not a simple alphanumeric/underscore identifier.
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {kind} name: {name!r}")
    return name


def _build_connection_uri() -> str:
    """
    Builds a Postgres connection URI from the same env-driven config used
    by ``init_database_engine``, for use with the ADBC write engine.

    User and password are percent-encoded, since a raw password containing
    characters like '@' or '/' would otherwise silently break URI parsing.

    Raises:
        ValueError: If neither IS_DEV nor IS_PROD is set.
    """
    if IS_DEV:
        user, password, host, port, dbname = (
            DEV_POSTGRES_USER,
            DEV_POSTGRES_PASSWORD,
            DEV_POSTGRES_HOST,
            DEV_POSTGRES_PORT,
            DEV_POSTGRES_DB,
        )
    elif IS_PROD:
        user, password, host, port, dbname = (
            PROD_POSTGRES_USER,
            PROD_POSTGRES_PASSWORD,
            PROD_POSTGRES_HOST,
            PROD_POSTGRES_PORT,
            PROD_POSTGRES_DB,
        )
    else:
        raise ValueError("Invalid environment: neither IS_DEV nor IS_PROD is set")

    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{dbname}"
    )


def _execute(
    pool: ConnectionPool,
    query: str | sql.SQL,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    fetch: bool = False,
) -> list[tuple[Any, ...]] | None:
    """
    Executes a SQL query or Composed SQL within a transaction using psycopg 3.

    Args:
        pool: The database connection pool.
        query: The SQL query string or sql.SQL object.
        params: The parameters (sequence or dict) to bind to the query.
        fetch: If True, returns all rows from the (first) result set.

    Returns:
        All fetched rows if fetch is True, otherwise None.
    """
    with pool.connection() as conn:
        with conn.transaction():
            cur = conn.execute(query, params)  # pyrefly: ignore[bad-argument-type]
            if fetch:
                return cur.fetchall()
    return None


def execute_sql_from_string(
    pool: ConnectionPool,
    query: str | sql.SQL,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    fetch: bool = False,
) -> list[tuple[Any, ...]] | None:
    """
    Executes a raw SQL string within a transaction.

    Args:
        pool: The database connection pool.
        query: The SQL query to execute.
        params: The parameters to use for the query.
        fetch: If True, returns all rows from the (first) result set.

    Raises:
        ValueError: If the query looks like more than one statement AND
            (a) params are supplied — psycopg3's extended protocol cannot
            bind params across multiple statements, or (b) fetch=True —
            psycopg3 only exposes the FIRST statement's result set via
            fetchall() (unlike psycopg2, which gives the last); silently
            ignoring the rest is worse than refusing to run.
    """
    is_multistatement = isinstance(query, str) and query.count(";") > 1

    if is_multistatement and params:
        raise ValueError(
            "Cannot combine params with a multi-statement query: psycopg3's "
            "extended protocol only supports a single statement per bound "
            "execute() call."
        )
    if is_multistatement and fetch:
        raise ValueError(
            "fetch=True with a multi-statement query would silently return "
            "only the first statement's results. Split the statements and "
            "call execute_sql_from_string() once per SELECT instead."
        )

    return _execute(pool, query, params, fetch=fetch)


def execute_sql_from_file(pool: ConnectionPool, path: str) -> None:
    """
    Reads a SQL file and executes it within a single, atomic transaction.

    Args:
        pool: The database connection pool.
        path: The path to the SQL file.

    Raises:
        FileNotFoundError: If no file exists at ``path``.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"SQL file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        ddl = f.read()

    _execute(pool, ddl)


def read_from_db(pool: ConnectionPool, schema: DatabaseSchema | str, table: str) -> pl.DataFrame:
    """
    Reads a full table from the database into a Polars DataFrame.

    Uses the pooled psycopg connection directly — pl.read_database supports
    DBAPI2 connections natively, so no separate engine/URI is needed here.

    Args:
        pool: The database connection pool.
        schema: The database schema.
        table: The table name.

    Returns:
        The table's contents as a Polars DataFrame.
    """
    schema_name = _validate_identifier(_get_schema_name(schema), "schema")
    table = _validate_identifier(table, "table")

    query = sql.SQL("SELECT * FROM {}.{}").format(
        sql.Identifier(schema_name),
        sql.Identifier(table),
    )

    try:
        with pool.connection() as conn:
            query_str = query.as_string(conn)
            return pl.read_database(query_str, connection=conn)
    except Exception as e:
        log_to_discord(f"read_from_db failed for {schema_name}.{table}: {e}", AlertLevel.ERROR)
        raise


def update_into_db(
    schema: DatabaseSchema | str,
    table: str,
    df: pl.DataFrame,
    if_table_exists: Literal["append", "fail", "replace"] = "append",
) -> None:
    """
    Writes a Polars DataFrame into the database via the ADBC engine.

    Note this does NOT take the ConnectionPool: pl.write_database cannot use
    a raw psycopg connection (only SQLAlchemy/ADBC connections or a URI
    string are accepted), so this opens its own short-lived ADBC connection
    via a URI built from the same env config as the pool. If this ends up
    being called at high frequency, consider opening one ADBC connection
    once (e.g. via adbc_driver_postgresql) and reusing it across calls
    instead of reconnecting every time.

    Args:
        schema: The database schema.
        table: The table name.
        df: The Polars DataFrame to write.
        if_table_exists: The action to take if the table already exists.

    Raises:
        ValueError: If schema/table aren't simple identifiers, or if
            neither IS_DEV nor IS_PROD is set.
    """
    schema_name = _validate_identifier(_get_schema_name(schema), "schema")
    table = _validate_identifier(table, "table")
    full_table_name = f"{schema_name}.{table}"

    try:
        df.write_database(
            table_name=full_table_name,
            connection=_build_connection_uri(),
            engine="adbc",
            if_table_exists=if_table_exists,
        )
    except Exception as e:
        log_to_discord(f"update_into_db failed for {full_table_name}: {e}", AlertLevel.ERROR)
        raise