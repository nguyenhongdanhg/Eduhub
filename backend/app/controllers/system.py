import time
from datetime import datetime, timezone

from fastapi import APIRouter

from app.db import get_db_connection
from app.services.qdrant_rest import QdrantRestClient
from app.services.vn_time import now_vn_iso

router = APIRouter()


@router.get("/users")
def list_users():
  return {"items": []}


@router.get("/status")
def system_status():
  api_start = time.perf_counter()
  checked_at = now_vn_iso()

  mariadb_start = time.perf_counter()
  mariadb_ok = False
  conn = None
  try:
    conn = get_db_connection()
    with conn.cursor() as cur:
      cur.execute("SELECT 1 AS ok")
      cur.fetchone()
    mariadb_ok = True
  except Exception:
    mariadb_ok = False
  finally:
    try:
      if conn is not None:
        conn.close()
    except Exception:
      pass
  mariadb_latency_ms = int((time.perf_counter() - mariadb_start) * 1000)

  qdrant_start = time.perf_counter()
  qdrant_ok = False
  try:
    qdrant_ok = QdrantRestClient().ready(timeout_sec=2.5)
  except Exception:
    qdrant_ok = False
  qdrant_latency_ms = int((time.perf_counter() - qdrant_start) * 1000)

  api_latency_ms = int((time.perf_counter() - api_start) * 1000)

  return {
    "checked_at": checked_at,
    "services": {
      "api": {"ok": True, "latency_ms": api_latency_ms},
      "mariadb": {"ok": mariadb_ok, "latency_ms": mariadb_latency_ms},
      "qdrant": {"ok": qdrant_ok, "latency_ms": qdrant_latency_ms},
    },
  }
