from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from psycopg_pool import ConnectionPool



def ingest_batches_to_postgres(azure_client: DataLakeServiceClient | BlobServiceClient, 
                               db_pool: ConnectionPool
) -> None:
    """
    PLACEHOLDER — future implementation.
    Reads newly landed raw/bronze batches from ADLS and loads them into Postgres.
    """
    pass
