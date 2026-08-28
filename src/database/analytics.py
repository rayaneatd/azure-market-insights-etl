# 1. third party
from src.igdb.models import BaseIGDBSchema
import polars as pl
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from psycopg_pool import ConnectionPool

# 2. local
from src.igdb.models import * #! this is important
from src.database.core import DatabaseSchema, execute_sql_from_string, update_into_db
from .types import AnalyticsTask
from src.database.logs import get_checkpoints, upsert_checkpoint
from src.database.fallback import (
    get_pending_fallback_events, 
    update_fallback_event_status, 
    upsert_fallback_checkpoint
)
from src.utils.alerting import AlertLevel, log_to_discord


def _get_watermark_dict(db_pool: ConnectionPool) -> dict[type, AnalyticsTask]:
    """
    Retrieves execution parameters for the ANALYTICS layer per table.
    Combines fallback events for tables that have them with standard incremental checkpoints for the rest.
    Pure read-only query without side effects.
    """
    defined_classes = BaseIGDBSchema.__subclasses__()
    pending_events = get_pending_fallback_events(db_pool, layer='ANALYTICS')
    checkpoints = get_checkpoints(db_pool, layer='ANALYTICS')

    # Index pending fallback events by table_name for O(1) lookup
    fallback_map = {event.table_name: event for event in pending_events}

    resolved: dict[type, AnalyticsTask] = {}

    for cls in defined_classes:
        name = cls.__name__
        
        # 1. Table has a PENDING fallback event
        if name in fallback_map:
            event = fallback_map[name]
            resolved[cls] = AnalyticsTask(
                start_watermark=event.start_watermark,
                end_watermark=event.end_watermark,
                is_fallback=True,
                event_id=event.event_id
            )
        # 2. Standard continuous incremental checkpoint
        else:
            ckpt = checkpoints.get(name)
            current_ts = ckpt.current_watermark if (ckpt and ckpt.current_watermark > 0) else cls._starting_point
            resolved[cls] = AnalyticsTask(
                start_watermark=current_ts,
                end_watermark=None,
                is_fallback=False,
                event_id=None
            )

    return resolved

def run_dq_checks(db_pool: ConnectionPool, dataframe: pl.DataFrame | None) -> bool:
    return False

def run_data_transformations(azure_client: DataLakeServiceClient | BlobServiceClient,
                             dataframe: pl.DataFrame | None
) -> pl.DataFrame:
    return pl.DataFrame()

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
    ensure_schema(db_pool=db_pool)

    dataframe: pl.DataFrame = pl.DataFrame()
    table_name: str = 'we need to populate this'

    # {'Nom De La Table': AnalyticsTask}
    data_to_ingest: dict[type, AnalyticsTask] = _get_watermark_dict(db_pool)

    # we get the batches to read from postgres
    for Model in data_to_ingest:
        # we apply polar transformations
        transformed_df = run_data_transformations(azure_client, dataframe=dataframe)

        # we do quality checks
        quality = run_dq_checks(db_pool=db_pool, dataframe=transformed_df)

        if quality:
            # we dump the dataframe to postgres
            update_into_db(
                pool=db_pool,
                schema=DatabaseSchema.ANALYTICS,
                table=table_name,
                df=transformed_df
            )
        else:
            log_to_discord(f"data quality sucks on {table_name}", AlertLevel.WARNING)