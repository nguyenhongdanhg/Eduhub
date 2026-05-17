import os
from datetime import datetime

from app.db import get_db_connection
from app.services.crypto import decrypt_text, encrypt_text


def init_db():
  return


def _ensure_user_exists(user_id: int) -> None:
  try:
    uid = int(user_id)
  except Exception:
    return
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        if row:
          return
        email = f"system+ioffice-{uid}@local"
        cur.execute(
          "INSERT INTO users (id, name, email, password_hash, status) VALUES (%s,%s,%s,%s,%s)",
          (uid, "System iOffice", email, "!", "DISABLED"),
        )
  except Exception:
    return


def get_account(user_id: int | None = None) -> dict:
  if user_id is None:
    try:
      user_id = int((os.environ.get("EDUAI_ACTIVE_USER_ID") or "1").strip() or "1")
    except Exception:
      user_id = 1
  sql = "SELECT user_id, username, password_enc FROM ioffice_accounts WHERE user_id=%s"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (int(user_id),))
      row = cur.fetchone()
  if not row:
    return {"username": "", "password": ""}
  try:
    pwd = decrypt_text(row.get("password_enc") or "")
  except Exception:
    pwd = ""
  return {"username": row.get("username") or "", "password": pwd}


def set_account(username: str, password: str, *, user_id: int = 1, school_id: int | None = None) -> None:
  _ensure_user_exists(int(user_id))
  sql = """
    INSERT INTO ioffice_accounts (user_id, school_id, username, password_enc)
    VALUES (%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
      school_id=VALUES(school_id),
      username=VALUES(username),
      password_enc=VALUES(password_enc),
      updated_at=CURRENT_TIMESTAMP
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (int(user_id), school_id, username or "", encrypt_text(password or "")))


def _map_fetch_status(s: str | None) -> str:
  v = (s or "").strip().lower()
  if v in ("ok", "success", "done", "1", "true"):
    return "OK"
  if v in ("fail", "failed", "error"):
    return "FAILED"
  if v in ("pending", ""):
    return "PENDING"
  return "OK"


def upsert_document(rec: dict, *, school_id: int | None = None) -> None:
  sql = """
    INSERT INTO ioffice_documents (
      school_id, ioffice_doc_id,
      so_ky_hieu, trich_yeu, hinh_thuc, ngay_van_ban, ngay_den,
      don_vi_ban_hanh, vai_tro, han_xu_ly, trang_thai_xu_ly,
      chi_dao_xl, nhiem_vu, link_goc,
      file_path, file_name,
      fetch_status, fetch_error, vb_status,
      synced_at
    )
    VALUES (
      %(school_id)s, %(ioffice_doc_id)s,
      %(so_ky_hieu)s, %(trich_yeu)s, %(hinh_thuc)s, %(ngay_van_ban)s, %(ngay_den)s,
      %(don_vi_ban_hanh)s, %(vai_tro)s, %(han_xu_ly)s, %(trang_thai_xu_ly)s,
      %(chi_dao_xl)s, %(nhiem_vu)s, %(link_goc)s,
      %(file_path)s, %(file_name)s,
      %(fetch_status)s, %(fetch_error)s, %(vb_status)s,
      %(synced_at)s
    )
    ON DUPLICATE KEY UPDATE
      school_id=VALUES(school_id),
      so_ky_hieu=VALUES(so_ky_hieu),
      trich_yeu=VALUES(trich_yeu),
      hinh_thuc=VALUES(hinh_thuc),
      ngay_van_ban=VALUES(ngay_van_ban),
      ngay_den=VALUES(ngay_den),
      don_vi_ban_hanh=VALUES(don_vi_ban_hanh),
      vai_tro=VALUES(vai_tro),
      han_xu_ly=VALUES(han_xu_ly),
      trang_thai_xu_ly=VALUES(trang_thai_xu_ly),
      chi_dao_xl=VALUES(chi_dao_xl),
      nhiem_vu=VALUES(nhiem_vu),
      link_goc=VALUES(link_goc),
      file_path=COALESCE(VALUES(file_path), file_path),
      file_name=COALESCE(VALUES(file_name), file_name),
      fetch_status=VALUES(fetch_status),
      fetch_error=VALUES(fetch_error),
      vb_status=VALUES(vb_status),
      synced_at=VALUES(synced_at),
      updated_at=CURRENT_TIMESTAMP
  """
  payload = {
    "school_id": school_id,
    "ioffice_doc_id": str(rec.get("doc_id") or ""),
    "so_ky_hieu": rec.get("so_ky_hieu"),
    "trich_yeu": rec.get("trich_yeu"),
    "hinh_thuc": rec.get("hinh_thuc"),
    "ngay_van_ban": rec.get("ngay_van_ban"),
    "ngay_den": rec.get("ngay_den"),
    "don_vi_ban_hanh": rec.get("don_vi_ban_hanh"),
    "vai_tro": rec.get("vai_tro"),
    "han_xu_ly": rec.get("han_xu_ly"),
    "trang_thai_xu_ly": rec.get("trang_thai_xu_ly"),
    "chi_dao_xl": rec.get("chi_dao_xl"),
    "nhiem_vu": rec.get("nhiem_vu"),
    "link_goc": rec.get("link_goc"),
    "file_path": rec.get("duong_dan_file"),
    "file_name": rec.get("ten_file"),
    "fetch_status": _map_fetch_status(rec.get("fetch_status")),
    "fetch_error": rec.get("error_msg") or "",
    "vb_status": (rec.get("vb_status") or "").strip() or None,
    "synced_at": datetime.utcnow(),
  }
  if not payload["ioffice_doc_id"]:
    return
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, payload)


def get_document(doc_id: str) -> dict | None:
  sql = "SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (str(doc_id),))
      return cur.fetchone()


def delete_document(doc_id: str) -> None:
  sql = "DELETE FROM ioffice_documents WHERE ioffice_doc_id=%s"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (str(doc_id),))


def fetch_recent(limit=500):
  sql = "SELECT * FROM ioffice_documents ORDER BY updated_at DESC, id DESC"
  args = []
  if limit is not None:
    sql += " LIMIT %s"
    args.append(int(limit))
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(args))
      return list(cur.fetchall())


def fetch_unprocessed_docs(limit=50):
  sql = """
    SELECT * FROM ioffice_documents
    WHERE (summary_text IS NULL OR summary_text='')
      AND fetch_status='OK'
    ORDER BY updated_at DESC
    LIMIT %s
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (int(limit),))
      return list(cur.fetchall())


def query_failed_docs(limit=200):
  sql = """
    SELECT * FROM ioffice_documents
    WHERE fetch_status='FAILED'
    ORDER BY updated_at DESC
    LIMIT %s
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (int(limit),))
      return list(cur.fetchall())


def stats():
  sql = "SELECT COUNT(*) AS total, SUM(fetch_status='FAILED') AS failed, SUM(fetch_status='OK') AS ok FROM ioffice_documents"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql)
      row = cur.fetchone() or {}
      return {"total": int(row.get("total") or 0), "ok": int(row.get("ok") or 0), "failed": int(row.get("failed") or 0)}


def role_counts():
  sql = "SELECT COALESCE(vai_tro,'') AS role, COUNT(*) AS cnt FROM ioffice_documents GROUP BY COALESCE(vai_tro,'') ORDER BY cnt DESC"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql)
      return list(cur.fetchall())


def query_docs_by_date(date_str: str):
  sql = "SELECT * FROM ioffice_documents WHERE ngay_den=%s OR ngay_van_ban=%s ORDER BY updated_at DESC"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (date_str, date_str))
      return list(cur.fetchall())


def delete_embedding(_doc_id: str):
  return
