from src.utils.alerting import AlertLevel
from src.utils.alerting import log_to_discord
import os
import polars as pl
from psycopg_pool import ConnectionPool
from psycopg import sql
from enum import Enum
from typing import (
    Literal,
    Sequence,
    Mapping,
    Any
)

class DatabaseSchema(Enum):
    LOGS = "logs"


def _get_schema_name(schema: DatabaseSchema) -> str:
    return schema.value if isinstance(schema, Enum) else schema


def _execute(
    pool: ConnectionPool, 
    query: str | sql.SQL, 
    params: Sequence[Any] | Mapping[str, Any] | None = None
) -> None:
    """
    Executes a SQL query string or Composed SQL within a transaction using psycopg 3.
    
    Args:
        pool: The database connection pool.
        query: The SQL query string or sql.SQL object.
        params: The parameters (sequence or dict) to bind to the query.
    """
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute(query, params) # pyrefly: ignore[bad-argument-type]


# function to execute sql queries from a string
def execute_sql_from_string(
    pool: ConnectionPool, 
    query: str | sql.SQL, 
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    is_multistatement: bool = False
) -> None:
    """
    Executes a raw SQL string within a transaction.
    
    Args:
        pool: The database connection pool.
        query: The SQL query to execute.
        params: The parameters to use for the query.
        is_multistatement: are there multiple queries ? 
    NOTE: 
        - IF is_multistatement is True, ANY PARAMETER WILL BE IGNORED !!!!
        - IF is_multistatement is True, Query must be a string
    """

    if is_multistatement:

        if not isinstance(query, str):
            log_to_discord('Query must be a string in multi-statement run', AlertLevel.ERROR)

            raise TypeError(f"is_multistatement=True attend un str, pas {type(query)} -> c'est ton DDL")
        else:
            statements = [s.strip() for s in query.split(";\n") if s.strip()]

            if params is not None:
                log_to_discord("PARAMETERS ARE IGNORED !", AlertLevel.WARNING)

            for statement in statements:
                if not statement.endswith(';'):
                    statement += ';'
                _execute(pool, statement)
    else:
        _execute(pool, query, params)


# functions to execute sql queries from a file
def execute_sql_from_file(pool: ConnectionPool, path: str) -> None:
    """
    Reads a SQL file and executes it within a transaction.
    
    Args:
        pool: The database connection pool.
        path: The path to the SQL file.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"SQL file not found at: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        query_str = f.read()
    
    statements = [s.strip() for s in query_str.split(";\n") if s.strip()]

    for statement in statements:
        _execute(pool, statement)


# function to read from the database
def read_from_db(pool: ConnectionPool, schema: DatabaseSchema, table: str) -> pl.DataFrame:
    """
    Reads a table from the database and returns a Polars DataFrame.
    
    Args:
        pool: The database connection pool.
        schema: The database schema.
        table: The table name.
    """
    schema_name = _get_schema_name(schema)
    
    query = sql.SQL("SELECT * FROM {}.{}").format(
        sql.Identifier(schema_name),
        sql.Identifier(table)
    )

    with pool.connection() as conn:
        query_str = query.as_string(conn)
        return pl.read_database(query_str, connection=conn)


# function to update/write into the database
def update_into_db(
    pool: ConnectionPool,
    schema: DatabaseSchema,
    table: str,
    df: pl.DataFrame,
    if_table_exists: Literal["append", "fail", "replace"] = "append"
) -> None:
    """
    Writes/updates a Polars DataFrame into the database.
    
    Args:
        pool: The database connection pool.
        schema: The database schema.
        table: The table name.
        df: The Polars DataFrame to write.
        if_table_exists: The action to take if the table already exists.
    """
    schema_name = _get_schema_name(schema)
    full_table_name = f"{schema_name}.{table}"

    with pool.connection() as conn:
        df.write_database(
            table_name=full_table_name,
            connection=conn,
            if_table_exists=if_table_exists
        )
