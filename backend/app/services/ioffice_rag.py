import json
import os
import uuid
import hashlib

from app.services.embedding_client import embed_text_document, embedding_available
from app.services.qdrant_rest import QdrantRestClient
from app.services.rag_conventions import build_payload, collection_for_domain
from app.services.rag_mapping_repo import RagMappingRepo


SOURCE_IOFFICE = "IOFFICE"
TYPE_IOFFICE_SUMMARY = "official_document_summary"
TYPE_IOFFICE_CHUNK = "official_document_chunk"


def _role_allowed() -> list[str]:
  raw = (os.getenv("EDUAI_IOFFICE_RAG_ROLE_ALLOWED") or "").strip()
  if raw:
    return [x.strip() for x in raw.split(",") if x.strip()]
  return ["principal"]


def build_summary_for_embedding(doc: dict) -> str:
  parts = []
  so_ky_hieu = (doc.get("so_ky_hieu") or "").strip()
  trich_yeu = (doc.get("trich_yeu") or "").strip()
  don_vi = (doc.get("don_vi_ban_hanh") or "").strip()
  ngay_den = (doc.get("ngay_den") or "").strip()
  han = (doc.get("han_xu_ly") or "").strip()
  if so_ky_hieu:
    parts.append(f"Số ký hiệu: {so_ky_hieu}")
  if trich_yeu:
    parts.append(f"Trích yếu: {trich_yeu}")
  if don_vi:
    parts.append(f"Đơn vị ban hành: {don_vi}")
  if ngay_den:
    parts.append(f"Ngày đến: {ngay_den}")
  if han:
    parts.append(f"Hạn xử lý: {han}")
  summary = (doc.get("summary_text") or "").strip()
  if summary:
    parts.append("")
    parts.append("TÓM TẮT:")
    parts.append(summary)
  return "\n".join(parts).strip()


def index_ioffice_summary(doc: dict, *, domain: str = "MANAGEMENT") -> dict:
  enabled_raw = (os.getenv("EDUAI_IOFFICE_RAG_ENABLED") or "1").strip().lower()
  if enabled_raw in ("0", "false", "no", "off"):
    return {"ok": True, "skipped": True, "reason": "disabled"}

  if not embedding_available():
    return {"ok": True, "skipped": True, "reason": "embedding_unavailable"}

  ioffice_doc_id = (doc.get("ioffice_doc_id") or "").strip()
  if ioffice_doc_id.lower().startswith("ioffice:"):
    ioffice_doc_id = ioffice_doc_id.split(":", 1)[1].strip()
  if not ioffice_doc_id:
    return {"ok": True, "skipped": True, "reason": "missing_doc_id"}

  domain = (domain or "MANAGEMENT").strip().upper() or "MANAGEMENT"
  source = SOURCE_IOFFICE
  type = TYPE_IOFFICE_SUMMARY
  original_id = f"ioffice:{ioffice_doc_id}"

  title = (doc.get("trich_yeu") or "").strip() or None
  school_id = doc.get("school_id") if doc.get("school_id") is not None else None

  repo = RagMappingRepo()
  text_for_embed = build_summary_for_embedding(doc)
  if not text_for_embed:
    return {"ok": True, "skipped": True, "reason": "empty_text"}
  content_hash = (doc.get("content_hash") or "").strip() or None
  if not content_hash:
    try:
      h = hashlib.sha1()
      h.update(text_for_embed.encode("utf-8"))
      content_hash = h.hexdigest()
    except Exception:
      content_hash = None
  existing = repo.get_document(domain=domain, source=source, type=type, original_id=original_id)
  if existing and existing.get("status") == "READY" and content_hash and existing.get("content_hash") == content_hash:
    return {"ok": True, "skipped": True, "reason": "already_indexed"}

  collection = collection_for_domain(domain)
  vector, embed_model = embed_text_document(text_for_embed)

  qdrant = QdrantRestClient()
  if collection not in qdrant.list_collections():
    qdrant.ensure_collection(name=collection, vector_size=len(vector))
  else:
    size = qdrant.get_collection_vector_size(name=collection)
    if size and int(size) != len(vector):
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
        qdrant.ensure_collection(name=collection, vector_size=len(vector))
      else:
        raise RuntimeError(f"qdrant_vector_size_mismatch: expected {size}, got {len(vector)}")

  doc_id = repo.upsert_document(
    domain=domain,
    source=source,
    type=type,
    original_id=original_id,
    title=title,
    school_id=school_id,
    subject_id=None,
    grade=None,
    qdrant_collection=collection,
    status="PROCESSING",
    content_hash=content_hash,
  )

  chunk_index = 0
  point_id = repo.get_item_point_id(rag_document_id=doc_id, chunk_index=chunk_index) or str(uuid.uuid4())
  payload = build_payload(
    domain=domain,
    source=source,
    type=type,
    original_id=original_id,
    title=title,
    school_id=school_id,
    role_allowed=_role_allowed(),
    chunk_index=chunk_index,
    content_hash=content_hash,
  )
  qdrant.upsert_points(collection=collection, points=[{"id": point_id, "vector": vector, "payload": payload}])
  item_id = repo.upsert_item(
    rag_document_id=doc_id,
    domain=domain,
    source=source,
    type=type,
    title=title,
    original_id=original_id,
    chunk_index=chunk_index,
    qdrant_collection=collection,
    qdrant_point_id=point_id,
    metadata=json.dumps(payload, ensure_ascii=False),
    status="READY",
    content_hash=content_hash,
  )
  repo.finalize_document(rag_document_id=doc_id, chunk_count=1, status="READY")
  return {"ok": True, "skipped": False, "rag_document_id": doc_id, "rag_item_id": item_id, "embed_model": embed_model}
