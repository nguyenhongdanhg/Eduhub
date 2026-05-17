from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RagCollections:
  management: str = "eduai_rag_management"
  teaching: str = "eduai_rag_teaching"
  learning: str = "eduai_rag_learning"


COLLECTIONS = RagCollections()


def collection_for_domain(domain: str) -> str:
  d = domain.upper()
  if d == "MANAGEMENT":
    return COLLECTIONS.management
  if d == "TEACHING":
    return COLLECTIONS.teaching
  if d == "LEARNING":
    return COLLECTIONS.learning
  raise ValueError(f"Unsupported domain: {domain}")


def build_payload(
  *,
  domain: str,
  source: str,
  type: str,
  original_id: str,
  title: str | None = None,
  school_id: int | None = None,
  subject_id: int | None = None,
  grade: int | None = None,
  role_allowed: list[str] | None = None,
  effective_date: str | None = None,
  chunk_index: int | None = None,
  content_hash: str | None = None,
) -> dict:
  payload: dict = {
    "domain": domain.upper(),
    "source": source,
    "type": type,
    "original_id": original_id,
  }
  if title is not None:
    payload["title"] = title
  if school_id is not None:
    payload["school_id"] = school_id
  if subject_id is not None:
    payload["subject_id"] = subject_id
  if grade is not None:
    payload["grade"] = grade
  if role_allowed is not None:
    payload["role_allowed"] = role_allowed
  if effective_date is not None:
    payload["effective_date"] = effective_date
  if chunk_index is not None:
    payload["chunk_index"] = chunk_index
  if content_hash is not None:
    payload["content_hash"] = content_hash
  return payload

