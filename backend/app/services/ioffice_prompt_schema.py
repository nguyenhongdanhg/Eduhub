from app.db import get_db_connection


def _table_exists(table: str) -> bool:
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.tables
        WHERE table_schema=DATABASE()
          AND table_name=%s
        """,
        (table,),
      )
      row = cur.fetchone() or {}
      return int(row.get("cnt") or 0) > 0


def ensure_ioffice_prompt_tables() -> None:
  table = "ioffice_prompt_presets"
  try:
    if _table_exists(table):
      return
  except Exception:
    return
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          """
          CREATE TABLE ioffice_prompt_presets (
            id VARCHAR(64) NOT NULL PRIMARY KEY,
            label VARCHAR(255) NOT NULL,
            prompt TEXT NOT NULL,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
          ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          """
        )
  except Exception:
    return

