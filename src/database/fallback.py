from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from typing import Literal

from .core import _execute
from .types import FallbackEvent


def get_pending_fallback_events(
    pool: ConnectionPool, 
    layer: Literal['RAW', 'ANALYTICS']
) -> list[FallbackEvent]:
    """Retrieves pending fallback events in FIFO order."""
    query = """
        SELECT event_id::text, table_name, layer, start_watermark, end_watermark, status
        FROM logs.fallback_events
        WHERE status = 'PENDING' AND layer = %(layer)s
        ORDER BY created_at ASC;
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, {"layer": layer})
            return [FallbackEvent(**row) for row in cur.fetchall()]


def update_fallback_event_status(
    pool: ConnectionPool,
    event_id: str | None,
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"],
    records_processed: int = 0,
    error_message: str | None = None
) -> None:
    """Updates status and metrics for a fallback event."""
    query = """
        UPDATE logs.fallback_events
        SET status = %(status)s,
            records_processed = records_processed + %(records_processed)s,
            error_message = %(error_message)s,
            completed_at = CASE WHEN %(status)s IN ('COMPLETED', 'FAILED') THEN CURRENT_TIMESTAMP ELSE completed_at END
        WHERE event_id = %(event_id)s::uuid;
    """
    _execute(pool, query, {
        "event_id": event_id,
        "status": status,
        "records_processed": records_processed,
        "error_message": error_message
    })


def upsert_fallback_checkpoint(pool: ConnectionPool, table_name: str, fallback_watermark: int) -> None:
    """
    Updates the fallback/safety point for a table (when run succeeds entirely).
    
    Args:
        pool: The database connection pool.
        table_name: The table name.
        fallback_watermark: The fallback watermark timestamp.
    """
    query = """
        INSERT INTO logs.ingestion_checkpoints (table_name, fallback_watermark, updated_at)
        VALUES (%(table_name)s, %(fallback_watermark)s, CURRENT_TIMESTAMP)
        ON CONFLICT (table_name) DO UPDATE SET
            fallback_watermark = EXCLUDED.fallback_watermark,
            updated_at = CURRENT_TIMESTAMP;
    """
    _execute(pool, query, {
        "table_name": table_name,
        "fallback_watermark": fallback_watermark
    })
