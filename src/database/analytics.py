# 1. third party
import polars as pl
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from psycopg_pool import ConnectionPool

# 2. local
from src.igdb.models import * #! this is important
from src.database.core import execute_sql_from_string
from src.utils.alerting import AlertLevel
from src.utils.alerting import log_to_discord

def run_dq_checks(db_pool: ConnectionPool, dataframe: pl.DataFrame) -> None:
    pass

def ensure_schema(db_pool: ConnectionPool) -> None:
    """
    A function that creates the tables automatically in postgres.

    db_pool: The database connection pool.
    """
    classes = BaseIGDBSchema.__subclasses__()
    
    for cls in classes:
        query: str = cls.build_pg_query()

        execute_sql_from_string(pool=db_pool, query=query, is_multistatement=True)

#TODO: on appelle cette fonction dans do ingestion si possible, ça sera un job séparé de blabla
def ingest_batches_to_postgres(azure_client: DataLakeServiceClient | BlobServiceClient, 
                               db_pool: ConnectionPool
) -> None:
    """
    PLACEHOLDER — future implementation.
    Reads newly landed raw/bronze batches from ADLS and loads them into Postgres.
    """

    dataframe: pl.DataFrame
    
    ensure_schema(db_pool=db_pool)
