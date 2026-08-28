# 1. third party
import polars as pl
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from psycopg_pool import ConnectionPool

# 2. local
from src.igdb.models import * #! this is important
from src.database.core import DatabaseSchema, execute_sql_from_string, update_into_db
from src.utils.alerting import AlertLevel, log_to_discord


def _get_watermark_dict(db_pool: ConnectionPool) -> dict[str, int]:
    return {}

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

    #TODO: pour cette partie on utilise le watermark classique, si c'est vide alors on essaie d'obtenir la date minimale loggée 
    #TODO (min batch raw history ça marche aussi) puis on RUN. Puis on inscrit le watermark etc.
    #TODO vu que la RAW est deja peuplée pas besoin de créer un autre, on réutilise le mm watermark, aucun risque de conflit
    #TODO d'écriture. On ferait ça ofc maybe si on passe en threading, mais c'est à voit mdr
    # {'Nom De La Table': }
    data_to_ingest: dict[str, int] = _get_watermark_dict(db_pool)

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