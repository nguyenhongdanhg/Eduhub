from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class QdrantConfig:
  base_url: str = "http://127.0.0.1:6333"
  api_key: str | None = None
  timeout_sec: float = 10.0


def load_qdrant_config() -> QdrantConfig:
  return QdrantConfig(
    base_url=(os.getenv("EDUAI_QDRANT_URL") or os.getenv("QDRANT_URL") or "http://127.0.0.1:6333").strip(),
    api_key=(os.getenv("EDUAI_QDRANT_API_KEY") or os.getenv("QDRANT_API_KEY") or "").strip() or None,
    timeout_sec=float(os.getenv("EDUAI_QDRANT_TIMEOUT_SEC") or os.getenv("QDRANT_TIMEOUT_SEC") or "10"),
  )


class QdrantRestClient:
  def __init__(self, config: QdrantConfig | None = None) -> None:
    self._config = config or load_qdrant_config()

  def _request(self, method: str, path: str, body: dict | None = None, *, timeout_sec: float | None = None) -> dict | str:
    url = f"{self._config.base_url.rstrip('/')}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if self._config.api_key:
      headers["api-key"] = self._config.api_key
    if body is not None:
      data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
      with urllib.request.urlopen(req, timeout=float(timeout_sec or self._config.timeout_sec)) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
          return {}
        try:
          return json.loads(raw)
        except Exception:
          return raw
    except urllib.error.HTTPError as e:
      raw = e.read().decode("utf-8", errors="replace")
      raise RuntimeError(f"Qdrant HTTP {e.code}: {raw}") from e

  def ready(self, *, timeout_sec: float = 2.5) -> bool:
    res = self._request("GET", "/readyz", timeout_sec=timeout_sec)
    if isinstance(res, str):
      return "ready" in res.lower()
    if isinstance(res, dict):
      return bool(res)
    return False

  def list_collections(self) -> list[str]:
    res = self._request("GET", "/collections")
    cols = res.get("result", {}).get("collections", [])
    return [c.get("name") for c in cols if isinstance(c, dict) and "name" in c]

  def ensure_collection(self, *, name: str, vector_size: int, distance: str = "Cosine") -> None:
    if name in self.list_collections():
      return
    self._request(
      "PUT",
      f"/collections/{name}",
      {
        "vectors": {"size": vector_size, "distance": distance},
      },
    )

  def get_collection_vector_size(self, *, name: str) -> int | None:
    res = self._request("GET", f"/collections/{name}")
    try:
      size = res.get("result", {}).get("config", {}).get("params", {}).get("vectors", {}).get("size")
      return int(size) if size is not None else None
    except Exception:
      return None

  def get_collection_points_count(self, *, name: str) -> int | None:
    res = self._request("GET", f"/collections/{name}")
    try:
      v = res.get("result", {}).get("points_count")
      if v is None:
        v = res.get("result", {}).get("vectors_count")
      return int(v) if v is not None else None
    except Exception:
      return None

  def delete_collection(self, *, name: str) -> None:
    self._request("DELETE", f"/collections/{name}")

  def upsert_points(self, *, collection: str, points: list[dict]) -> None:
    self._request("PUT", f"/collections/{collection}/points", {"points": points})

  def set_payload(self, *, collection: str, point_ids: list[str | int], payload: dict) -> None:
    self._request("POST", f"/collections/{collection}/points/payload", {"payload": payload, "points": point_ids})

  def delete_points(self, *, collection: str, point_ids: list[str | int]) -> None:
    self._request("POST", f"/collections/{collection}/points/delete", {"points": point_ids})

  def search_points(
    self,
    *,
    collection: str,
    vector: list[float],
    limit: int = 10,
    score_threshold: float | None = None,
    filter_: dict | None = None,
    with_payload: bool = True,
  ) -> list[dict]:
    body: dict = {
      "vector": vector,
      "limit": int(limit),
      "with_payload": bool(with_payload),
    }
    if score_threshold is not None:
      body["score_threshold"] = float(score_threshold)
    if filter_ is not None:
      body["filter"] = filter_
    res = self._request("POST", f"/collections/{collection}/points/search", body)
    out = res.get("result")
    return out if isinstance(out, list) else []
