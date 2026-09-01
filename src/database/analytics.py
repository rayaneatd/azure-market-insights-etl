# 1. native
import io
from concurrent.futures import ThreadPoolExecutor
from app.server import db_pool
from concurrent.futures import ThreadPoolExecutor

# 2. third party
from src.igdb.models import BaseIGDBSchema
import polars as pl
from azure.storage.blob import BlobServiceClient
from azure.storage.filedatalake import DataLakeServiceClient
from psycopg_pool import ConnectionPool 

# 3. local
from src.igdb.models import * #! this is important
from src.database.core import (
    DatabaseSchema, 
    execute_sql_from_string, 
    update_into_db
)
from src.datalake.functions import (
    Containers,
    read_from_raw 
)
from .types import AnalyticsTask
from src.database.logs import (
    get_checkpoints, 
    upsert_checkpoint, 
    get_unconsumed_raw_batches
)
from src.database.fallback import (
    get_pending_fallback_events, 
    update_fallback_event_status, 
    upsert_fallback_checkpoint
)
from src.utils.alerting import (
    AlertLevel, 
    log_to_discord
)


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

def ensure_schema(db_pool: ConnectionPool) -> None:
    classes = BaseIGDBSchema.__subclasses__()

    # 1. snapshot existant
    rows = execute_sql_from_string(
        pool=db_pool,
        query="SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
        params=(DatabaseSchema.ANALYTICS.value,)
    )
    existing = {r[0] for r in rows} if rows else set()

    for cls in classes:
        base = cls._endpoint.strip('/').replace('/', '_')
        scd1 = base
        scd2 = f"{base}_scd2"
        target = cls.get_table_name()
        other = scd2 if target == scd1 else scd1

        if other in existing and target not in existing:
            raise RuntimeError(
                f"[SCD SWITCH BLOQUÉ] {base}: {other} existe déjà, tu veux créer {target}. "
                f"Fais une migration manuelle, pas un switch de flag."
            )

        query = cls.build_pg_query()
        execute_sql_from_string(pool=db_pool, query=query)


def get_data_from_datalake(
    azure_client: DataLakeServiceClient | BlobServiceClient,
    db_pool: ConnectionPool,
    Model: type,
    task: AnalyticsTask,
) -> pl.DataFrame:
    """
    Reads raw bronze batches from ADLS for a specific model and watermark
    range, and returns them concatenated into a single DataFrame.
 
    Which files to read is resolved entirely from logs.batch_logs (via
    get_unconsumed_raw_batches). Downloads happen concurrently (I/O-bound, safe:
    the file list is already fully known up front, no ordering
    dependency between files). Parsing happens sequentially afterwards,
    so Polars' own internal thread pool isn't competing against the
    download threads.
 
    Raises:
        FileNotFoundError: If batch_logs claims a batch succeeded but the
            corresponding blob is missing from ADLS — a real data
            integrity issue, not something to skip silently.
    """
    paths = get_unconsumed_raw_batches(
        pool=db_pool,
        table_name=Model.__name__,
        endpoint=Model._endpoint,
        start_watermark=task.start_watermark,
        end_watermark=task.end_watermark,
    )
 
    if not paths:
        return pl.DataFrame()
 
    def _download(path: str) -> bytes | None:
        return read_from_raw(azure_client, Containers.Data.value, path)
 
    with ThreadPoolExecutor(max_workers=8) as executor:
        raw_blobs = list(executor.map(_download, paths))
 
    missing = [p for p, b in zip(paths, raw_blobs) if b is None]
    if missing:
        log_to_discord(
            f"{len(missing)} batch(es) marked SUCCESS in batch_logs but "
            f"missing from ADLS for {Model.__name__}: {missing[:5]}"
            f"{'...' if len(missing) > 5 else ''}",
            AlertLevel.ERROR,
        )
        raise FileNotFoundError(
            f"Missing raw blob(s) for {Model.__name__}: {len(missing)} file(s)"
        )
 
    frames = [pl.read_json(io.BytesIO(b)) for b in raw_blobs if b is not None]
    return pl.concat(frames) if frames else pl.DataFrame()
 

def run_data_transformations(
    Model: type,
    dataframe: pl.DataFrame
) -> pl.DataFrame:
    """Applies Polars transformations to produce silver analytics dataframe."""

    # jv probablement rename cette fonction lol. en gros on retreive les bonnes colonnes du dataframe
    # on fait un schema check ici... si y a des colonnes en + on ignore mais on est notifiés avec suffisamment
    # de context pour check les logs etc. si y a des colonnes en - alors on fail ce batch et notif
    # SI TOUT VA BIEN alors ici on construis le scd2 ou rempli les m2m quoi.
    # peut etre que jv introduire un ddl generator pour l'upsert dans BASE.py mais bref
    # c'est ici qu'on fait tout ça 
    # 
    # d'ailleurs à voir pour la partie fallback aussi... Car apres avoir implémenté ça, le fallback
    # sera le GROS prochain truc à faire. Apres ça bah cb je fais un day off + révision archi pour pas me faire
    # griller en entretien. + j'update la doc + je fais révision de comment je construirai réellement
    # le projet dans une vraie doc (je code RIEN hein...) + je revois le projet fabric et je fais un POC moche  
    return dataframe

def run_dq_checks(db_pool: ConnectionPool, dataframe: pl.DataFrame) -> bool:
    """Runs data quality assertions on transformed dataframe."""
    # alors ici rien de spécial juste on prend les pt.Field, on traduis en check postgres
    # rien de fou. tout va obéir le data contract. ez. 
    return True


def ingest_batches_to_postgres(
    azure_client: DataLakeServiceClient | BlobServiceClient, 
    db_pool: ConnectionPool
) -> None:
    """
    Reads newly landed raw/bronze batches from ADLS, transforms them with Polars,
    executes DQ checks, loads into Postgres ANALYTICS schema, and updates checkpoints.
    """
    ensure_schema(db_pool=db_pool)

    data_to_ingest: dict[type, AnalyticsTask] = _get_watermark_dict(db_pool)

    for Model, task in data_to_ingest.items():
        table_name = Model.get_table_name()

        # 1. Fetch raw batch for this model and watermark window
        raw_df: pl.DataFrame = get_data_from_datalake(
            azure_client=azure_client,
            db_pool=db_pool,
            Model=Model,
            task=task
        )

        if raw_df.is_empty():
            continue

        # 2. Polars Transformations
        transformed_df: pl.DataFrame = run_data_transformations(Model=Model, dataframe=raw_df)

        # 3. Quality Checks
        quality = run_dq_checks(db_pool=db_pool, dataframe=transformed_df)
        if not quality:
            log_to_discord(f"Data quality check failed on table '{table_name}'", AlertLevel.WARNING)
            if task.is_fallback and task.event_id:
                update_fallback_event_status(db_pool, task.event_id, status="FAILED", error_message="DQ check failed")
            continue

        # 4. Dump transformed dataframe into Postgres ANALYTICS schema
        update_into_db(
            schema=DatabaseSchema.ANALYTICS,
            table=table_name,
            df=transformed_df
        )

        # 5. Update Checkpoint or Fallback Event Status
        if task.is_fallback and task.event_id:
            update_fallback_event_status(
                db_pool, 
                task.event_id, 
                status="COMPLETED", 
                records_processed=len(transformed_df)
            )
        else:
            raw_max = transformed_df["updated_at"].max() if "updated_at" in transformed_df.columns else None
            new_watermark: int = int(raw_max) if isinstance(raw_max, (int, float)) else task.start_watermark

            upsert_checkpoint(
                pool=db_pool,
                table_name=Model.__name__,
                current_watermark=new_watermark,
                last_id=0,
                layer="ANALYTICS",
                offset_val=0,
                run_id=None
            )
            upsert_fallback_checkpoint(
                pool=db_pool, 
                table_name=Model.__name__,
                layer='ANALYTICS', 
                fallback_watermark=new_watermark
            )