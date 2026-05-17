from app.db import get_db_connection


def _column_exists(table: str, column: str) -> bool:
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.columns
        WHERE table_schema=DATABASE()
          AND table_name=%s
          AND column_name=%s
        """,
        (table, column),
      )
      row = cur.fetchone() or {}
      return int(row.get("cnt") or 0) > 0


def ensure_ioffice_audio_columns() -> None:
  table = "ioffice_documents"
  cols = {
    "audio_status": "ALTER TABLE ioffice_documents ADD COLUMN audio_status VARCHAR(16) NULL",
    "audio_path": "ALTER TABLE ioffice_documents ADD COLUMN audio_path VARCHAR(1024) NULL",
    "audio_error": "ALTER TABLE ioffice_documents ADD COLUMN audio_error TEXT NULL",
    "audio_updated_at": "ALTER TABLE ioffice_documents ADD COLUMN audio_updated_at TIMESTAMP NULL",
    "audio_hash": "ALTER TABLE ioffice_documents ADD COLUMN audio_hash CHAR(64) NULL",
  }
  for col, ddl in cols.items():
    try:
      if _column_exists(table, col):
        continue
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(ddl)
    except Exception:
      continue

