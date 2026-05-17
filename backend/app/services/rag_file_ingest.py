import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.db import get_db_connection
from app.services.embedding_client import embed_texts_document, embedding_available
from app.services.qdrant_rest import QdrantRestClient
from app.services.rag_conventions import build_payload, collection_for_domain
from app.services.rag_mapping_repo import RagMappingRepo
from utils import RAG_FILES_ROOT, ensure_dir


@dataclass(frozen=True)
class ChunkingConfig:
  chunk_chars: int = 1400
  overlap_chars: int = 200
  min_chunk_chars: int = 200
  max_total_chars: int = 500_000


def _env_int(name: str, default: int) -> int:
  try:
    return int((os.getenv(name) or "").strip() or str(default))
  except Exception:
    return default


def _chunking_cfg() -> ChunkingConfig:
  return ChunkingConfig(
    chunk_chars=max(300, _env_int("EDUAI_RAG_UPLOAD_CHUNK_CHARS", 1400)),
    overlap_chars=max(0, _env_int("EDUAI_RAG_UPLOAD_OVERLAP_CHARS", 200)),
    min_chunk_chars=max(50, _env_int("EDUAI_RAG_UPLOAD_MIN_CHUNK_CHARS", 200)),
    max_total_chars=max(10_000, _env_int("EDUAI_RAG_UPLOAD_MAX_TOTAL_CHARS", 500_000)),
  )


def _safe_rel_path(path_like: str) -> str:
  s = str(path_like or "").strip().replace("\\", "/").lstrip("/")
  parts = [p for p in s.split("/") if p and p not in (".", "..")]
  return "/".join(parts)


def _full_path_from_rel(rel_path: str) -> Path:
  rel = _safe_rel_path(rel_path)
  full = (RAG_FILES_ROOT / rel).resolve()
  root = RAG_FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise ValueError("unsafe_path")
  return full


def _sha256_file(full: Path) -> str:
  h = hashlib.sha256()
  with open(full, "rb") as f:
    while True:
      b = f.read(1024 * 1024)
      if not b:
        break
      h.update(b)
  return h.hexdigest()


def _try_update_rag_doc_file_meta(*, rag_document_id: int, file_hash: str | None, file_exists: bool, file_size: int | None, file_mtime_iso: str | None) -> None:
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          """
          UPDATE rag_documents
          SET file_hash=%s, file_exists=%s, file_size=%s, file_mtime=%s, file_checked_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
          WHERE id=%s
          """,
          (file_hash, 1 if file_exists else 0, file_size, file_mtime_iso, int(rag_document_id)),
        )
      conn.commit()
  except Exception:
    return


def _is_low_quality_text(text: str) -> bool:
  t = (text or "").strip()
  if len(t) < 200:
    return True
  alnum = sum(1 for ch in t if ch.isalnum())
  if alnum / max(1, len(t)) < 0.15:
    return True
  lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
  if len(lines) >= 8:
    uniq = len(set(lines))
    if uniq / max(1, len(lines)) < 0.35:
      return True
  return False


def save_uploaded_file(*, filename: str, data: bytes) -> dict:
  ensure_dir(RAG_FILES_ROOT)
  safe_name = re.sub(r"[^\w.\-]+", "_", str(filename or "").strip())[:180] or "upload.bin"
  uid = uuid.uuid4().hex
  subdir = Path("manual") / uid[:2]
  ensure_dir((RAG_FILES_ROOT / subdir).resolve())
  rel = str((subdir / f"{uid}_{safe_name}").as_posix())
  full = _full_path_from_rel(rel)
  full.write_bytes(data)
  return {"rel_path": rel, "full_path": str(full), "stored_name": f"{uid}_{safe_name}"}


def _decode_text_bytes(data: bytes) -> str:
  if not data:
    return ""
  b = bytes(data)
  if b.startswith(b"\xef\xbb\xbf"):
    try:
      return b.decode("utf-8-sig", errors="strict")
    except Exception:
      pass
  if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
    try:
      return b.decode("utf-16", errors="strict")
    except Exception:
      pass
  candidates = ["utf-8", "utf-16", "cp1258", "cp1252", "latin-1"]
  best = ""
  best_score = -1.0
  for enc in candidates:
    try:
      s = b.decode(enc, errors="replace")
    except Exception:
      continue
    s2 = s.replace("\x00", "").strip()
    if not s2:
      continue
    repl = s2.count("\ufffd")
    printable = sum(1 for ch in s2 if ch.isprintable())
    score = (printable / max(1, len(s2))) - (repl / max(1, len(s2))) * 2.5
    if score > best_score:
      best_score = score
      best = s2
  return best.strip()


def _extract_text_from_file_with_reason(full: Path) -> tuple[str, str]:
  if not full.exists():
    return "", "file_missing"
  ext = full.suffix.lower()
  if ext == ".zip":
    try:
      import zipfile

      from ai_summary_compat import extract_text_from_zip

      try:
        with zipfile.ZipFile(str(full), "r") as z:
          members = [m for m in z.namelist() if m and not m.endswith("/")]
      except zipfile.BadZipFile:
        return "", "zip_bad"

      supported = [m for m in members if Path(m).suffix.lower() in (".pdf", ".docx", ".txt", ".md", ".html", ".htm")]
      if not supported:
        return "", "zip_no_supported_members"
      text = str(extract_text_from_zip(full) or "").strip()
      if not text:
        return "", "zip_extract_empty"
      return text, "ok"
    except Exception as e:
      return "", f"zip_parse_failed:{str(e)[:120]}"
  if ext in (".txt", ".md", ".html", ".htm"):
    try:
      raw = full.read_bytes()
      text = _decode_text_bytes(raw)
      return text.strip(), "ok" if text.strip() else "decode_failed"
    except Exception as e:
      return "", f"decode_failed:{str(e)[:120]}"
  if ext == ".docx":
    try:
      import zipfile
      from io import BytesIO

      data = full.read_bytes()
      with zipfile.ZipFile(BytesIO(data)) as dz:
        xml = dz.read("word/document.xml")
      s = xml.decode("utf-8", errors="ignore")
      s = re.sub(r"<[^>]+>", " ", s)
      s = re.sub(r"\s+", " ", s)
      val = s.strip()
      return val, "ok" if val else "docx_empty"
    except Exception as e:
      return "", f"docx_parse_failed:{str(e)[:120]}"
  if ext == ".pdf":
    try:
      import pypdf

      reader = pypdf.PdfReader(str(full))
      texts = []
      for pg in reader.pages:
        t = pg.extract_text() or ""
        if t.strip():
          texts.append(t)
      val = "\n".join(texts).strip()
      if val:
        return val, "ok"
      try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(str(full))
        ocr_texts = []
        for img in images:
          page_text = pytesseract.image_to_string(img, lang="vie+eng")
          if page_text.strip():
            ocr_texts.append(page_text)
        ocr_val = "\n".join(ocr_texts).strip()
        return ocr_val, "ok_ocr" if ocr_val else "pdf_no_text"
      except ImportError:
        return "", "pdf_no_text_ocr_unavailable"
      except Exception as e:
        return "", f"pdf_ocr_failed:{str(e)[:120]}"
    except Exception as e:
      return "", f"pdf_parse_failed:{str(e)[:120]}"
  return "", f"unsupported_filetype:{ext or 'unknown'}"


def _chunk_text(text: str, cfg: ChunkingConfig) -> list[str]:
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


def create_pending_document_for_file(*, domain: str, source: str, type: str, file_rel_path: str, filename: str | None = None) -> dict:
  dom = str(domain or "").strip().upper()
  if dom not in ("MANAGEMENT", "TEACHING", "LEARNING"):
    return {"ok": False, "error": "invalid_domain"}
  src = str(source or "").strip()
  typ = str(type or "").strip()
  rel = _safe_rel_path(file_rel_path)
  if not src or not typ or not rel:
    return {"ok": False, "error": "missing_required_fields"}
  original_id = f"file:{rel}"
  title = str(filename or Path(rel).name or "").strip() or None
  collection = collection_for_domain(dom)

  repo = RagMappingRepo()
  doc_id = repo.upsert_document(
    domain=dom,
    source=src,
    type=typ,
    original_id=original_id,
    title=title,
    school_id=None,
    subject_id=None,
    grade=None,
    qdrant_collection=collection,
    status="PENDING",
    content_hash=None,
  )
  try:
    full = _full_path_from_rel(rel)
    if full.exists():
      st = full.stat()
      file_size = int(st.st_size)
      file_mtime_iso = None
      try:
        import datetime

        file_mtime_iso = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
      except Exception:
        file_mtime_iso = None
      file_hash = _sha256_file(full)
      _try_update_rag_doc_file_meta(
        rag_document_id=int(doc_id),
        file_hash=file_hash,
        file_exists=True,
        file_size=file_size,
        file_mtime_iso=file_mtime_iso,
      )
    else:
      _try_update_rag_doc_file_meta(
        rag_document_id=int(doc_id),
        file_hash=None,
        file_exists=False,
        file_size=None,
        file_mtime_iso=None,
      )
  except Exception:
    pass
  return {"ok": True, "rag_document_id": int(doc_id), "original_id": original_id, "file_rel_path": rel}


def ingest_saved_file(*, rag_document_id: int) -> dict:
  rid = int(rag_document_id or 0)
  if rid <= 0:
    return {"ok": False, "error": "missing_rag_document_id"}

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM rag_documents WHERE id=%s LIMIT 1", (rid,))
      doc = cur.fetchone() or None
  if not doc:
    return {"ok": False, "error": "rag_document_not_found"}

  if not embedding_available():
    repo = RagMappingRepo()
    repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error="embedding_unavailable")
    return {"ok": False, "error": "embedding_unavailable"}

  dom = str(doc.get("domain") or "").strip().upper()
  src = str(doc.get("source") or "").strip()
  typ = str(doc.get("type") or "").strip()
  original_id = str(doc.get("original_id") or "").strip()
  if not original_id.lower().startswith("file:"):
    return {"ok": False, "error": "not_file_document"}
  rel = _safe_rel_path(original_id.split("file:", 1)[1].strip())

  full = _full_path_from_rel(rel)
  if not full.exists():
    repo = RagMappingRepo()
    repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error="file_missing")
    _try_update_rag_doc_file_meta(rag_document_id=rid, file_hash=None, file_exists=False, file_size=None, file_mtime_iso=None)
    return {"ok": False, "error": "file_missing"}

  try:
    st = full.stat()
    file_size = int(st.st_size)
    file_mtime_iso = None
    try:
      import datetime

      file_mtime_iso = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
      file_mtime_iso = None
    file_hash = _sha256_file(full)
  except Exception:
    file_size = None
    file_mtime_iso = None
    file_hash = None

  _try_update_rag_doc_file_meta(
    rag_document_id=rid,
    file_hash=file_hash,
    file_exists=True,
    file_size=file_size,
    file_mtime_iso=file_mtime_iso,
  )

  if file_hash:
    try:
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(
            """
            SELECT id FROM rag_documents
            WHERE deleted_at IS NULL AND status='READY' AND file_hash=%s AND id<>%s
            LIMIT 1
            """,
            (file_hash, rid),
          )
          row = cur.fetchone()
      dup_id = int(row.get("id") or 0) if isinstance(row, dict) else int(row[0]) if row else 0
      if dup_id:
        with get_db_connection() as conn:
          with conn.cursor() as cur:
            cur.execute(
              "UPDATE rag_documents SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, last_error=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
              (f"duplicate_file_of:{dup_id}", rid),
            )
          conn.commit()
        return {"ok": True, "skipped": True, "reason": "duplicate_file", "existing_rag_document_id": dup_id}
    except Exception:
      pass

  text, reason = _extract_text_from_file_with_reason(full)
  if not text:
    repo = RagMappingRepo()
    repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error=f"empty_text:{reason}")
    return {"ok": False, "error": "empty_text", "reason": reason}
  if _is_low_quality_text(text):
    repo = RagMappingRepo()
    repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error="low_quality_text")
    return {"ok": False, "error": "low_quality_text"}

  cfg = _chunking_cfg()
  vectors_model = os.getenv("EDUAI_EMBEDDING_MODEL") or ""
  h = hashlib.sha256()
  h.update(text.encode("utf-8"))
  h.update(f"|chunk_chars={cfg.chunk_chars}|overlap={cfg.overlap_chars}|min={cfg.min_chunk_chars}|model={vectors_model}".encode("utf-8"))
  content_hash = h.hexdigest()
  collection = str(doc.get("qdrant_collection") or "").strip() or collection_for_domain(dom)

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        "SELECT id FROM rag_documents WHERE domain=%s AND content_hash=%s AND deleted_at IS NULL AND status='READY' LIMIT 1",
        (dom, content_hash),
      )
      dup = cur.fetchone()
      dup_id = int(dup.get("id") or 0) if isinstance(dup, dict) else int(dup[0]) if dup else 0
      if dup_id and dup_id != rid:
        cur.execute(
          "UPDATE rag_documents SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, last_error=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
          (f"duplicate_of:{dup_id}", rid),
        )
        conn.commit()
        return {"ok": True, "skipped": True, "reason": "duplicate", "existing_rag_document_id": dup_id}

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("UPDATE rag_documents SET status='PROCESSING', content_hash=%s, last_error=NULL, deleted_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (content_hash, rid))
    conn.commit()

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        "UPDATE rag_items SET status='DELETED', deleted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE rag_document_id=%s AND deleted_at IS NULL",
        (rid,),
      )
    conn.commit()

  chunks = _chunk_text(text, cfg)
  if not chunks:
    repo = RagMappingRepo()
    repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error="empty_chunks")
    return {"ok": False, "error": "empty_chunks"}

  vectors, model_used = embed_texts_document(chunks)
  vector_size = 0
  for v in vectors:
    if v:
      vector_size = len(v)
      break
  if not vector_size:
    repo = RagMappingRepo()
    repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error="empty_vectors")
    return {"ok": False, "error": "empty_vectors"}

  qdrant = QdrantRestClient()
  if collection not in qdrant.list_collections():
    qdrant.ensure_collection(name=collection, vector_size=vector_size)
  else:
    size = qdrant.get_collection_vector_size(name=collection)
    if size and int(size) != vector_size:
      repo = RagMappingRepo()
      repo.finalize_document(rag_document_id=rid, chunk_count=0, status="FAILED", last_error=f"qdrant_vector_size_mismatch:{size}:{vector_size}")
      return {"ok": False, "error": "qdrant_vector_size_mismatch"}

  points = []
  item_ids: list[int] = []
  repo = RagMappingRepo()
  title = str(doc.get("title") or "").strip() or None
  for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
    if not vector:
      continue
    chunk_index = int(idx)
    point_id = repo.get_item_point_id(rag_document_id=rid, chunk_index=chunk_index) or str(uuid.uuid4())
    payload = build_payload(
      domain=dom,
      source=src,
      type=typ,
      original_id=original_id,
      title=title,
      school_id=None,
      role_allowed=None,
      chunk_index=chunk_index,
      content_hash=content_hash,
    )
    points.append({"id": point_id, "vector": vector, "payload": payload})
    meta = dict(payload)
    meta["text"] = str(chunk_text)[:4000]
    meta["file_rel_path"] = rel
    meta["file_name"] = str(full.name or "")
    item_id = repo.upsert_item(
      rag_document_id=rid,
      domain=dom,
      source=src,
      type=typ,
      title=title,
      original_id=original_id,
      chunk_index=chunk_index,
      qdrant_collection=collection,
      qdrant_point_id=point_id,
      metadata=json.dumps(meta, ensure_ascii=False),
      status="READY",
      content_hash=content_hash,
    )
    item_ids.append(int(item_id))
    if len(points) >= 64:
      qdrant.upsert_points(collection=collection, points=points)
      points = []

  if points:
    qdrant.upsert_points(collection=collection, points=points)

  repo.finalize_document(rag_document_id=rid, chunk_count=len(item_ids), status="READY")
  return {"ok": True, "rag_document_id": rid, "chunk_count": len(item_ids), "embed_model": model_used, "original_id": original_id, "file_rel_path": rel}


def ingest_uploaded_file(*, domain: str, source: str, type: str, file_rel_path: str, filename: str | None = None) -> dict:
  pending = create_pending_document_for_file(domain=domain, source=source, type=type, file_rel_path=file_rel_path, filename=filename)
  if not pending.get("ok"):
    return pending
  return ingest_saved_file(rag_document_id=int(pending.get("rag_document_id") or 0))
