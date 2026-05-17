from __future__ import annotations

import os
from dataclasses import dataclass

import pymysql


@dataclass(frozen=True)
class MariaDbConfig:
  host: str = "127.0.0.1"
  port: int = 3306
  user: str = "root"
  password: str = "root"
  database: str = "eduai_hub"


def load_db_config() -> MariaDbConfig:
  return MariaDbConfig(
    host=os.getenv("EDUAI_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("EDUAI_DB_PORT", "3306")),
    user=os.getenv("EDUAI_DB_USER", "root"),
    password=os.getenv("EDUAI_DB_PASSWORD", "root"),
    database=os.getenv("EDUAI_DB_NAME", "eduai_hub"),
  )


class RagMappingRepo:
  def __init__(self, config: MariaDbConfig | None = None) -> None:
    self._config = config or load_db_config()

  def _conn(self):
    return pymysql.connect(
      host=self._config.host,
      port=self._config.port,
      user=self._config.user,
      password=self._config.password,
      database=self._config.database,
      charset="utf8mb4",
      autocommit=True,
      init_command="SET time_zone = '+07:00'",
    )

  def upsert_document(
    self,
    *,
    domain: str,
    source: str,
    type: str,
    original_id: str,
    title: str | None,
    school_id: int | None,
    subject_id: int | None,
    grade: int | None,
    qdrant_collection: str,
    status: str,
    content_hash: str | None,
  ) -> int:
    sql = """
      INSERT INTO rag_documents
        (domain, source, type, original_id, title, school_id, subject_id, grade, qdrant_collection, status, content_hash)
      VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        title=VALUES(title),
        school_id=VALUES(school_id),
        subject_id=VALUES(subject_id),
        grade=VALUES(grade),
        qdrant_collection=VALUES(qdrant_collection),
        status=VALUES(status),
        content_hash=VALUES(content_hash),
        deleted_at=NULL,
        last_error=NULL,
        updated_at=CURRENT_TIMESTAMP
    """
    with self._conn() as conn:
      with conn.cursor() as cur:
        cur.execute(
          sql,
          (
            domain,
            source,
            type,
            original_id,
            title,
            school_id,
            subject_id,
            grade,
            qdrant_collection,
            status,
            content_hash,
          ),
        )
        cur.execute(
          "SELECT id FROM rag_documents WHERE domain=%s AND source=%s AND type=%s AND original_id=%s",
          (domain, source, type, original_id),
        )
        row = cur.fetchone()
        return int(row[0])

  def get_document(self, *, domain: str, source: str, type: str, original_id: str) -> dict | None:
    sql = """
      SELECT id, domain, source, type, original_id, title, qdrant_collection, status, content_hash, chunk_count, last_indexed_at
      FROM rag_documents
      WHERE domain=%s AND source=%s AND type=%s AND original_id=%s
    """
    with self._conn() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (domain, source, type, original_id))
        row = cur.fetchone()
        if not row:
          return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

  def get_item_point_id(self, *, rag_document_id: int, chunk_index: int) -> str | None:
    sql = "SELECT qdrant_point_id FROM rag_items WHERE rag_document_id=%s AND chunk_index=%s LIMIT 1"
    with self._conn() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (int(rag_document_id), int(chunk_index)))
        row = cur.fetchone()
        return str(row[0]) if row and row[0] else None

  def insert_item(
    self,
    *,
    rag_document_id: int,
    domain: str,
    source: str,
    type: str,
    title: str | None,
    original_id: str,
    chunk_index: int,
    qdrant_collection: str,
    qdrant_point_id: str,
    metadata: str,
    status: str,
    content_hash: str | None,
  ) -> int:
    sql = """
      INSERT INTO rag_items
        (rag_document_id, domain, source, type, title, original_id, chunk_index, qdrant_collection, qdrant_point_id, metadata, status, content_hash, embedded_at)
      VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, CASE WHEN %s='READY' THEN CURRENT_TIMESTAMP ELSE NULL END)
    """
    with self._conn() as conn:
      with conn.cursor() as cur:
        cur.execute(
          sql,
          (
            rag_document_id,
            domain,
            source,
            type,
            title,
            original_id,
            chunk_index,
            qdrant_collection,
            qdrant_point_id,
            metadata,
            status,
            content_hash,
            status,
          ),
        )
        return int(cur.lastrowid)

  def upsert_item(
    self,
    *,
    rag_document_id: int,
    domain: str,
    source: str,
    type: str,
    title: str | None,
    original_id: str,
    chunk_index: int,
    qdrant_collection: str,
    qdrant_point_id: str,
    metadata: str,
    status: str,
    content_hash: str | None,
  ) -> int:
    sql = """
      INSERT INTO rag_items
        (rag_document_id, domain, source, type, title, original_id, chunk_index, qdrant_collection, qdrant_point_id, metadata, status, content_hash, embedded_at, deleted_at, last_error)
      VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, CASE WHEN %s='READY' THEN CURRENT_TIMESTAMP ELSE NULL END, NULL, NULL)
      ON DUPLICATE KEY UPDATE
        qdrant_collection=VALUES(qdrant_collection),
        qdrant_point_id=VALUES(qdrant_point_id),
        metadata=VALUES(metadata),
        status=VALUES(status),
        content_hash=VALUES(content_hash),
        embedded_at=CASE WHEN VALUES(status)='READY' THEN CURRENT_TIMESTAMP ELSE embedded_at END,
        deleted_at=NULL,
        last_error=NULL,
        updated_at=CURRENT_TIMESTAMP
    """
    with self._conn() as conn:
      with conn.cursor() as cur:
        cur.execute(
          sql,
          (
            int(rag_document_id),
            domain,
            source,
            type,
            title,
            original_id,
            int(chunk_index),
            qdrant_collection,
            qdrant_point_id,
            metadata,
            status,
            content_hash,
            status,
          ),
        )
        cur.execute(
          "SELECT id FROM rag_items WHERE rag_document_id=%s AND chunk_index=%s",
          (int(rag_document_id), int(chunk_index)),
        )
        row = cur.fetchone()
        return int(row[0])

  def finalize_document(self, *, rag_document_id: int, chunk_count: int, status: str, last_error: str | None = None) -> None:
    sql = """
      UPDATE rag_documents
      SET status=%s, chunk_count=%s, last_error=%s, last_indexed_at=CURRENT_TIMESTAMP
      WHERE id=%s
    """
    with self._conn() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (status, chunk_count, last_error, rag_document_id))
