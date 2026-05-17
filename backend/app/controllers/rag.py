from datetime import datetime, timezone

import pymysql
from fastapi import APIRouter
from fastapi import File
from fastapi import Header
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi import Query
from fastapi import Form
from pydantic import BaseModel
from fastapi.responses import FileResponse

from app.db import get_db_connection

router = APIRouter()


@router.get("/collections")
def list_collections():
  return {"items": ["RAG_MANAGEMENT", "RAG_TEACHING", "RAG_LEARNING"]}


@router.get("/stats")
def rag_stats(include_deleted: bool = False):
  from app.services.vn_time import now_vn_iso

  checked_at = now_vn_iso()
  where_docs = "" if include_deleted else "WHERE deleted_at IS NULL"
  where_items = "" if include_deleted else "WHERE deleted_at IS NULL"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT COUNT(*) AS total FROM rag_documents {where_docs}")
      docs_total = int((cur.fetchone() or {}).get("total") or 0)
      cur.execute(f"SELECT COUNT(*) AS total FROM rag_items {where_items}")
      items_total = int((cur.fetchone() or {}).get("total") or 0)
      cur.execute(
        f"""
          SELECT domain, status, COUNT(*) AS count
          FROM rag_documents
          {where_docs}
          GROUP BY domain, status
          ORDER BY domain, status
        """
      )
      docs_by_domain_status = cur.fetchall() or []
      cur.execute(
        f"""
          SELECT domain, status, COUNT(*) AS count
          FROM rag_items
          {where_items}
          GROUP BY domain, status
          ORDER BY domain, status
        """
      )
      items_by_domain_status = cur.fetchall() or []
      cur.execute(
        f"""
          SELECT qdrant_collection, COUNT(*) AS count
          FROM rag_items
          {where_items}
          GROUP BY qdrant_collection
          ORDER BY count DESC
          LIMIT 20
        """
      )
      items_by_collection = cur.fetchall() or []

  return {
    "checked_at": checked_at,
    "documents": {"total": docs_total, "by_domain_status": docs_by_domain_status},
    "items": {"total": items_total, "by_domain_status": items_by_domain_status, "by_collection": items_by_collection},
  }


class RagSourceCreateBody(BaseModel):
  domain: str
  name: str
  description: str | None = None


class RagRequeueIofficeBody(BaseModel):
  doc_id: str
  priority: bool = True
  level1: bool = True
  level2: bool = True
  purge_existing: bool = False
  delete_qdrant: bool = False


@router.get("/sources")
def list_rag_sources(domain: str | None = None, include_distinct_from_docs: bool = True):
  from app.services.rag_sources_repo import list_sources

  try:
    items = list_sources(domain=domain, include_distinct_from_docs=bool(include_distinct_from_docs))
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
  return {"ok": True, "items": items}


@router.post("/sources")
def create_rag_source(payload: RagSourceCreateBody):
  from app.services.rag_sources_repo import create_source

  try:
    row = create_source(domain=payload.domain, name=payload.name, description=payload.description)
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
  return {"ok": True, "item": row}


@router.post("/requeue_ioffice")
def requeue_ioffice(payload: RagRequeueIofficeBody):
  from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

  did = str(payload.doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  did2 = did.split(":", 1)[1].strip() if did.lower().startswith("ioffice:") else did
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s LIMIT 1", (did2,))
      doc = cur.fetchone()
  if not doc:
    raise HTTPException(status_code=404, detail="ioffice_document_not_found")

  purge_res = {"ok": True, "skipped": True, "reason": "not_requested"}
  if bool(payload.purge_existing):
    mode = "hard" if bool(payload.delete_qdrant) else "soft"
    purge_res = ioffice_rag_ingestor.delete_all_for_ioffice_doc_id(did2, mode=mode)

  out: dict = {"ok": True, "doc_id": did2, "purge": purge_res, "queued": {}}
  if bool(payload.level1):
    out["queued"]["level1"] = ioffice_rag_ingestor.queue_level1_for_doc(doc)
  if bool(payload.level2):
    out["queued"]["level2"] = ioffice_rag_ingestor.queue_level2_for_doc(doc, domains=None, priority=bool(payload.priority))
  return out


def _safe_rel_path(path_like: str) -> str:
  s = str(path_like or "").strip().replace("\\", "/").lstrip("/")
  parts = [p for p in s.split("/") if p and p not in (".", "..")]
  return "/".join(parts)


@router.post("/upload")
async def rag_upload(domain: str = Form(...), source: str = Form(...), type: str = Form(...), file: UploadFile = File(...)):
  from app.services.rag_file_ingest import ingest_uploaded_file, save_uploaded_file

  if not file:
    raise HTTPException(status_code=400, detail="missing_file")
  data = await file.read()
  if not data:
    raise HTTPException(status_code=400, detail="empty_file")
  stored = save_uploaded_file(filename=str(file.filename or "upload.bin"), data=data)
  rel = _safe_rel_path(stored.get("rel_path") or "")
  res = ingest_uploaded_file(domain=domain, source=source, type=type, file_rel_path=rel, filename=str(file.filename or ""))
  if not isinstance(res, dict) or not res.get("ok"):
    raise HTTPException(status_code=400, detail=res or {"ok": False, "error": "ingest_failed"})
  res["view_path"] = f"/api/rag/view-file/{rel}"
  return res


@router.post("/upload-file")
async def rag_upload_file(domain: str = Form(...), source: str = Form(...), type: str = Form(...), file: UploadFile = File(...)):
  from app.services.rag_file_ingest import create_pending_document_for_file, save_uploaded_file

  if not file:
    raise HTTPException(status_code=400, detail="missing_file")
  data = await file.read()
  if not data:
    raise HTTPException(status_code=400, detail="empty_file")
  stored = save_uploaded_file(filename=str(file.filename or "upload.bin"), data=data)
  rel = _safe_rel_path(stored.get("rel_path") or "")
  res = create_pending_document_for_file(domain=domain, source=source, type=type, file_rel_path=rel, filename=str(file.filename or ""))
  if not isinstance(res, dict) or not res.get("ok"):
    raise HTTPException(status_code=400, detail=str((res or {}).get("error") or "save_failed"))
  res["view_path"] = f"/api/rag/view-file/{rel}"
  return res


class RagIngestFileBody(BaseModel):
  rag_document_id: int


@router.post("/ingest-file")
def rag_ingest_file(payload: RagIngestFileBody):
  from app.services.rag_file_ingest import ingest_saved_file

  res = ingest_saved_file(rag_document_id=int(payload.rag_document_id or 0))
  if not isinstance(res, dict) or not res.get("ok"):
    raise HTTPException(status_code=400, detail=res or {"ok": False, "error": "ingest_failed"})
  return res


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
  rid = int(doc_id or 0)
  if rid < 1:
    raise HTTPException(status_code=400, detail="invalid_doc_id")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
          SELECT
            id, domain, source, type, original_id, title,
            status, chunk_count, last_error, created_at, updated_at, deleted_at
          FROM rag_documents
          WHERE id=%s
          LIMIT 1
        """,
        (rid,),
      )
      row = cur.fetchone() or None
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  return {"ok": True, "item": row}


@router.get("/view-file/{filepath:path}")
def rag_view_file(filepath: str):
  from utils import RAG_FILES_ROOT

  rel = _safe_rel_path(filepath)
  full = (RAG_FILES_ROOT / rel).resolve()
  root = RAG_FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=400, detail="invalid_path")
  if not full.exists():
    raise HTTPException(status_code=404, detail="not_found")
  return FileResponse(str(full), filename=full.name)


@router.get("/runtime_status")
def rag_runtime_status():
  from app.services.embedding_client import embedding_runtime_info
  from app.services.ioffice_rag_worker import ioffice_rag_worker
  from app.services.vn_time import now_vn_iso

  embed = embedding_runtime_info()
  worker = ioffice_rag_worker.status()

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
          SELECT status, COUNT(*) AS count
          FROM rag_documents
          WHERE deleted_at IS NULL
          GROUP BY status
        """
      )
      docs_by_status = cur.fetchall() or []
      cur.execute(
        """
          SELECT status, COUNT(*) AS count
          FROM rag_items
          WHERE deleted_at IS NULL
          GROUP BY status
        """
      )
      items_by_status = cur.fetchall() or []
      cur.execute(
        """
          SELECT d.id AS rag_document_id, d.status AS doc_status,
                 SUM(CASE WHEN i.status='READY' THEN 1 ELSE 0 END) AS ready_count,
                 SUM(CASE WHEN i.status='EMBEDDING' THEN 1 ELSE 0 END) AS embedding_count,
                 SUM(CASE WHEN i.status='PENDING' THEN 1 ELSE 0 END) AS pending_count,
                 SUM(CASE WHEN i.status='FAILED' THEN 1 ELSE 0 END) AS failed_count,
                 COUNT(i.id) AS total_count
          FROM rag_documents d
          LEFT JOIN rag_items i
            ON i.rag_document_id=d.id AND i.deleted_at IS NULL
          WHERE d.deleted_at IS NULL AND d.status IN ('PENDING','PROCESSING','FAILED')
          GROUP BY d.id, d.status
          ORDER BY d.updated_at DESC
          LIMIT 100
        """
      )
      progress = cur.fetchall() or []

  return {
    "ok": True,
    "embedding": embed,
    "worker": worker,
    "docs_by_status": docs_by_status,
    "items_by_status": items_by_status,
    "progress": progress,
    "checked_at": now_vn_iso(),
  }


class RagDocumentCreateBody(BaseModel):
  domain: str
  source: str
  type: str
  original_id: str
  title: str | None = None
  school_id: int | None = None
  subject_id: int | None = None
  grade: int | None = None
  qdrant_collection: str | None = None
  status: str | None = None
  content_hash: str | None = None


class RagDocumentUpdateBody(BaseModel):
  title: str | None = None
  school_id: int | None = None
  subject_id: int | None = None
  grade: int | None = None
  qdrant_collection: str | None = None
  status: str | None = None
  content_hash: str | None = None
  last_error: str | None = None


def _clean_str(value: str | None) -> str:
  s = str(value or "").strip()
  return s


def _read_document_by_id(doc_id: int) -> dict | None:
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM rag_documents WHERE id=%s LIMIT 1", (int(doc_id),))
      return cur.fetchone()

def _read_item_by_id(item_id: int) -> dict | None:
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM rag_items WHERE id=%s LIMIT 1", (int(item_id),))
      return cur.fetchone()


def _chunks(seq: list, size: int) -> list[list]:
  if size <= 0:
    return [seq]
  return [seq[i : i + size] for i in range(0, len(seq), size)]


def _delete_qdrant_points(rows: list[dict]) -> dict:
  from app.services.qdrant_rest import QdrantRestClient

  by_collection: dict[str, list[str | int]] = {}
  for r in rows or []:
    col = str((r or {}).get("qdrant_collection") or "").strip()
    pid = (r or {}).get("qdrant_point_id")
    if not col or pid is None or str(pid).strip() == "":
      continue
    by_collection.setdefault(col, []).append(pid)

  if not by_collection:
    return {"ok": True, "deleted_points": 0, "collections": [], "errors": []}

  client = QdrantRestClient()
  deleted_points = 0
  errors: list[str] = []
  for col, ids in by_collection.items():
    for batch in _chunks(ids, 256):
      try:
        client.delete_points(collection=col, point_ids=batch)
        deleted_points += len(batch)
      except Exception as e:
        errors.append(f"{col}: {str(e)}")
  return {"ok": len(errors) == 0, "deleted_points": deleted_points, "collections": sorted(by_collection.keys()), "errors": errors}



@router.get("/documents")
def list_documents(
  limit: int = Query(20, ge=1, le=200),
  offset: int = Query(0, ge=0),
  keyword: str | None = None,
  domain: str | None = None,
  status: str | None = None,
  source: str | None = None,
  type: str | None = None,
  include_deleted: bool = False,
):
  kw = _clean_str(keyword)
  conditions: list[str] = []
  params: list[object] = []
  if not include_deleted:
    conditions.append("deleted_at IS NULL")
  if kw:
    conditions.append("(title LIKE %s OR original_id LIKE %s OR source LIKE %s OR type LIKE %s)")
    like = f"%{kw}%"
    params.extend([like, like, like, like])
  if domain:
    conditions.append("domain=%s")
    params.append(_clean_str(domain).upper())
  if status:
    conditions.append("status=%s")
    params.append(_clean_str(status).upper())
  if source:
    conditions.append("source=%s")
    params.append(_clean_str(source))
  if type:
    conditions.append("type=%s")
    params.append(_clean_str(type))

  where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT COUNT(*) AS total FROM rag_documents {where_sql}", tuple(params))
      total = int((cur.fetchone() or {}).get("total") or 0)
      cur.execute(
        f"""
          SELECT
            id, domain, source, type, original_id, title,
            school_id, subject_id, grade,
            qdrant_collection, status, content_hash, chunk_count,
            last_indexed_at, last_error,
            created_at, updated_at, deleted_at
          FROM rag_documents
          {where_sql}
          ORDER BY updated_at DESC, id DESC
          LIMIT %s OFFSET %s
        """,
        tuple(params + [int(limit), int(offset)]),
      )
      items = cur.fetchall() or []
  try:
    from pathlib import Path

    from utils import RAG_FILES_ROOT

    root = Path(RAG_FILES_ROOT).resolve()
    for it in items:
      if not isinstance(it, dict):
        continue
      oid = str(it.get("original_id") or "").strip()
      if not oid.lower().startswith("file:"):
        continue
      rel = oid.split("file:", 1)[1].strip().replace("\\", "/").lstrip("/")
      it["file_rel_path"] = rel
      try:
        full = (root / rel).resolve()
        if not str(full).startswith(str(root)):
          it["file_exists"] = False
          continue
        it["file_exists"] = bool(full.exists())
        it["file_size"] = int(full.stat().st_size) if full.exists() else None
      except Exception:
        it["file_exists"] = False
        it["file_size"] = None
  except Exception:
    pass
  return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/documents")
def create_document(payload: RagDocumentCreateBody):
  from app.services.rag_conventions import collection_for_domain

  domain = _clean_str(payload.domain).upper()
  source = _clean_str(payload.source)
  type_ = _clean_str(payload.type)
  original_id = _clean_str(payload.original_id)
  if not domain or not source or not type_ or not original_id:
    raise HTTPException(status_code=400, detail="missing_required_fields")
  qdrant_collection = _clean_str(payload.qdrant_collection) or collection_for_domain(domain)
  status = _clean_str(payload.status).upper() or "PENDING"

  sql = """
    INSERT INTO rag_documents
      (domain, source, type, original_id, title, school_id, subject_id, grade, qdrant_collection, status, content_hash)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
  """
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          sql,
          (
            domain,
            source,
            type_,
            original_id,
            payload.title,
            payload.school_id,
            payload.subject_id,
            payload.grade,
            qdrant_collection,
            status,
            payload.content_hash,
          ),
        )
        doc_id = int(cur.lastrowid)
    row = _read_document_by_id(doc_id)
    return {"item": row}
  except pymysql.err.IntegrityError as e:
    if int(getattr(e, "args", [0])[0] or 0) == 1062:
      raise HTTPException(status_code=409, detail="duplicate_document")
    raise HTTPException(status_code=400, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.put("/documents/{doc_id}")
def update_document(doc_id: int, payload: RagDocumentUpdateBody):
  fields: list[str] = []
  params: list[object] = []
  if payload.title is not None:
    fields.append("title=%s")
    params.append(payload.title)
  if payload.school_id is not None:
    fields.append("school_id=%s")
    params.append(payload.school_id)
  if payload.subject_id is not None:
    fields.append("subject_id=%s")
    params.append(payload.subject_id)
  if payload.grade is not None:
    fields.append("grade=%s")
    params.append(payload.grade)
  if payload.qdrant_collection is not None:
    fields.append("qdrant_collection=%s")
    params.append(_clean_str(payload.qdrant_collection))
  if payload.status is not None:
    fields.append("status=%s")
    params.append(_clean_str(payload.status).upper())
  if payload.content_hash is not None:
    fields.append("content_hash=%s")
    params.append(_clean_str(payload.content_hash) or None)
  if payload.last_error is not None:
    fields.append("last_error=%s")
    params.append(payload.last_error)
  if not fields:
    row = _read_document_by_id(doc_id)
    if not row:
      raise HTTPException(status_code=404, detail="not_found")
    return {"item": row}

  sql = f"UPDATE rag_documents SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=%s"
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, tuple(params + [int(doc_id)]))
    row = _read_document_by_id(doc_id)
    if not row:
      raise HTTPException(status_code=404, detail="not_found")
    return {"item": row}
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, purge_items: bool = True, delete_qdrant: bool = False):
  doc = _read_document_by_id(doc_id)
  qdrant_result: dict | None = None
  if delete_qdrant and doc:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          """
            SELECT qdrant_collection, qdrant_point_id
            FROM rag_items
            WHERE
              deleted_at IS NULL
              AND (
                rag_document_id=%s
                OR (rag_document_id IS NULL AND domain=%s AND source=%s AND type=%s AND original_id=%s)
              )
          """,
          (int(doc_id), doc.get("domain"), doc.get("source"), doc.get("type"), doc.get("original_id")),
        )
        rows = cur.fetchall() or []
    qdrant_result = _delete_qdrant_points(rows)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
          UPDATE rag_documents
          SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
          WHERE id=%s
        """,
        (int(doc_id),),
      )
      if purge_items:
        if doc:
          cur.execute(
            """
              UPDATE rag_items
              SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
              WHERE
                rag_document_id=%s
                OR (rag_document_id IS NULL AND domain=%s AND source=%s AND type=%s AND original_id=%s)
            """,
            (int(doc_id), doc.get("domain"), doc.get("source"), doc.get("type"), doc.get("original_id")),
          )
        else:
          cur.execute(
            """
              UPDATE rag_items
              SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
              WHERE rag_document_id=%s
            """,
            (int(doc_id),),
          )
  return {"ok": True, "qdrant": qdrant_result}


@router.get("/items")
def list_items(
  limit: int = Query(50, ge=1, le=200),
  offset: int = Query(0, ge=0),
  keyword: str | None = None,
  domain: str | None = None,
  status: str | None = None,
  qdrant_collection: str | None = None,
  rag_document_id: int | None = None,
  include_deleted: bool = False,
):
  kw = _clean_str(keyword)
  conditions: list[str] = []
  params: list[object] = []
  if not include_deleted:
    conditions.append("deleted_at IS NULL")
  if kw:
    conditions.append("(title LIKE %s OR original_id LIKE %s OR qdrant_point_id LIKE %s OR qdrant_collection LIKE %s)")
    like = f"%{kw}%"
    params.extend([like, like, like, like])
  if domain:
    conditions.append("domain=%s")
    params.append(_clean_str(domain).upper())
  if status:
    conditions.append("status=%s")
    params.append(_clean_str(status).upper())
  if qdrant_collection:
    conditions.append("qdrant_collection=%s")
    params.append(_clean_str(qdrant_collection))
  if rag_document_id is not None:
    conditions.append("rag_document_id=%s")
    params.append(int(rag_document_id))

  where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT COUNT(*) AS total FROM rag_items {where_sql}", tuple(params))
      total = int((cur.fetchone() or {}).get("total") or 0)
      cur.execute(
        f"""
          SELECT
            id, rag_document_id,
            domain, source, type, title, original_id,
            chunk_index, qdrant_collection, qdrant_point_id,
            status, chunk_tokens, content_hash, embedded_at, last_error,
            created_at, updated_at, deleted_at
          FROM rag_items
          {where_sql}
          ORDER BY updated_at DESC, id DESC
          LIMIT %s OFFSET %s
        """,
        tuple(params + [int(limit), int(offset)]),
      )
      items = cur.fetchall() or []
  return {"items": items, "total": total, "limit": limit, "offset": offset}


class RagItemUpdateBody(BaseModel):
  status: str | None = None
  chunk_tokens: int | None = None
  last_error: str | None = None


@router.put("/items/{item_id}")
def update_item(item_id: int, payload: RagItemUpdateBody):
  fields: list[str] = []
  params: list[object] = []
  if payload.status is not None:
    fields.append("status=%s")
    params.append(_clean_str(payload.status).upper())
  if payload.chunk_tokens is not None:
    fields.append("chunk_tokens=%s")
    params.append(int(payload.chunk_tokens))
  if payload.last_error is not None:
    fields.append("last_error=%s")
    params.append(payload.last_error)
  if not fields:
    row = _read_item_by_id(item_id)
    if not row:
      raise HTTPException(status_code=404, detail="not_found")
    return {"item": row}

  sql = f"UPDATE rag_items SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=%s"
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, tuple(params + [int(item_id)]))
    row = _read_item_by_id(item_id)
    if not row:
      raise HTTPException(status_code=404, detail="not_found")
    return {"item": row}
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.delete("/items/{item_id}")
def delete_item(item_id: int, delete_qdrant: bool = False):
  item = _read_item_by_id(item_id)
  if not item:
    raise HTTPException(status_code=404, detail="not_found")
  qdrant_result: dict | None = None
  if delete_qdrant:
    qdrant_result = _delete_qdrant_points([{"qdrant_collection": item.get("qdrant_collection"), "qdrant_point_id": item.get("qdrant_point_id")}])

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
          UPDATE rag_items
          SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
          WHERE id=%s
        """,
        (int(item_id),),
      )
  return {"ok": True, "qdrant": qdrant_result}


@router.get("/documents/{doc_id}/items")
def list_document_items(
  doc_id: int,
  limit: int = Query(50, ge=1, le=200),
  offset: int = Query(0, ge=0),
  status: str | None = None,
  include_deleted: bool = False,
):
  doc = _read_document_by_id(doc_id)
  if not doc:
    raise HTTPException(status_code=404, detail="not_found")

  conditions = [
    "(rag_document_id=%s OR (rag_document_id IS NULL AND domain=%s AND source=%s AND type=%s AND original_id=%s))"
  ]
  params: list[object] = [int(doc_id), doc.get("domain"), doc.get("source"), doc.get("type"), doc.get("original_id")]
  if not include_deleted:
    conditions.append("deleted_at IS NULL")
  if status:
    conditions.append("status=%s")
    params.append(_clean_str(status).upper())
  where_sql = f"WHERE {' AND '.join(conditions)}"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT COUNT(*) AS total FROM rag_items {where_sql}", tuple(params))
      total = int((cur.fetchone() or {}).get("total") or 0)
      cur.execute(
        f"""
          SELECT
            id, rag_document_id,
            domain, source, type, title, original_id,
            chunk_index, qdrant_collection, qdrant_point_id,
            status, chunk_tokens, content_hash, embedded_at, last_error,
            created_at, updated_at, deleted_at
          FROM rag_items
          {where_sql}
          ORDER BY chunk_index ASC, id ASC
          LIMIT %s OFFSET %s
        """,
        tuple(params + [int(limit), int(offset)]),
      )
      items = cur.fetchall() or []
  return {"items": items, "total": total, "limit": limit, "offset": offset}


class RagImportIofficeDocBody(BaseModel):
  document_id: int | None = None
  ioffice_doc_id: str | None = None
  require_ready_summary: bool = True
  fulltext: bool = False


def _queue_ioffice_document(doc: dict) -> dict:
  from app.services.rag_conventions import collection_for_domain
  from app.services.rag_mapping_repo import RagMappingRepo

  ioffice_doc_id = str((doc.get("ioffice_doc_id") or "")).strip()
  if ioffice_doc_id.lower().startswith("ioffice:"):
    ioffice_doc_id = ioffice_doc_id.split(":", 1)[1].strip()
  if not ioffice_doc_id:
    raise HTTPException(status_code=400, detail="missing_ioffice_doc_id")
  repo = RagMappingRepo()
  rid = repo.upsert_document(
    domain="MANAGEMENT",
    source="IOFFICE",
    type="official_document_summary",
    original_id=f"ioffice:{ioffice_doc_id}",
    title=(str((doc.get("trich_yeu") or "")).strip() or None),
    school_id=doc.get("school_id") if doc.get("school_id") is not None else None,
    subject_id=None,
    grade=None,
    qdrant_collection=collection_for_domain("MANAGEMENT"),
    status="PENDING",
    content_hash=(str((doc.get("content_hash") or "")).strip() or None),
  )
  return {"ok": True, "queued": True, "rag_document_id": rid}


@router.post("/import/ioffice/document")
def import_ioffice_document(payload: RagImportIofficeDocBody):
  from app.services.ioffice_rag import index_ioffice_summary
  from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

  doc_id = int(payload.document_id) if payload.document_id is not None else 0
  ioffice_doc_id = _clean_str(payload.ioffice_doc_id)
  if not doc_id and not ioffice_doc_id:
    raise HTTPException(status_code=400, detail="missing_document_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      if doc_id:
        cur.execute("SELECT * FROM ioffice_documents WHERE id=%s LIMIT 1", (int(doc_id),))
      else:
        cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s LIMIT 1", (ioffice_doc_id,))
      doc = cur.fetchone()
      if not doc and not doc_id and ioffice_doc_id:
        alt = f"ioffice:{ioffice_doc_id}" if not ioffice_doc_id.lower().startswith("ioffice:") else ioffice_doc_id.split(":", 1)[1].strip()
        cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s LIMIT 1", (alt,))
        doc = cur.fetchone()
  if not doc:
    raise HTTPException(status_code=404, detail="ioffice_document_not_found")
  summary_ready = str((doc.get("summary_status") or "")).upper() == "READY" and bool(str((doc.get("summary_text") or "")).strip())
  summary_required = bool(payload.require_ready_summary)
  want_fulltext = bool(payload.fulltext)

  try:
    summary_res: dict | None = None
    if summary_ready:
      res = index_ioffice_summary(doc)
      if isinstance(res, dict) and res.get("skipped") and res.get("reason") in ("disabled", "embedding_unavailable"):
        queued = _queue_ioffice_document(doc)
        queued["reason"] = res.get("reason")
        summary_res = queued
      else:
        summary_res = res if isinstance(res, dict) else {"ok": True}
    else:
      summary_res = {"ok": True, "skipped": True, "reason": ("ioffice_summary_not_ready" if summary_required else "summary_missing")}

    level2_res: dict | None = None
    if want_fulltext:
      try:
        level2_res = ioffice_rag_ingestor.queue_level2_for_doc(doc, domains=None, priority=False)
      except Exception:
        level2_res = {"ok": False, "error": "queue_failed"}
    else:
      level2_res = {"ok": True, "skipped": True, "reason": "fulltext_disabled"}

    return {"ok": True, "level1": summary_res, "level2": level2_res}
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


class RagImportIofficeCategoryBody(BaseModel):
  category_id: int
  include_children: bool = False
  limit: int = 200
  require_ready_summary: bool = True
  fulltext: bool = False


def _descendant_category_ids(root_id: int) -> list[int]:
  root_id = int(root_id)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT id, parent_id FROM document_categories")
      rows = cur.fetchall() or []
  by_parent: dict[int, list[int]] = {}
  for r in rows:
    cid = int(r.get("id") or 0)
    pid = int(r.get("parent_id") or 0)
    if not cid:
      continue
    by_parent.setdefault(pid, []).append(cid)

  out: list[int] = []
  stack = [root_id]
  seen: set[int] = set()
  while stack:
    cid = stack.pop()
    if cid in seen:
      continue
    seen.add(cid)
    out.append(cid)
    for kid in by_parent.get(cid, []):
      stack.append(int(kid))
  return out


@router.post("/import/ioffice/category")
def import_ioffice_category(payload: RagImportIofficeCategoryBody, x_user_id: str | None = Header(default=None)):
  from app.services.ioffice_rag import index_ioffice_summary
  from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

  category_id = int(payload.category_id)
  limit = int(payload.limit or 200)
  if limit < 1:
    limit = 1
  if limit > 2000:
    limit = 2000

  category_ids = [category_id]
  if bool(payload.include_children):
    category_ids = _descendant_category_ids(category_id)

  placeholders = ",".join(["%s"] * len(category_ids))
  sql = f"""
    SELECT d.*
    FROM document_category_items i
    JOIN ioffice_documents d ON d.id=i.ioffice_document_id
    WHERE i.category_id IN ({placeholders})
    ORDER BY d.updated_at DESC, d.id DESC
    LIMIT %s
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(category_ids + [limit]))
      docs = cur.fetchall() or []

  indexed = 0
  skipped = 0
  fulltext_queued = 0
  errors: list[dict] = []
  results: list[dict] = []
  for doc in docs:
    summary_ready = str((doc.get("summary_status") or "")).upper() == "READY" and bool(str((doc.get("summary_text") or "")).strip())
    summary_required = bool(payload.require_ready_summary)
    want_fulltext = bool(payload.fulltext)
    try:
      level1: dict | None = None
      if summary_ready:
        res = index_ioffice_summary(doc)
        if isinstance(res, dict) and res.get("skipped") and res.get("reason") in ("disabled", "embedding_unavailable"):
          queued = _queue_ioffice_document(doc)
          queued["reason"] = res.get("reason")
          level1 = queued
        else:
          level1 = res if isinstance(res, dict) else {"ok": True}
      else:
        level1 = {"ok": True, "skipped": True, "reason": ("ioffice_summary_not_ready" if summary_required else "summary_missing")}

      level2: dict | None = None
      if want_fulltext:
        try:
          level2 = ioffice_rag_ingestor.queue_level2_for_doc(doc, domains=None, priority=False)
          if isinstance(level2, dict) and level2.get("queued"):
            fulltext_queued += 1
        except Exception:
          level2 = {"ok": False, "error": "queue_failed"}
      else:
        level2 = {"ok": True, "skipped": True, "reason": "fulltext_disabled"}

      results.append({"ioffice_id": doc.get("id"), "ok": True, "level1": level1, "level2": level2})
      if level1 and isinstance(level1, dict) and level1.get("skipped"):
        skipped += 1
      else:
        indexed += 1
    except Exception as e:
      errors.append({"ioffice_id": doc.get("id"), "error": str(e)})
      results.append({"ioffice_id": doc.get("id"), "ok": False, "error": str(e)})

  return {
    "ok": len(errors) == 0,
    "category_id": category_id,
    "category_ids": category_ids,
    "limit": limit,
    "total_docs": len(docs),
    "indexed": indexed,
    "skipped": skipped,
    "fulltext_queued": fulltext_queued,
    "errors": errors,
    "results": results[:200],
    "user_id": x_user_id,
  }
