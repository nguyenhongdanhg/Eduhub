from datetime import datetime

from app.db import get_db_connection


class IOfficeRepo:
  def upsert_account(self, *, user_id: int, school_id: int | None, username: str, password_enc: str) -> None:
    sql = """
      INSERT INTO ioffice_accounts (user_id, school_id, username, password_enc)
      VALUES (%s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        school_id=VALUES(school_id),
        username=VALUES(username),
        password_enc=VALUES(password_enc),
        updated_at=CURRENT_TIMESTAMP
    """
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (user_id, school_id, username, password_enc))

  def get_account(self, *, user_id: int) -> dict | None:
    sql = "SELECT user_id, school_id, username, password_enc, updated_at FROM ioffice_accounts WHERE user_id=%s"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        return cur.fetchone()

  def upsert_document(self, doc: dict) -> int:
    sql = """
      INSERT INTO ioffice_documents (
        school_id, ioffice_doc_id,
        so_ky_hieu, trich_yeu, hinh_thuc, ngay_van_ban, ngay_den,
        don_vi_ban_hanh, vai_tro, han_xu_ly, trang_thai_xu_ly,
        chi_dao_xl, nhiem_vu, link_goc,
        file_path, file_name,
        fetch_status, fetch_error,
        synced_at
      )
      VALUES (
        %(school_id)s, %(ioffice_doc_id)s,
        %(so_ky_hieu)s, %(trich_yeu)s, %(hinh_thuc)s, %(ngay_van_ban)s, %(ngay_den)s,
        %(don_vi_ban_hanh)s, %(vai_tro)s, %(han_xu_ly)s, %(trang_thai_xu_ly)s,
        %(chi_dao_xl)s, %(nhiem_vu)s, %(link_goc)s,
        %(file_path)s, %(file_name)s,
        %(fetch_status)s, %(fetch_error)s,
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
        synced_at=VALUES(synced_at),
        updated_at=CURRENT_TIMESTAMP
    """
    payload = {
      "school_id": doc.get("school_id"),
      "ioffice_doc_id": str(doc.get("ioffice_doc_id") or ""),
      "so_ky_hieu": doc.get("so_ky_hieu"),
      "trich_yeu": doc.get("trich_yeu"),
      "hinh_thuc": doc.get("hinh_thuc"),
      "ngay_van_ban": doc.get("ngay_van_ban"),
      "ngay_den": doc.get("ngay_den"),
      "don_vi_ban_hanh": doc.get("don_vi_ban_hanh"),
      "vai_tro": doc.get("vai_tro"),
      "han_xu_ly": doc.get("han_xu_ly"),
      "trang_thai_xu_ly": doc.get("trang_thai_xu_ly"),
      "chi_dao_xl": doc.get("chi_dao_xl"),
      "nhiem_vu": doc.get("nhiem_vu"),
      "link_goc": doc.get("link_goc"),
      "file_path": doc.get("file_path"),
      "file_name": doc.get("file_name"),
      "fetch_status": doc.get("fetch_status") or "OK",
      "fetch_error": doc.get("fetch_error"),
      "synced_at": doc.get("synced_at") or datetime.utcnow(),
    }
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, payload)
        cur.execute("SELECT id FROM ioffice_documents WHERE ioffice_doc_id=%s", (payload["ioffice_doc_id"],))
        row = cur.fetchone()
        return int(row["id"])

  def list_documents(self, *, limit: int = 100, offset: int = 0, keyword: str | None = None) -> list[dict]:
    where = []
    args: list = []
    if keyword:
      where.append("(trich_yeu LIKE %s OR so_ky_hieu LIKE %s OR don_vi_ban_hanh LIKE %s)")
      k = f"%{keyword}%"
      args.extend([k, k, k])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
      SELECT id, ioffice_doc_id, so_ky_hieu, trich_yeu, ngay_den, ngay_van_ban, don_vi_ban_hanh, vai_tro, han_xu_ly,
             fetch_status, summary_status, synced_at, updated_at
      FROM ioffice_documents
      {where_sql}
      ORDER BY synced_at DESC, id DESC
      LIMIT %s OFFSET %s
    """
    args.extend([int(limit), int(offset)])
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, tuple(args))
        return list(cur.fetchall())

  def get_document(self, *, document_id: int) -> dict | None:
    sql = "SELECT * FROM ioffice_documents WHERE id=%s"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (document_id,))
        return cur.fetchone()

  def update_summary(self, *, document_id: int, status: str, text: str | None, model: str | None, error: str | None, content_hash: str | None) -> None:
    sql = """
      UPDATE ioffice_documents
      SET summary_status=%s,
          summary_text=%s,
          summary_model=%s,
          summary_error=%s,
          summary_updated_at=CURRENT_TIMESTAMP,
          content_hash=COALESCE(%s, content_hash)
      WHERE id=%s
    """
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (status, text, model, error, content_hash, document_id))

