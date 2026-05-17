import os
import threading
import time
from datetime import datetime

from app.services.vn_time import now_vn_iso


def _env_bool(name: str, default: bool) -> bool:
  try:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
      return default
    return v not in ("0", "false", "no", "off")
  except Exception:
    return default


def _env_int(name: str, default: int) -> int:
  try:
    return int((os.getenv(name) or "").strip() or str(default))
  except Exception:
    return default


class IOfficeRagWorker:
  def __init__(self) -> None:
    self._lock = threading.Lock()
    self._thread: threading.Thread | None = None
    self._running = False
    self._last_tick_at: str | None = None
    self._last_error: str | None = None
    self._processed = 0

  def status(self) -> dict:
    with self._lock:
      return {
        "running": bool(self._running),
        "processed": int(self._processed),
        "last_tick_at": self._last_tick_at,
        "last_error": self._last_error,
      }

  def start(self) -> None:
    enabled = _env_bool("EDUAI_IOFFICE_RAG_LEVEL2_WORKER", True)
    if not enabled:
      return
    with self._lock:
      if self._thread and self._thread.is_alive():
        return
      self._running = True
      self._thread = threading.Thread(target=self._loop, daemon=True)
      self._thread.start()

  def _loop(self) -> None:
    from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

    interval_sec = max(2, _env_int("EDUAI_IOFFICE_RAG_LEVEL2_INTERVAL_SEC", 5))
    while True:
      with self._lock:
        self._last_tick_at = now_vn_iso()
        self._last_error = None
      try:
        oid = ioffice_rag_ingestor.pop_priority_original_id()
        processed_any = 0
        res1 = ioffice_rag_ingestor.process_one_pending_summary(original_id=oid if oid else None)
        if isinstance(res1, dict) and res1.get("ok") and not res1.get("skipped"):
          processed_any += 1
        res2 = ioffice_rag_ingestor.process_one_pending_fulltext(original_id=oid if oid else None)
        if isinstance(res2, dict) and res2.get("ok") and not res2.get("skipped"):
          processed_any += 1
        if processed_any:
          with self._lock:
            self._processed += processed_any
      except Exception as e:
        with self._lock:
          self._last_error = str(e)
      time.sleep(interval_sec)


ioffice_rag_worker = IOfficeRagWorker()
