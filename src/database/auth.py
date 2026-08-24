from psycopg_pool import ConnectionPool 
from src.config import (
    # dev postgres credentials
    DEV_POSTGRES_USER, 
    DEV_POSTGRES_PASSWORD,
    DEV_POSTGRES_HOST,
    DEV_POSTGRES_PORT,
    DEV_POSTGRES_DB,
    # prod postgres credentials
    PROD_POSTGRES_USER,
    PROD_POSTGRES_PASSWORD,
    PROD_POSTGRES_HOST,
    PROD_POSTGRES_PORT,
    PROD_POSTGRES_DB,

    # project env helpers
    IS_DEV,
    IS_PROD
)

from src.utils.alerting import log_to_discord, AlertLevel


# initialize database engine
def init_database_engine() -> ConnectionPool | None:
    """
    Create and return a Postgres connection pool based on environment.

    Returns:
        ConnectionPool configured for DEV or PROD, or None if initialization fails.

    Raises:
        ValueError: If neither IS_DEV nor IS_PROD is set. This prevents
            silently falling back to production.
    """

    try:
        
        pool: ConnectionPool | None = None
        
        
        if IS_DEV:
            pool = ConnectionPool(
                kwargs={
                    "host": DEV_POSTGRES_HOST,
                    "port": DEV_POSTGRES_PORT,
                    "dbname": DEV_POSTGRES_DB,
                    "user": DEV_POSTGRES_USER,
                    "password": DEV_POSTGRES_PASSWORD,
                    "autocommit": False,
                },
                min_size=1,
                max_size=10,
                timeout=30,
            )
        elif IS_PROD:
            pool = ConnectionPool(
                kwargs={
                    "host": PROD_POSTGRES_HOST,
                    "port": PROD_POSTGRES_PORT,
                    "dbname": PROD_POSTGRES_DB,
                    "user": PROD_POSTGRES_USER,
                    "password": PROD_POSTGRES_PASSWORD,
                    "autocommit": False,
                },
                min_size=1,
                max_size=10,
                timeout=30,
            )
        else:
            raise ValueError("Invalid environment")
        

        return pool
    except Exception as e:
        log_to_discord(f"Error: {e}", level=AlertLevel.ERROR)
        return None