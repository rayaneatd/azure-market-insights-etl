import os

from src.datalake.service_client import init_datalake_service_client
from src.database.auth import init_database_engine
from src.utils.alerting import log_to_discord, AlertLevel 
from src.database import execute_sql_from_file

from src.handle_ingestion import do_ingestion
from src.database.analytics import ingest_batches_to_postgres

# authentication is managed only when the program starts
datalake_service_client = init_datalake_service_client()
database_pool = init_database_engine()

# full code - orchestration is fully linear
def run_full_pipeline():                                                                                                                                                                                                   
    if datalake_service_client is None:
        log_to_discord("Error: Datalake service client not initialized", level=AlertLevel.ERROR)
        return 

    if database_pool is None:
        log_to_discord("Error: Database connection pool not initialized", level=AlertLevel.ERROR)
        return

    # Ensure log tables schema is applied before ingestion
    try:
        ddl_path = os.path.join(os.path.dirname(__file__), "src", "database", "models", "log_schemas.sql")
        execute_sql_from_file(database_pool, ddl_path)
    except Exception as e:
        log_to_discord(f"Critical error applying database migrations: {e}", level=AlertLevel.ERROR)
        return
    
    
    # main pipeline
    #TODO; la fonction qui log les runs sera déplacée ici, peut etre qu'on sépare Raw et Analytics, on met tout en pending puis on update à chaque début des deux pipelines respectives
    do_ingestion(datalake_service_client, database_pool)
    ingest_batches_to_postgres(datalake_service_client, database_pool)

if __name__ == "__main__":
    run_full_pipeline()