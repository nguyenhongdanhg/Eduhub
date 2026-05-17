from __future__ import annotations

from typing import Any

from app.db import get_db_connection


def ensure_rag_sources_table() -> None:
  sql = """
    CREATE TABLE IF NOT EXISTS rag_sources (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      domain ENUM('MANAGEMENT','TEACHING','LEARNING') NOT NULL DEFAULT 'MANAGEMENT',
      name VARCHAR(255) NOT NULL,
      description TEXT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uniq_rag_sources_domain_name (domain, name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql)
      cur.execute(
        """
          SELECT COUNT(*) AS cnt
          FROM INFORMATION_SCHEMA.COLUMNS
          WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='rag_sources' AND COLUMN_NAME='domain'
        """
      )
      has_domain = int((cur.fetchone() or {}).get("cnt") or 0) > 0
      if not has_domain:
        cur.execute("ALTER TABLE rag_sources ADD COLUMN domain ENUM('MANAGEMENT','TEACHING','LEARNING') NOT NULL DEFAULT 'MANAGEMENT' AFTER id")
      cur.execute(
        """
          SELECT COUNT(*) AS cnt
          FROM INFORMATION_SCHEMA.STATISTICS
          WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='rag_sources' AND INDEX_NAME='uniq_rag_sources_name'
        """
      )
      has_old_unique = int((cur.fetchone() or {}).get("cnt") or 0) > 0
      if has_old_unique:
        cur.execute("ALTER TABLE rag_sources DROP INDEX uniq_rag_sources_name")
      cur.execute(
        """
          SELECT COUNT(*) AS cnt
          FROM INFORMATION_SCHEMA.STATISTICS
          WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='rag_sources' AND INDEX_NAME='uniq_rag_sources_domain_name'
        """
      )
      has_new_unique = int((cur.fetchone() or {}).get("cnt") or 0) > 0
      if not has_new_unique:
        cur.execute("ALTER TABLE rag_sources ADD UNIQUE KEY uniq_rag_sources_domain_name (domain, name)")
    conn.commit()


def list_sources(*, domain: str | None = None, include_distinct_from_docs: bool = True) -> list[dict[str, Any]]:
  ensure_rag_sources_table()
  rows: list[dict[str, Any]] = []
  dom = (str(domain or "").strip().upper() or None)
  if dom not in (None, "MANAGEMENT", "TEACHING", "LEARNING"):
    dom = None
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      if dom:
        cur.execute(
          "SELECT id, domain, name, description, created_at, updated_at FROM rag_sources WHERE domain=%s ORDER BY name ASC",
          (dom,),
        )
      else:
        cur.execute("SELECT id, domain, name, description, created_at, updated_at FROM rag_sources ORDER BY name ASC")
      rows = list(cur.fetchall() or [])
  if not include_distinct_from_docs:
    return rows

  known = {(str(r.get("domain") or "").strip().upper(), str(r.get("name") or "").strip()): True for r in rows if isinstance(r, dict)}
  extras: list[str] = []
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      if dom:
        cur.execute(
          "SELECT DISTINCT domain, source AS name FROM rag_documents WHERE deleted_at IS NULL AND domain=%s AND source IS NOT NULL AND source <> '' LIMIT 500",
          (dom,),
        )
      else:
        cur.execute(
          "SELECT DISTINCT domain, source AS name FROM rag_documents WHERE deleted_at IS NULL AND source IS NOT NULL AND source <> '' LIMIT 500"
        )
      for r in cur.fetchall() or []:
        d = str((r or {}).get("domain") or "").strip().upper() or "MANAGEMENT"
        n = str((r or {}).get("name") or "").strip()
        key = (d, n)
        if n and key not in known:
          known[key] = True
          extras.append(f"{d}\t{n}")
  for raw in sorted(extras):
    d, n = raw.split("\t", 1)
    rows.append({"id": None, "domain": d, "name": n, "description": None, "created_at": None, "updated_at": None})
  return rows


def create_source(*, domain: str, name: str, description: str | None = None) -> dict[str, Any]:
  ensure_rag_sources_table()
  dom = str(domain or "").strip().upper()
  if dom not in ("MANAGEMENT", "TEACHING", "LEARNING"):
    raise ValueError("invalid_domain")
  n = str(name or "").strip()
  if not n:
    raise ValueError("missing_name")
  d = str(description or "").strip() or None
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
          INSERT INTO rag_sources (domain, name, description)
          VALUES (%s, %s, %s)
          ON DUPLICATE KEY UPDATE
            description=COALESCE(VALUES(description), description),
            updated_at=CURRENT_TIMESTAMP
        """,
        (dom, n, d),
      )
      cur.execute(
        "SELECT id, domain, name, description, created_at, updated_at FROM rag_sources WHERE domain=%s AND name=%s LIMIT 1",
        (dom, n),
      )
      row = cur.fetchone() or {}
    conn.commit()
  return dict(row)
