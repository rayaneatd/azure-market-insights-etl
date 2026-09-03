import os

from src.datalake.service_client import init_datalake_service_client
from src.database.auth import init_database_engine
from src.utils.alerting import log_to_discord, AlertLevel 
from src.database import execute_sql_from_file

from src.handle_ingestion import do_ingestion
from src.database.analytics import ingest_batches_to_postgres

def run_full_pipeline(datalake_client=None, db_pool=None):                                                                                                                                                                                                   
    print("[PIPELINE] Starting Azure Market Insights ELT orchestration...", flush=True)

    client = datalake_client or init_datalake_service_client()
    pool = db_pool or init_database_engine()

    if client is None:
        log_to_discord("Error: Datalake service client not initialized", level=AlertLevel.ERROR)
        print("[PIPELINE ERROR] Datalake service client not initialized", flush=True)
        return 

    if pool is None:
        log_to_discord("Error: Database connection pool not initialized", level=AlertLevel.ERROR)
        print("[PIPELINE ERROR] Database connection pool not initialized", flush=True)
        return

    # Ensure log tables schema is applied before ingestion
    try:
        ddl_path = os.path.join(os.path.dirname(__file__), "src", "database", "models", "log_schemas.sql")
        execute_sql_from_file(pool, ddl_path)
    except Exception as e:
        log_to_discord(f"Critical error applying database migrations: {e}", level=AlertLevel.ERROR)
        print(f"[PIPELINE ERROR] Critical error applying migrations: {e}", flush=True)
        return
    
    # Ingestion Layer: API -> RAW Layer (ADLS)
    print("[PIPELINE] Executing RAW Ingestion layer...", flush=True)
    do_ingestion(client, pool)

    # Analytics Layer: RAW -> Polars -> PostgreSQL
    print("[PIPELINE] Executing ANALYTICS Transformation & Loading layer...", flush=True)
    ingest_batches_to_postgres(client, pool)
    print("[PIPELINE] ELT Pipeline execution completed.", flush=True)

if __name__ == "__main__":
    run_full_pipeline()