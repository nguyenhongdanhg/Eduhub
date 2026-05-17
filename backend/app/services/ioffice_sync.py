import os
import queue
import re
import threading
import traceback
import asyncio
import sys
from datetime import datetime

from app.services.vn_time import now_vn_iso

class IOfficeSyncService:
  def __init__(self) -> None:
    self._lock = threading.Lock()
    self._thread: threading.Thread | None = None
    self._log_thread: threading.Thread | None = None
    self._log_q: queue.Queue | None = None
    self._log_seq = 0
    self._status = {
      "running": False,
      "started_at": None,
      "ended_at": None,
      "processed": 0,
      "error": None,
      "last_line": None,
      "logs": [],
    }

  def status(self) -> dict:
    with self._lock:
      return dict(self._status)

  def stop(self) -> None:
    from fetcher.control import request_stop

    request_stop()

  def start(self, *, user_id: int, headless: bool, cats: list[str], mode: str, max_pages: int | None = None) -> bool:
    with self._lock:
      if self._thread and self._thread.is_alive():
        return False
      os.environ["EDUAI_ACTIVE_USER_ID"] = str(int(user_id))
      self._log_q = queue.Queue()
      self._status = {
        "running": True,
        "started_at": now_vn_iso(),
        "ended_at": None,
        "processed": 0,
        "error": None,
        "last_line": None,
        "logs": [],
      }
      self._thread = threading.Thread(
        target=self._run,
        kwargs={"headless": headless, "cats": cats, "mode": mode, "max_pages": max_pages},
        daemon=True,
      )
      self._thread.start()
      self._log_thread = threading.Thread(target=self._consume_logs, daemon=True)
      self._log_thread.start()
      return True

  def start_rerun(self, *, user_id: int, headless: bool, doc_ids: list[str]) -> bool:
    with self._lock:
      if self._thread and self._thread.is_alive():
        return False
      os.environ["EDUAI_ACTIVE_USER_ID"] = str(int(user_id))
      self._log_q = queue.Queue()
      self._status = {
        "running": True,
        "started_at": now_vn_iso(),
        "ended_at": None,
        "processed": 0,
        "error": None,
        "last_line": None,
        "logs": [],
      }
      self._thread = threading.Thread(
        target=self._run_rerun,
        kwargs={"doc_ids": doc_ids, "headless": headless},
        daemon=True,
      )
      self._thread.start()
      self._log_thread = threading.Thread(target=self._consume_logs, daemon=True)
      self._log_thread.start()
      return True

  def _consume_logs(self) -> None:
    if not self._log_q:
      return
    rx = re.compile(r"\[(\d+)\]\s+START process")
    while True:
      try:
        line = self._log_q.get(timeout=0.5)
      except Exception:
        with self._lock:
          if not self._status.get("running"):
            return
        continue
      inc = 1 if rx.search(str(line or "")) else 0
      with self._lock:
        if inc:
          self._status["processed"] = int(self._status.get("processed") or 0) + 1
        self._status["last_line"] = line
        logs = list(self._status.get("logs") or [])
        self._log_seq += 1
        logs.append({"id": self._log_seq, "line": line})
        self._status["logs"] = logs[-400:]

  def _run(self, *, headless: bool, cats: list[str], mode: str, max_pages: int | None) -> None:
    loop = None
    try:
      if sys.platform == "win32":
        try:
          asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
          pass
        try:
          loop = asyncio.new_event_loop()
          asyncio.set_event_loop(loop)
        except Exception:
          loop = None
      from fetcher.runner import run_fetch_all_with_queue

      run_fetch_all_with_queue(self._log_q, headless=headless, cats=cats, mode=mode, max_pages=max_pages)
    except Exception as e:
      try:
        if self._log_q:
          self._log_q.put_nowait(f"ERROR: {e}")
          tb = traceback.format_exc().strip().replace("\r", "")
          if tb:
            for ln in tb.split("\n")[-20:]:
              self._log_q.put_nowait(f"TRACE: {ln}")
      except Exception:
        pass
      with self._lock:
        self._status["error"] = str(e)
    finally:
      try:
        if loop:
          loop.close()
      except Exception:
        pass
      with self._lock:
        self._status["running"] = False
        self._status["ended_at"] = now_vn_iso()

  def _run_rerun(self, *, doc_ids: list[str], headless: bool) -> None:
    loop = None
    try:
      if sys.platform == "win32":
        try:
          asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
          pass
        try:
          loop = asyncio.new_event_loop()
          asyncio.set_event_loop(loop)
        except Exception:
          loop = None
      from fetcher.rerun import run_rerun_list

      run_rerun_list(doc_ids, self._log_q, headless=headless)
    except Exception as e:
      try:
        if self._log_q:
          self._log_q.put_nowait(f"ERROR: {e}")
          tb = traceback.format_exc().strip().replace("\r", "")
          if tb:
            for ln in tb.split("\n")[-20:]:
              self._log_q.put_nowait(f"TRACE: {ln}")
      except Exception:
        pass
      with self._lock:
        self._status["error"] = str(e)
    finally:
      try:
        if loop:
          loop.close()
      except Exception:
        pass
      with self._lock:
        self._status["running"] = False
        self._status["ended_at"] = now_vn_iso()


ioffice_sync_service = IOfficeSyncService()
