import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.db import get_db_connection
from app.services.embedding_client import embed_text_query, embed_texts_document, embedding_available
from app.services.ioffice_rag import SOURCE_IOFFICE, TYPE_IOFFICE_CHUNK, TYPE_IOFFICE_SUMMARY, index_ioffice_summary
from app.services.qdrant_rest import QdrantRestClient
from app.services.rag_conventions import build_payload, collection_for_domain
from app.services.rag_mapping_repo import RagMappingRepo
from utils import FILES_ROOT, make_safe_relative_from_any
from ai_summary_compat import extract_text_from_zip_selected


@dataclass(frozen=True)
class FulltextChunkingConfig:
  chunk_chars: int = 1400
  overlap_chars: int = 200
  min_chunk_chars: int = 200
  max_total_chars: int = 500_000


def _env_int(name: str, default: int) -> int:
  try:
    return int((os.getenv(name) or "").strip() or str(default))
  except Exception:
    return default


def _env_bool(name: str, default: bool) -> bool:
  try:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
      return default
    return v not in ("0", "false", "no", "off")
  except Exception:
    return default


def _chunking_cfg() -> FulltextChunkingConfig:
  return FulltextChunkingConfig(
    chunk_chars=max(300, _env_int("EDUAI_IOFFICE_RAG_CHUNK_CHARS", 1400)),
    overlap_chars=max(0, _env_int("EDUAI_IOFFICE_RAG_OVERLAP_CHARS", 200)),
    min_chunk_chars=max(50, _env_int("EDUAI_IOFFICE_RAG_MIN_CHUNK_CHARS", 200)),
    max_total_chars=max(10_000, _env_int("EDUAI_IOFFICE_RAG_MAX_TOTAL_CHARS", 500_000)),
  )


def _safe_load_json(text: str) -> dict:
  try:
    val = json.loads(text)
    return val if isinstance(val, dict) else {}
  except Exception:
    return {}


def _category_domain_map() -> dict[str, list[str]]:
  raw = (os.getenv("EDUAI_RAG_CATEGORY_DOMAIN_MAP") or "").strip()
  if not raw:
    return {}
  m = _safe_load_json(raw)
  out: dict[str, list[str]] = {}
  for k, v in m.items():
    kk = str(k).strip()
    if not kk:
      continue
    if isinstance(v, list):
      domains = [str(x).strip().upper() for x in v if str(x).strip()]
    else:
      domains = [str(v).strip().upper()] if str(v).strip() else []
    domains = [d for d in domains if d in ("MANAGEMENT", "TEACHING", "LEARNING")]
    if domains:
      out[kk] = domains
  return out


def _domains_from_category_ids(category_ids: list[int]) -> list[str]:
  m = _category_domain_map()
  desired: list[str] = []
  for cid in category_ids:
    key = str(int(cid))
    domains = m.get(key)
    if domains:
      desired.extend(domains)
  if not desired:
    desired = ["MANAGEMENT"]
  uniq: list[str] = []
  seen: set[str] = set()
  for d in desired:
    dd = str(d or "").strip().upper()
    if not dd or dd in seen:
      continue
    seen.add(dd)
    uniq.append(dd)
  return uniq


def _ioffice_doc_id_from_original_id(original_id: str) -> str:
  oid = str(original_id or "").strip()
  if oid.lower().startswith("ioffice:"):
    return oid.split(":", 1)[1].strip()
  return oid


def _extract_text_from_file(file_path: str, *, selected_members: list[str] | None) -> str:
  p = (file_path or "").strip()
  if not p:
    return ""
  safe = make_safe_relative_from_any(p)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    return ""
  if not full.exists():
    return ""
  ext = full.suffix.lower()
  if ext == ".zip":
    return extract_text_from_zip_selected(full, selected_members)
  if ext in (".txt", ".md", ".html", ".htm"):
    try:
      raw = full.read_bytes()
      for enc in ("utf-8", "utf-16", "cp1258", "cp1252", "latin-1"):
        try:
          val = raw.decode(enc, errors="replace").replace("\x00", "").strip()
          if val and val.count("\ufffd") / max(1, len(val)) < 0.03:
            return val
        except Exception:
          continue
      return raw.decode("utf-8", errors="ignore").replace("\x00", "").strip()
    except Exception:
      return ""
  if ext == ".docx":
    try:
      import zipfile
      import re
      from io import BytesIO

      data = full.read_bytes()
      with zipfile.ZipFile(BytesIO(data)) as dz:
        xml = dz.read("word/document.xml")
      s = xml.decode("utf-8", errors="ignore")
      s = re.sub(r"<[^>]+>", " ", s)
      s = re.sub(r"\s+", " ", s)
      return s.strip()
    except Exception:
      return ""
  if ext == ".pdf":
    try:
      import pypdf

      reader = pypdf.PdfReader(str(full))
      texts = []
      has_text = False
      for pg in reader.pages:
        t = pg.extract_text() or ""
        if t.strip():
          texts.append(t)
          if len(t.strip()) > 50: # Heuristic: if page has >50 chars, assume it's text
              has_text = True
      
      combined_text = "\n".join(texts).strip()
      
      # If pypdf failed to extract meaningful text, try OCR fallback
      if not has_text or not combined_text:
          print(f"PDF text extraction empty for {full.name}, attempting OCR fallback...")
          try:
              # Check if pytesseract is available
              import pytesseract
              from pdf2image import convert_from_path
              
              # Convert PDF to images
              images = convert_from_path(str(full))
              ocr_texts = []
              for img in images:
                  # Run OCR on each page image
                  # Use Vietnamese and English language data
                  page_text = pytesseract.image_to_string(img, lang='vie+eng')
                  if page_text.strip():
                      ocr_texts.append(page_text)
              
              ocr_combined = "\n".join(ocr_texts).strip()
              if ocr_combined:
                  return ocr_combined
          except ImportError:
              print("OCR dependencies (pytesseract, pdf2image) not found. Skipping OCR.")
          except Exception as e:
              print(f"OCR failed for {full.name}: {e}")
              
      return combined_text
    except Exception:
      return ""
  return ""


def _chunk_text(text: str, cfg: FulltextChunkingConfig) -> list[str]:
  t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
  if not t:
    return []
  if len(t) > cfg.max_total_chars:
    t = t[: cfg.max_total_chars]
  parts = [p.strip() for p in t.split("\n\n") if p and p.strip()]
  if not parts:
    parts = [t]
  chunks: list[str] = []
  buf = ""
  for p in parts:
    if not buf:
      buf = p
      continue
    if len(buf) + 2 + len(p) <= cfg.chunk_chars:
      buf = f"{buf}\n\n{p}"
    else:
      chunks.append(buf.strip())
      buf = p
  if buf.strip():
    chunks.append(buf.strip())

  out: list[str] = []
  overlap = max(0, cfg.overlap_chars)
  for c in chunks:
    c2 = c.strip()
    if not c2:
      continue
    if len(c2) <= cfg.chunk_chars:
      out.append(c2)
      continue
    start = 0
    while start < len(c2):
      end = min(len(c2), start + cfg.chunk_chars)
      piece = c2[start:end].strip()
      if piece and len(piece) >= cfg.min_chunk_chars:
        out.append(piece)
      if end >= len(c2):
        break
      start = max(0, end - overlap)
  return out


def _hash_fulltext(text: str, *, cfg: FulltextChunkingConfig, embed_model: str) -> str:
  h = hashlib.sha256()
  h.update((text or "").encode("utf-8"))
  h.update(f"|chunk_chars={cfg.chunk_chars}|overlap={cfg.overlap_chars}|min={cfg.min_chunk_chars}|model={embed_model}".encode("utf-8"))
  return h.hexdigest()


class IOfficeRagIngestor:
  def __init__(self) -> None:
    self._priority_lock = threading.Lock()
    self._priority_original_ids: list[str] = []

  def request_level2_for_doc_ids(self, doc_ids: list[str], *, priority: bool) -> None:
    ids = [str(x or "").strip() for x in (doc_ids or []) if str(x or "").strip()]
    if not ids:
      return
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT * FROM ioffice_documents WHERE ioffice_doc_id IN ({placeholders})", tuple(ids))
        rows = cur.fetchall() or []
    for doc in rows:
      self.queue_level2_for_doc(doc, domains=None, priority=priority)

  def queue_level2_for_doc_id(self, document_row_id: int, *, priority: bool) -> dict:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT * FROM ioffice_documents WHERE id=%s LIMIT 1", (int(document_row_id),))
        doc = cur.fetchone()
    if not doc:
      return {"ok": False, "error": "ioffice_document_not_found"}
    return self.queue_level2_for_doc(doc, domains=None, priority=priority)

  def queue_level2_for_doc(self, doc: dict, *, domains: list[str] | None, priority: bool) -> dict:
    ioffice_doc_id = str((doc.get("ioffice_doc_id") or "")).strip()
    if ioffice_doc_id.lower().startswith("ioffice:"):
      ioffice_doc_id = ioffice_doc_id.split(":", 1)[1].strip()
    if not ioffice_doc_id:
      return {"ok": False, "error": "missing_doc_id"}
    original_id = f"ioffice:{ioffice_doc_id}"

    if domains is None:
      try:
        doc_row_id = int(doc.get("id") or 0)
      except Exception:
        doc_row_id = 0
      domains = self._desired_domains_for_document_row(doc_row_id) if doc_row_id else ["MANAGEMENT"]
    domains2 = [str(d).strip().upper() for d in (domains or []) if str(d).strip()]
    if not domains2:
      domains2 = ["MANAGEMENT"]

    repo = RagMappingRepo()
    queued_ids: list[int] = []
    for domain in domains2:
      col = collection_for_domain(domain)
      rid = repo.upsert_document(
        domain=domain,
        source=SOURCE_IOFFICE,
        type=TYPE_IOFFICE_CHUNK,
        original_id=original_id,
        title=(str((doc.get("trich_yeu") or "")).strip() or None),
        school_id=doc.get("school_id") if doc.get("school_id") is not None else None,
        subject_id=None,
        grade=None,
        qdrant_collection=col,
        status="PENDING",
        content_hash=None,
      )
      queued_ids.append(int(rid))
    if priority:
      with self._priority_lock:
        if original_id not in self._priority_original_ids:
          self._priority_original_ids.insert(0, original_id)
    return {"ok": True, "queued": True, "rag_document_ids": queued_ids, "original_id": original_id, "domains": domains2}

  def ensure_level1_summary(self, doc: dict) -> dict:
    return index_ioffice_summary(doc, domain="MANAGEMENT")

  def queue_level1_for_doc_id(self, document_row_id: int) -> dict:
    if not _env_bool("EDUAI_IOFFICE_RAG_ENABLED", True):
      return {"ok": True, "skipped": True, "reason": "level1_disabled"}
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT * FROM ioffice_documents WHERE id=%s LIMIT 1", (int(document_row_id),))
        doc = cur.fetchone()
    if not doc:
      return {"ok": False, "error": "ioffice_document_not_found"}
    return self.queue_level1_for_doc(doc)

  def queue_level1_for_doc(self, doc: dict) -> dict:
    if not _env_bool("EDUAI_IOFFICE_RAG_ENABLED", True):
      return {"ok": True, "skipped": True, "reason": "level1_disabled"}
    ioffice_doc_id = str((doc.get("ioffice_doc_id") or "")).strip()
    if ioffice_doc_id.lower().startswith("ioffice:"):
      ioffice_doc_id = ioffice_doc_id.split(":", 1)[1].strip()
    if not ioffice_doc_id:
      return {"ok": False, "error": "missing_doc_id"}
    original_id = f"ioffice:{ioffice_doc_id}"
    repo = RagMappingRepo()
    rid = repo.upsert_document(
      domain="MANAGEMENT",
      source=SOURCE_IOFFICE,
      type=TYPE_IOFFICE_SUMMARY,
      original_id=original_id,
      title=(str((doc.get("trich_yeu") or "")).strip() or None),
      school_id=doc.get("school_id") if doc.get("school_id") is not None else None,
      subject_id=None,
      grade=None,
      qdrant_collection=collection_for_domain("MANAGEMENT"),
      status="PENDING",
      content_hash=(str((doc.get("content_hash") or "")).strip() or None),
    )
    return {"ok": True, "queued": True, "rag_document_id": int(rid), "original_id": original_id}

  def prune_level2_for_document_row(self, document_row_id: int, *, delete_qdrant: bool) -> dict:
    if not document_row_id:
      return {"ok": True, "skipped": True, "reason": "missing_document_row_id"}
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT ioffice_doc_id FROM ioffice_documents WHERE id=%s LIMIT 1", (int(document_row_id),))
        row = cur.fetchone()
    if not row:
      return {"ok": True, "skipped": True, "reason": "ioffice_document_not_found"}
    ioffice_doc_id = str((row.get("ioffice_doc_id") or "")).strip()
    if ioffice_doc_id.lower().startswith("ioffice:"):
      ioffice_doc_id = ioffice_doc_id.split(":", 1)[1].strip()
    if not ioffice_doc_id:
      return {"ok": True, "skipped": True, "reason": "missing_doc_id"}
    original_id = f"ioffice:{ioffice_doc_id}"

    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT category_id FROM document_category_items WHERE ioffice_document_id=%s", (int(document_row_id),))
        rows = cur.fetchall() or []
    category_ids: list[int] = []
    for r in rows:
      try:
        category_ids.append(int(r.get("category_id") or 0))
      except Exception:
        continue
    category_ids = [x for x in category_ids if x > 0]
    desired_domains = _domains_from_category_ids(category_ids) if category_ids else []

    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          """
          SELECT id, domain, qdrant_collection, original_id
          FROM rag_documents
          WHERE deleted_at IS NULL AND source=%s AND type=%s AND original_id=%s
          """,
          (SOURCE_IOFFICE, TYPE_IOFFICE_CHUNK, original_id),
        )
        docs = cur.fetchall() or []

    removed: list[int] = []
    for d in docs:
      dom = str((d.get("domain") or "")).strip().upper()
      rid = int(d.get("id") or 0)
      if not rid:
        continue
      if desired_domains and dom in desired_domains:
        continue
      self.delete_rag_document(rid, delete_qdrant=delete_qdrant)
      removed.append(rid)

    return {"ok": True, "removed_rag_document_ids": removed, "desired_domains": desired_domains, "original_id": original_id}

  def delete_rag_document(self, rag_document_id: int, *, delete_qdrant: bool) -> dict:
    rid = int(rag_document_id or 0)
    if not rid:
      return {"ok": False, "error": "missing_rag_document_id"}
    qdrant_result = None
    if delete_qdrant:
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(
            "SELECT qdrant_collection, qdrant_point_id FROM rag_items WHERE deleted_at IS NULL AND rag_document_id=%s",
            (int(rid),),
          )
          rows = cur.fetchall() or []
      qdrant = QdrantRestClient()
      deleted = 0
      errors: list[str] = []
      by_collection: dict[str, list[str | int]] = {}
      for r in rows:
        col = str((r or {}).get("qdrant_collection") or "").strip()
        pid = (r or {}).get("qdrant_point_id")
        if not col or pid is None or str(pid).strip() == "":
          continue
        by_collection.setdefault(col, []).append(pid)
      for col, ids in by_collection.items():
        for i in range(0, len(ids), 256):
          batch = ids[i : i + 256]
          try:
            qdrant.delete_points(collection=col, point_ids=batch)
            deleted += len(batch)
          except Exception as e:
            errors.append(f"{col}: {str(e)}")
      qdrant_result = {"ok": len(errors) == 0, "deleted_points": deleted, "collections": sorted(by_collection.keys()), "errors": errors}

    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "UPDATE rag_documents SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
          (int(rid),),
        )
        cur.execute(
          "UPDATE rag_items SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE rag_document_id=%s",
          (int(rid),),
        )
    return {"ok": True, "qdrant": qdrant_result}

  def delete_all_for_ioffice_doc_id(self, ioffice_doc_id: str, *, mode: str) -> dict:
    did = str(ioffice_doc_id or "").strip()
    if did.lower().startswith("ioffice:"):
      did = did.split(":", 1)[1].strip()
    if not did:
      return {"ok": False, "error": "missing_doc_id"}
    original_id = f"ioffice:{did}"
    delete_qdrant = str(mode or "").strip().lower() in ("hard", "purge", "qdrant")

    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "SELECT id FROM rag_documents WHERE deleted_at IS NULL AND source=%s AND original_id=%s",
          (SOURCE_IOFFICE, original_id),
        )
        rows = cur.fetchall() or []
    ids = [int(r.get("id") or 0) for r in rows if int(r.get("id") or 0) > 0]
    out: list[int] = []
    for rid in ids:
      try:
        self.delete_rag_document(rid, delete_qdrant=delete_qdrant)
        out.append(rid)
      except Exception:
        continue
    return {"ok": True, "deleted_rag_document_ids": out, "original_id": original_id, "delete_qdrant": delete_qdrant}

  def pop_priority_original_id(self) -> str | None:
    with self._priority_lock:
      if not self._priority_original_ids:
        return None
      return self._priority_original_ids.pop(0)

  def _desired_domains_for_document_row(self, document_row_id: int) -> list[str]:
    if not document_row_id:
      return ["MANAGEMENT"]
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT category_id FROM document_category_items WHERE ioffice_document_id=%s", (int(document_row_id),))
        rows = cur.fetchall() or []
    category_ids: list[int] = []
    for r in rows:
      try:
        category_ids.append(int(r.get("category_id") or 0))
      except Exception:
        continue
    category_ids = [x for x in category_ids if x > 0]
    return _domains_from_category_ids(category_ids)

  def process_one_pending_fulltext(self, *, original_id: str | None = None) -> dict:
    doc_row = self._pick_pending_doc(original_id=original_id)
    if not doc_row:
      return {"ok": True, "skipped": True, "reason": "no_pending"}

    domain = str(doc_row.get("domain") or "").strip().upper()
    rag_doc_id = int(doc_row.get("id") or 0)
    oid = str(doc_row.get("original_id") or "").strip()
    ioffice_doc_id = _ioffice_doc_id_from_original_id(oid)
    if not rag_doc_id or not domain or not ioffice_doc_id:
      return {"ok": False, "error": "invalid_rag_document"}

    if not _env_bool("EDUAI_IOFFICE_RAG_LEVEL2_ENABLED", True):
      self._mark_rag_doc_failed(rag_doc_id, "level2_disabled")
      return {"ok": True, "skipped": True, "reason": "level2_disabled", "rag_document_id": rag_doc_id}
    if not embedding_available():
      self._mark_rag_doc_failed(rag_doc_id, "embedding_unavailable")
      return {"ok": False, "error": "embedding_unavailable", "rag_document_id": rag_doc_id}

    # Support for manual upload: if original_id starts with 'file:manual/',
    # we should check rag_documents for title/path instead of querying ioffice_documents.
    # Manual uploads don't exist in ioffice_documents table.
    doc = None
    is_manual = str(ioffice_doc_id).startswith("file:manual/")
    
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        if is_manual:
             # Fetch info from rag_documents itself for manual uploads
             cur.execute("SELECT id, title, source, original_id FROM rag_documents WHERE id=%s LIMIT 1", (rag_doc_id,))
             rd = cur.fetchone()
             if rd:
                 # Construct a pseudo-doc object from rag_documents info
                 # title -> so_ky_hieu (as fallback)
                 # original_id -> file_path (after removing file: prefix)
                 path = str(rd.get("original_id") or "").replace("file:", "", 1)
                 doc = {
                     "id": 0, # Virtual ID
                     "so_ky_hieu": str(rd.get("title") or "Manual Upload"),
                     "trich_yeu": str(rd.get("title") or "Manual Upload"),
                     "file_path": path,
                     "duong_dan_file": path,
                     "ioffice_doc_id": ioffice_doc_id,
                     "summary_text": "", # Manual uploads might not have summary yet
                 }
        else:
            cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s LIMIT 1", (ioffice_doc_id,))
            doc = cur.fetchone()
            
    if not doc:
      self._mark_rag_doc_failed(rag_doc_id, f"ioffice_document_not_found:{ioffice_doc_id}")
      return {"ok": False, "error": "ioffice_document_not_found", "rag_document_id": rag_doc_id}

    try:
      return self._ingest_fulltext(domain=domain, rag_document_id=rag_doc_id, original_id=original_id, doc=doc)
    except Exception as e:
      self._mark_rag_doc_failed(rag_doc_id, f"exception:{str(e)[:1500]}")
      return {"ok": False, "error": "exception", "rag_document_id": rag_doc_id, "detail": str(e)}

  def process_one_pending_summary(self, *, original_id: str | None = None) -> dict:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        if original_id:
          cur.execute(
            """
            SELECT * FROM rag_documents
            WHERE deleted_at IS NULL AND type=%s AND status IN ('PENDING','FAILED') AND original_id=%s
            ORDER BY (status='PENDING') DESC, updated_at ASC, id ASC
            LIMIT 1
            """,
            (TYPE_IOFFICE_SUMMARY, str(original_id)),
          )
        else:
          cur.execute(
            """
            SELECT * FROM rag_documents
            WHERE deleted_at IS NULL AND type=%s AND status IN ('PENDING','FAILED')
            ORDER BY (status='PENDING') DESC, updated_at ASC, id ASC
            LIMIT 1
            """,
            (TYPE_IOFFICE_SUMMARY,),
          )
        doc_row = cur.fetchone()

    if not doc_row:
      return {"ok": True, "skipped": True, "reason": "no_pending"}

    rag_doc_id = int(doc_row.get("id") or 0)
    oid = str(doc_row.get("original_id") or "").strip()
    ioffice_doc_id = _ioffice_doc_id_from_original_id(oid)
    if not rag_doc_id or not ioffice_doc_id:
      return {"ok": False, "error": "invalid_rag_document"}

    if not _env_bool("EDUAI_IOFFICE_RAG_ENABLED", True):
      self._mark_rag_doc_failed(rag_doc_id, "level1_disabled")
      return {"ok": True, "skipped": True, "reason": "level1_disabled", "rag_document_id": rag_doc_id}
    if not embedding_available():
      self._mark_rag_doc_failed(rag_doc_id, "embedding_unavailable")
      return {"ok": False, "error": "embedding_unavailable", "rag_document_id": rag_doc_id}

    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s LIMIT 1", (ioffice_doc_id,))
        doc = cur.fetchone()
    if not doc:
      self._mark_rag_doc_failed(rag_doc_id, f"ioffice_document_not_found:{ioffice_doc_id}")
      return {"ok": False, "error": "ioffice_document_not_found", "rag_document_id": rag_doc_id}

    if str((doc.get("summary_status") or "")).upper() != "READY" or not str((doc.get("summary_text") or "")).strip():
      self._mark_rag_doc_failed(rag_doc_id, "summary_not_ready")
      return {"ok": False, "error": "summary_not_ready", "rag_document_id": rag_doc_id}

    try:
      res = index_ioffice_summary(doc, domain="MANAGEMENT")
      if isinstance(res, dict) and res.get("skipped"):
        self._mark_rag_doc_failed(rag_doc_id, str(res.get("reason") or "skipped"))
        return {"ok": True, "skipped": True, "reason": str(res.get("reason") or "skipped"), "rag_document_id": rag_doc_id}
      return {"ok": True, "skipped": False, "rag_document_id": rag_doc_id}
    except Exception as e:
      self._mark_rag_doc_failed(rag_doc_id, f"exception:{str(e)[:1500]}")
      return {"ok": False, "error": "exception", "rag_document_id": rag_doc_id, "detail": str(e)}

  def _pick_pending_doc(self, *, original_id: str | None) -> dict | None:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        if original_id:
          cur.execute(
            """
            SELECT * FROM rag_documents
            WHERE deleted_at IS NULL AND type=%s AND status IN ('PENDING','FAILED') AND original_id=%s
            ORDER BY (status='PENDING') DESC, updated_at ASC, id ASC
            LIMIT 1
            """,
            (TYPE_IOFFICE_CHUNK, str(original_id)),
          )
        else:
          cur.execute(
            """
            SELECT * FROM rag_documents
            WHERE deleted_at IS NULL AND type=%s AND status IN ('PENDING','FAILED')
            ORDER BY (status='PENDING') DESC, updated_at ASC, id ASC
            LIMIT 1
            """,
            (TYPE_IOFFICE_CHUNK,),
          )
        return cur.fetchone()

  def _mark_rag_doc_failed(self, rag_document_id: int, error: str) -> None:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "UPDATE rag_documents SET status='FAILED', last_error=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
          (str(error)[:2000], int(rag_document_id)),
        )

  def _ingest_fulltext(self, *, domain: str, rag_document_id: int, original_id: str, doc: dict) -> dict:
    file_path = str(doc.get("file_path") or doc.get("duong_dan_file") or "").strip()
    selected_members = None
    text = _extract_text_from_file(file_path, selected_members=selected_members)
    if not text:
      self._mark_rag_doc_failed(rag_document_id, "empty_fulltext")
      return {"ok": False, "error": "empty_fulltext"}

    cfg = _chunking_cfg()
    auto_chunking = (os.getenv("EDUAI_IOFFICE_RAG_AUTO_CHUNKING") or "1").strip().lower() not in ("0", "false", "no", "off")
    if auto_chunking and not str(os.getenv("EDUAI_IOFFICE_RAG_CHUNK_CHARS") or "").strip():
      total_chars = len(text)
      target_k = int((total_chars / 20000.0) + 3)
      if target_k < 3:
        target_k = 3
      if target_k > 20:
        target_k = 20
      chunk_chars = int(total_chars / max(1, target_k))
      if chunk_chars < 700:
        chunk_chars = 700
      if chunk_chars > 4000:
        chunk_chars = 4000
      overlap_chars = int(chunk_chars * 0.18)
      if overlap_chars < 80:
        overlap_chars = 80
      if overlap_chars > 800:
        overlap_chars = 800
      cfg = FulltextChunkingConfig(
        chunk_chars=chunk_chars,
        overlap_chars=overlap_chars,
        min_chunk_chars=cfg.min_chunk_chars,
        max_total_chars=cfg.max_total_chars,
      )
    chunks = _chunk_text(text, cfg)
    if not chunks:
      self._mark_rag_doc_failed(rag_document_id, "empty_chunks")
      return {"ok": False, "error": "empty_chunks"}

    title = (str((doc.get("trich_yeu") or "")).strip() or None)
    school_id = doc.get("school_id") if doc.get("school_id") is not None else None
    collection = collection_for_domain(domain)

    sample_vecs, embed_model = embed_texts_document([chunks[0]])
    if not sample_vecs or not sample_vecs[0]:
      self._mark_rag_doc_failed(rag_document_id, "empty_embedding")
      return {"ok": False, "error": "empty_embedding"}
    vector_size = len(sample_vecs[0])

    fulltext_hash = _hash_fulltext(text, cfg=cfg, embed_model=embed_model)

    repo = RagMappingRepo()
    existing = repo.get_document(domain=domain, source=SOURCE_IOFFICE, type=TYPE_IOFFICE_CHUNK, original_id=original_id)
    if existing and existing.get("status") == "READY" and existing.get("content_hash") == fulltext_hash:
      return {"ok": True, "skipped": True, "reason": "already_indexed", "rag_document_id": int(existing.get("id") or rag_document_id)}

    qdrant = QdrantRestClient()
    if collection not in qdrant.list_collections():
      qdrant.ensure_collection(name=collection, vector_size=vector_size)
    else:
      size = qdrant.get_collection_vector_size(name=collection)
      if size and int(size) != vector_size:
        allow = (os.getenv("EDUAI_QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH") or "1").strip().lower() not in ("0", "false", "no", "off")
        try:
          max_points = int((os.getenv("EDUAI_QDRANT_RECREATE_MAX_POINTS") or "").strip() or "10")
        except Exception:
          max_points = 10
        if max_points < 0:
          max_points = 0
        cnt = qdrant.get_collection_points_count(name=collection) or 0
        if allow and cnt <= max_points:
          qdrant.delete_collection(name=collection)
          qdrant.ensure_collection(name=collection, vector_size=vector_size)
        else:
          self._mark_rag_doc_failed(rag_document_id, f"qdrant_vector_size_mismatch:{size}:{vector_size}")
          return {"ok": False, "error": "qdrant_vector_size_mismatch"}

    doc_id = repo.upsert_document(
      domain=domain,
      source=SOURCE_IOFFICE,
      type=TYPE_IOFFICE_CHUNK,
      original_id=original_id,
      title=title,
      school_id=school_id,
      subject_id=None,
      grade=None,
      qdrant_collection=collection,
      status="PROCESSING",
      content_hash=fulltext_hash,
    )

    vectors, _ = embed_texts_document(chunks)
    points = []
    item_ids: list[int] = []
    for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
      if not vector:
        continue
      chunk_index = int(idx)
      point_id = repo.get_item_point_id(rag_document_id=doc_id, chunk_index=chunk_index) or str(uuid.uuid4())
      payload = build_payload(
        domain=domain,
        source=SOURCE_IOFFICE,
        type=TYPE_IOFFICE_CHUNK,
        original_id=original_id,
        title=title,
        school_id=school_id,
        role_allowed=None,
        chunk_index=chunk_index,
        content_hash=fulltext_hash,
      )
      points.append({"id": point_id, "vector": vector, "payload": payload})
      meta = dict(payload)
      meta["text"] = str(chunk_text)[:4000]
      item_id = repo.upsert_item(
        rag_document_id=doc_id,
        domain=domain,
        source=SOURCE_IOFFICE,
        type=TYPE_IOFFICE_CHUNK,
        title=title,
        original_id=original_id,
        chunk_index=chunk_index,
        qdrant_collection=collection,
        qdrant_point_id=point_id,
        metadata=json.dumps(meta, ensure_ascii=False),
        status="READY",
        content_hash=fulltext_hash,
      )
      item_ids.append(int(item_id))

      if len(points) >= 64:
        qdrant.upsert_points(collection=collection, points=points)
        points = []

    if points:
      qdrant.upsert_points(collection=collection, points=points)

    repo.finalize_document(rag_document_id=doc_id, chunk_count=len(item_ids), status="READY")
    return {"ok": True, "skipped": False, "rag_document_id": int(doc_id), "rag_item_ids": item_ids[:50], "embed_model": embed_model, "chunk_count": len(item_ids)}


ioffice_rag_ingestor = IOfficeRagIngestor()
