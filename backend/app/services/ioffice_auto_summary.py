import os
import threading
import time
from datetime import datetime

from app.services.vn_time import now_vn_iso

def _env_bool(name: str, default: bool = False) -> bool:
  try:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
      return default
    return v not in ("0", "false", "no")
  except Exception:
    return default


def _env_int(name: str, default: int) -> int:
  try:
    return int((os.getenv(name) or "").strip() or str(default))
  except Exception:
    return default


class IOfficeAutoSummaryWorker:
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
    enabled = _env_bool("EDUAI_IOFFICE_AUTO_SUMMARY", True)
    if not enabled:
      return
    with self._lock:
      if self._thread and self._thread.is_alive():
        return
      self._running = True
      self._thread = threading.Thread(target=self._loop, daemon=True)
      self._thread.start()

  def _loop(self) -> None:
    from app.db import get_db_connection
    from app.services.ioffice_summary import summarize_document
    from app.services.ioffice_summary import prepare_summary_input
    from app.services.llm_client import validate_summary_model

    interval_sec = max(10, _env_int("EDUAI_IOFFICE_AUTO_SUMMARY_INTERVAL_SEC", 60))
    batch = max(1, min(50, _env_int("EDUAI_IOFFICE_AUTO_SUMMARY_BATCH", 5)))
    rescue_sec = max(60, _env_int("EDUAI_IOFFICE_AUTO_SUMMARY_RESCUE_SEC", 1800))
    prompt_mode = (os.getenv("EDUAI_IOFFICE_AUTO_SUMMARY_PROMPT_MODE") or "").strip()
    model = (os.getenv("EDUAI_IOFFICE_AUTO_SUMMARY_MODEL") or "").strip() or None
    if not prompt_mode:
      try:
        from app.services.ioffice_prompt_store import list_prompt_presets

        presets = [p for p in (list_prompt_presets() or []) if isinstance(p, dict) and p.get("id") and bool(p.get("enabled"))]
        presets.sort(key=lambda x: (int(x.get("sort_order") or 0), str(x.get("id") or "")))
        if presets:
          prompt_mode = str(presets[0].get("id") or "").strip()
      except Exception:
        prompt_mode = ""
    if not prompt_mode:
      prompt_mode = "p3"

    while True:
      with self._lock:
        self._last_tick_at = now_vn_iso()
        self._last_error = None
      try:
        now = datetime.utcnow()
        candidates: list[dict] = []
        with get_db_connection() as conn:
          with conn.cursor() as cur:
            cur.execute(
              """
              SELECT *
              FROM ioffice_documents
              WHERE fetch_status='OK'
                AND (
                  summary_text IS NULL OR summary_text='' OR summary_status IN ('PENDING','FAILED')
                  OR (summary_status='PROCESSING' AND summary_updated_at IS NOT NULL AND summary_updated_at < (UTC_TIMESTAMP() - INTERVAL %s SECOND))
                )
              ORDER BY COALESCE(summary_updated_at, updated_at) DESC
              LIMIT %s
              """,
              (int(rescue_sec), int(batch)),
            )
            candidates = list(cur.fetchall() or [])

        try:
          model_plan = validate_summary_model(model=model, prompt_mode=prompt_mode, content_type="ioffice_summary")
          checked_model = str(model_plan.get("model") or model or "").strip() or None
        except Exception as e:
          message = f"Chưa chạy tóm tắt tự động vì cấu hình AI/model chưa hợp lệ: {e}"
          with get_db_connection() as conn:
            with conn.cursor() as cur:
              cur.execute(
                "UPDATE ioffice_documents SET summary_status='FAILED', summary_error=%s, summary_updated_at=UTC_TIMESTAMP() WHERE fetch_status='OK' AND (summary_text IS NULL OR summary_text='' OR summary_status IN ('PENDING','FAILED')) LIMIT %s",
                (message, int(batch)),
              )
          with self._lock:
            self._last_error = message
          time.sleep(interval_sec)
          continue

        for doc in candidates:
          try:
            doc_id = int(doc.get("id") or 0)
            if not doc_id:
              continue
            _, content_hash = prepare_summary_input(doc, model=checked_model, prompt_mode=prompt_mode)
            if doc.get("content_hash") and doc.get("content_hash") == content_hash and (doc.get("summary_text") or "").strip() and str(doc.get("summary_model") or "").strip() == str(checked_model or "").strip():
              with get_db_connection() as conn:
                with conn.cursor() as cur:
                  cur.execute(
                    "UPDATE ioffice_documents SET summary_status='READY', summary_error=NULL, summary_updated_at=UTC_TIMESTAMP() WHERE id=%s",
                    (doc_id,),
                  )
              with self._lock:
                self._processed += 1
              continue
            if (doc.get("summary_status") or "").strip().upper() == "PROCESSING":
              pass
            with get_db_connection() as conn:
              with conn.cursor() as cur:
                cur.execute(
                  "UPDATE ioffice_documents SET summary_status='PROCESSING', summary_updated_at=UTC_TIMESTAMP() WHERE id=%s",
                  (doc_id,),
                )
            summary, model_used, content_hash = summarize_document(doc, model=checked_model, prompt_mode=prompt_mode)
            with get_db_connection() as conn:
              with conn.cursor() as cur:
                cur.execute(
                  """
                  UPDATE ioffice_documents
                  SET summary_status='READY',
                      summary_text=%s,
                      summary_model=%s,
                      summary_error=NULL,
                      summary_updated_at=UTC_TIMESTAMP(),
                      content_hash=%s
                  WHERE id=%s
                  """,
                  (summary, model_used, content_hash, doc_id),
                )
            try:
              with get_db_connection() as conn:
                with conn.cursor() as cur:
                  cur.execute("SELECT * FROM ioffice_documents WHERE id=%s", (int(doc_id),))
                  doc2 = cur.fetchone()
              if doc2:
                from app.services.ioffice_rag import index_ioffice_summary

                index_ioffice_summary(doc2)
            except Exception:
              pass
            with self._lock:
              self._processed += 1
          except Exception as e:
            try:
              doc_id = int(doc.get("id") or 0)
            except Exception:
              doc_id = 0
            if doc_id:
              try:
                with get_db_connection() as conn:
                  with conn.cursor() as cur:
                    cur.execute(
                      "UPDATE ioffice_documents SET summary_status='FAILED', summary_error=%s, summary_updated_at=UTC_TIMESTAMP() WHERE id=%s",
                      (str(e), int(doc_id)),
                    )
              except Exception:
                pass
            with self._lock:
              self._last_error = str(e)
      except Exception as e:
        with self._lock:
          self._last_error = str(e)
      time.sleep(interval_sec)


ioffice_auto_summary_worker = IOfficeAutoSummaryWorker()
