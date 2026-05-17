from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
  sys.path.insert(0, PROJECT_ROOT)

from backend.app.services.qdrant_rest import QdrantRestClient
from backend.app.services.rag_conventions import build_payload, collection_for_domain
from backend.app.services.rag_mapping_repo import RagMappingRepo


def sha256_hex(text: str) -> str:
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
  domain = "MANAGEMENT"
  source = "IOFFICE"
  type = "official_document"
  original_id = "ioffice:1024"
  title = "Quy định kiểm tra học kỳ II"

  qdrant = QdrantRestClient()
  repo = RagMappingRepo()

  collection = collection_for_domain(domain)
  qdrant.ensure_collection(name=collection, vector_size=4)

  normalized_content = "Demo content for doc 1024"
  content_hash = sha256_hex(normalized_content)

  doc_id = repo.upsert_document(
    domain=domain,
    source=source,
    type=type,
    original_id=original_id,
    title=title,
    school_id=None,
    subject_id=None,
    grade=None,
    qdrant_collection=collection,
    status="PROCESSING",
    content_hash=content_hash,
  )

  chunk_index = 0
  point_id = str(uuid.uuid4())
  vector = [0.1, 0.2, 0.3, 0.4]
  payload = build_payload(
    domain=domain,
    source=source,
    type=type,
    original_id=original_id,
    title=title,
    role_allowed=["principal"],
    chunk_index=chunk_index,
    content_hash=content_hash,
  )

  qdrant.upsert_points(
    collection=collection,
    points=[{"id": point_id, "vector": vector, "payload": payload}],
  )

  item_id = repo.insert_item(
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

  print("OK")
  print({"rag_document_id": doc_id, "rag_item_id": item_id, "qdrant_collection": collection, "qdrant_point_id": point_id})


if __name__ == "__main__":
  main()
