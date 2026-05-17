import os
import threading
import urllib.parse
import uuid
import zipfile
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, PlainTextResponse, Response
from pydantic import BaseModel

from app.services.ioffice_sync import ioffice_sync_service
from app.services.ioffice_summary import summarize_document
from app.services.document_categories_repo import DocumentCategoriesRepo
from app.services.audit_repo import AuditRepo
from utils import FILES_ROOT, ensure_dir, make_safe_relative_from_any

router = APIRouter()
_ai_lock = threading.Lock()
_ai_thread: threading.Thread | None = None
_ioffice_doc_cols: set[str] | None = None


def _user_id(x_user_id: str | None) -> int:
  try:
    return int(x_user_id or "1")
  except Exception:
    return 1


def _normalize_and_validate(filepath_raw: str) -> str:
  p = urllib.parse.unquote(filepath_raw or "")
  p = p.replace("\\", "/")
  p = p.lstrip("/")
  try:
    rel = make_safe_relative_from_any(p)
  except Exception:
    lowered = p.lower()
    if "ioffice/" in lowered:
      idx = lowered.find("ioffice/")
      rel = p[idx + 7 :]
    elif "files/" in lowered:
      idx = lowered.find("files/")
      rel = p[idx + 6 :]
    else:
      rel = Path(p).name if ":" in p else p
  rel = rel.strip("/ ")
  rel_path = Path(rel)
  return "/".join(rel_path.parts)


def _get_ioffice_document_columns() -> set[str]:
  global _ioffice_doc_cols
  if _ioffice_doc_cols is not None:
    return _ioffice_doc_cols
  from app.db import get_db_connection

  cols: set[str] = set()
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
          ("ioffice_documents",),
        )
        cols = {str(r.get("COLUMN_NAME") or "") for r in cur.fetchall()}
  except Exception:
    cols = set()
  _ioffice_doc_cols = cols
  return cols


def _sel_optional(col: str, alias: str | None = None) -> str:
  cols = _get_ioffice_document_columns()
  if col in cols:
    return f"{col} AS {alias}" if alias else col
  return f"NULL AS {alias or col}"


class AccountUpsert(BaseModel):
  school_id: int | None = None
  username: str
  password: str


@router.get("/account")
def get_account(x_user_id: str | None = Header(default=None)):
  import database as iodb

  uid = _user_id(x_user_id)
  row = iodb.get_account(uid)
  return {"username": row.get("username") or "", "has_password": bool(row.get("password")), "school_id": None}


@router.post("/account")
def set_account(payload: AccountUpsert, request: Request, x_user_id: str | None = Header(default=None)):
  if not payload.username.strip() or not payload.password.strip():
    raise HTTPException(status_code=400, detail="missing_username_or_password")
  uid = _user_id(x_user_id)
  import database as iodb

  iodb.set_account(payload.username.strip(), payload.password.strip(), user_id=uid, school_id=payload.school_id)
  AuditRepo().log(action="ioffice.account.set", user_id=uid, payload={"school_id": payload.school_id, "username": payload.username.strip()}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"ok": True}


class SyncStart(BaseModel):
  headless: bool = True
  cats: list[str] = ["CHO_XU_LY", "XEM_DE_BIET", "DA_XU_LY"]
  mode: str = "update"
  max_pages: int | None = None


class RerunBody(BaseModel):
  headless: bool = True
  doc_ids: list[str]


@router.post("/sync/start")
def start_sync(payload: SyncStart, request: Request, x_user_id: str | None = Header(default=None)):
  uid = _user_id(x_user_id)
  ok = ioffice_sync_service.start(
    user_id=uid,
    headless=payload.headless,
    cats=payload.cats,
    mode=(payload.mode or "update").strip().lower(),
    max_pages=payload.max_pages,
  )
  AuditRepo().log(action="ioffice.sync.start", user_id=uid, payload={"mode": payload.mode, "cats": payload.cats, "headless": payload.headless, "max_pages": payload.max_pages}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"started": ok}


@router.post("/sync/stop")
def stop_sync(request: Request, x_user_id: str | None = Header(default=None)):
  ioffice_sync_service.stop()
  AuditRepo().log(action="ioffice.sync.stop", user_id=_user_id(x_user_id), payload={}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"stopped": True}


@router.post("/sync/rerun")
def rerun(payload: RerunBody, request: Request, x_user_id: str | None = Header(default=None)):
  uid = _user_id(x_user_id)
  ok = ioffice_sync_service.start_rerun(user_id=uid, headless=payload.headless, doc_ids=payload.doc_ids)
  AuditRepo().log(action="ioffice.sync.rerun", user_id=uid, payload={"count": len(payload.doc_ids or [])}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"started": ok}


@router.post("/sync/rerun-failed")
def rerun_failed(request: Request, x_user_id: str | None = Header(default=None)):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT ioffice_doc_id FROM ioffice_documents WHERE fetch_status='FAILED' ORDER BY updated_at DESC LIMIT 2000")
      ids = [str(r.get("ioffice_doc_id")) for r in cur.fetchall() if r.get("ioffice_doc_id")]
  if not ids:
    return {"started": False, "rerun_count": 0}
  ok = ioffice_sync_service.start_rerun(user_id=uid, headless=True, doc_ids=ids)
  AuditRepo().log(action="ioffice.sync.rerun_failed", user_id=uid, payload={"rerun_count": len(ids)}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"started": ok, "rerun_count": len(ids)}


@router.get("/sync/status")
def sync_status():
  return ioffice_sync_service.status()


@router.get("/ui/config")
def ui_get_config(x_user_id: str | None = Header(default=None)):
  import database as iodb

  uid = _user_id(x_user_id)
  acc = iodb.get_account(uid)
  return {"username": acc.get("username") or "", "has_password": bool(acc.get("password"))}


class UiConfigBody(BaseModel):
  username: str = ""
  password: str = ""


@router.post("/ui/config")
def ui_set_config(payload: UiConfigBody, x_user_id: str | None = Header(default=None)):
  import database as iodb

  uid = _user_id(x_user_id)
  try:
    iodb.set_account((payload.username or "").strip(), (payload.password or "").strip(), user_id=uid)
    return {"ok": True}
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


class UiStartBody(BaseModel):
  headless: bool = True
  cats: list[str] | None = None
  mode: str = "update"
  max_pages: int | None = None


@router.post("/ui/start")
def ui_start(payload: UiStartBody, x_user_id: str | None = Header(default=None)):
  import database as iodb

  uid = _user_id(x_user_id)
  acc = iodb.get_account(uid)
  if not (acc.get("username") and acc.get("password")):
    return {"started": False, "reason": "missing_account"}
  try:
    import playwright
    _ = playwright
  except Exception:
    return {
      "started": False,
      "reason": "missing_playwright",
      "message": "Thiếu thư viện playwright. Chạy: cd backend; pip install -r requirements.txt; python -m playwright install",
    }
  cats = payload.cats or ["CHO_XU_LY", "XEM_DE_BIET", "DA_XU_LY"]
  mode = (payload.mode or "update").strip().lower()
  if mode == "update":
    try:
      from app.db import get_db_connection

      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT COUNT(*) AS c FROM ioffice_documents")
          c = int((cur.fetchone() or {}).get("c") or 0)
      if c <= 0:
        mode = "full"
    except Exception:
      pass
  ok = ioffice_sync_service.start(user_id=uid, headless=payload.headless, cats=cats, mode=mode, max_pages=payload.max_pages)
  return {"started": ok}


@router.post("/ui/stop")
def ui_stop():
  ioffice_sync_service.stop()
  return {"stopped": True}


@router.get("/ui/fetch_status")
def ui_fetch_status():
  st = ioffice_sync_service.status()
  return {"running": bool(st.get("running"))}


@router.post("/ui/rerun_failed")
def ui_rerun_failed(x_user_id: str | None = Header(default=None)):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT ioffice_doc_id FROM ioffice_documents WHERE fetch_status='FAILED' ORDER BY updated_at DESC LIMIT 2000")
      ids = [str(r.get("ioffice_doc_id")) for r in cur.fetchall() if r.get("ioffice_doc_id")]
  if not ids:
    return {"rerun_count": 0}
  ok = ioffice_sync_service.start_rerun(user_id=uid, headless=True, doc_ids=ids)
  return {"rerun_count": len(ids), "started": ok}


@router.get("/ui/recent")
def ui_recent(
  limit: int = 1000,
  offset: int | None = None,
  vb_tab: str | None = None,
  role: str | None = None,
  q: str | None = None,
  sort_key: str | None = None,
  sort_dir: str | None = None,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  try:
    limit2 = int(limit or 0)
  except Exception:
    limit2 = 0
  if limit2 <= 0:
    limit2 = 20
  if limit2 > 2000:
    limit2 = 2000
  paged = offset is not None
  offset2 = 0
  if paged:
    try:
      offset2 = int(offset or 0)
    except Exception:
      offset2 = 0
    if offset2 < 0:
      offset2 = 0

  where = []
  args: list = []
  if vb_tab and vb_tab != "ALL":
    where.append("vb_status=%s")
    args.append(vb_tab)
  if role:
    if role == "OTHER":
      where.append("(vai_tro IS NULL OR (UPPER(vai_tro) NOT LIKE 'XLC%' AND UPPER(vai_tro) NOT LIKE 'PH%'))")
    else:
      where.append("UPPER(vai_tro) LIKE %s")
      args.append(f"{role}%")
  if q:
    cols = _get_ioffice_document_columns()
    parts = ["trich_yeu LIKE %s", "so_ky_hieu LIKE %s", "don_vi_ban_hanh LIKE %s"]
    if "summary_text" in cols:
      parts.append("summary_text LIKE %s")
    where.append("(" + " OR ".join(parts) + ")")
    k = f"%{q}%"
    args.extend([k] * len(parts))
  where_sql = f"WHERE {' AND '.join(where)}" if where else ""

  sort_key2 = str(sort_key or "").strip().lower()
  sort_dir2 = str(sort_dir or "").strip().lower()
  dir_sql = "ASC" if sort_dir2 == "asc" else "DESC"
  cols = _get_ioffice_document_columns()

  def _to_dt_expr(col: str) -> str:
    v = f"NULLIF({col}, '')"
    return f"COALESCE(STR_TO_DATE({v}, '%%d/%%m/%%Y %%H:%%i:%%s'), STR_TO_DATE({v}, '%%d/%%m/%%Y'))"

  dt_parts = []
  if "ngay_van_ban" in cols:
    dt_parts.append(_to_dt_expr("ngay_van_ban"))
  if "ngay_den" in cols:
    dt_parts.append(_to_dt_expr("ngay_den"))
  dt_parts.append("updated_at")
  time_expr = f"COALESCE({', '.join(dt_parts)})" if len(dt_parts) > 1 else dt_parts[0]

  order_sql = f"{time_expr} DESC, updated_at DESC, id DESC"
  if sort_key2 in ("time", "tgian", "vb_time", "vbtime", "ngay_vb", "ngayvb"):
    order_sql = f"{time_expr} {dir_sql}, updated_at DESC, id DESC"

  total = 0
  if paged:
    sql_count = f"SELECT COUNT(*) AS cnt FROM ioffice_documents {where_sql}"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql_count, tuple(args))
        total = int((cur.fetchone() or {}).get("cnt") or 0)

  select_trang_thai = _sel_optional("trang_thai_xu_ly")
  select_chi_dao = _sel_optional("chi_dao_xl")
  select_nhiem_vu = _sel_optional("nhiem_vu")
  select_nhiem_vu_more = _sel_optional("nhiem_vu_more")
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  select_summary_status = _sel_optional("summary_status", "ai_status")
  select_summary_error = _sel_optional("summary_error", "ai_error")
  select_summary_model = _sel_optional("summary_model", "ai_model")
  sql = f"""
    SELECT
      id AS row_id,
      ioffice_doc_id AS doc_id,
      so_ky_hieu,
      trich_yeu,
      hinh_thuc,
      ngay_van_ban,
      ngay_den,
      don_vi_ban_hanh,
      vai_tro,
      han_xu_ly,
      {select_trang_thai},
      {select_chi_dao},
      {select_nhiem_vu},
      {select_nhiem_vu_more},
      link_goc,
      file_path AS duong_dan_file,
      file_name AS ten_file,
      {select_summary_text},
      {select_summary_status},
      {select_summary_error},
      {select_summary_model},
      'ui' AS ai_source,
      CASE fetch_status WHEN 'OK' THEN 'ok' WHEN 'FAILED' THEN 'fail' ELSE 'pending' END AS fetch_status,
      fetch_error AS error_msg,
      vb_status,
      DATE_FORMAT(updated_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
    FROM ioffice_documents
    {where_sql}
    ORDER BY {order_sql}
    LIMIT %s
  """
  if paged:
    sql += " OFFSET %s"
    args2 = list(args) + [int(limit2), int(offset2)]
  else:
    args2 = list(args) + [int(limit2)]
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(args2))
      rows = list(cur.fetchall())
  uid = _user_id(x_user_id)
  try:
    DocumentCategoriesRepo().ensure_default_categories(user_id=uid)
  except Exception:
    pass
  try:
    ids = [int(r.get("row_id") or 0) for r in rows if int(r.get("row_id") or 0) > 0]
  except Exception:
    ids = []
  cat_map: dict[int, list[dict]] = {}
  if ids:
    try:
      in_sql = ",".join(["%s"] * len(ids))
      sql2 = f"""
        SELECT i.ioffice_document_id AS doc_row_id, c.id AS category_id, c.name, c.parent_id
        FROM document_category_items i
        JOIN document_categories c ON c.id=i.category_id
        WHERE c.user_id=%s AND i.ioffice_document_id IN ({in_sql})
        ORDER BY c.sort_order ASC, c.id ASC
      """
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(sql2, tuple([uid] + ids))
          for it in cur.fetchall() or []:
            did = int(it.get("doc_row_id") or 0)
            cid = int(it.get("category_id") or 0)
            name = str(it.get("name") or "").strip()
            try:
              pid = int(it.get("parent_id") or 0)
            except Exception:
              pid = 0
            if did and cid and name:
              cat_map.setdefault(did, []).append({"id": cid, "name": name, "parent_id": (pid or None)})
    except Exception:
      cat_map = {}
  for r in rows:
    p = r.get("duong_dan_file") or ""
    if p:
      r["duong_dan_file"] = make_safe_relative_from_any(p)
    try:
      did = int(r.get("row_id") or 0)
    except Exception:
      did = 0
    items = cat_map.get(did) or []
    r["cong_viec"] = items
    r["loai_vb"] = ", ".join([str(x.get("name") or "").strip() for x in items if str(x.get("name") or "").strip()])
  if not paged:
    return rows
  return {"ok": True, "items": rows, "total": total, "limit": limit2, "offset": offset2}


@router.delete("/ui/documents/{doc_id}")
def ui_delete_document(doc_id: str):
  from app.db import get_db_connection
  from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

  did = (doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT id FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  rid = int(row.get("id") or 0)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      if rid:
        cur.execute("DELETE FROM document_category_items WHERE ioffice_document_id=%s", (rid,))
      cur.execute("DELETE FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
  try:
    mode = (os.getenv("EDUAI_IOFFICE_DELETE_CASCADE_RAG") or "hard").strip().lower()
    if mode in ("soft", "hard", "purge", "qdrant"):
      ioffice_rag_ingestor.delete_all_for_ioffice_doc_id(did, mode=mode)
  except Exception:
    pass
  return {"ok": True}


@router.get("/ui/document/{doc_id}")
def ui_document(doc_id: str):
  from app.db import get_db_connection

  did = (doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  select_summary_status = _sel_optional("summary_status", "ai_status")
  select_summary_error = _sel_optional("summary_error", "ai_error")
  select_summary_model = _sel_optional("summary_model", "ai_model")
  sql = f"""
    SELECT
      id AS row_id,
      ioffice_doc_id AS doc_id,
      so_ky_hieu,
      trich_yeu,
      don_vi_ban_hanh,
      ngay_den,
      ngay_van_ban,
      han_xu_ly,
      link_goc,
      file_path AS duong_dan_file,
      file_name AS ten_file,
      {select_summary_text},
      {select_summary_status},
      {select_summary_error},
      {select_summary_model},
      fetch_status,
      fetch_error
    FROM ioffice_documents
    WHERE ioffice_doc_id=%s
    LIMIT 1
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (did,))
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  p = (row.get("duong_dan_file") or "").strip()
  if p:
    try:
      row["duong_dan_file"] = make_safe_relative_from_any(p)
    except Exception:
      row["duong_dan_file"] = ""
  return {"ok": True, "item": row}


@router.get("/ui/zip_members")
def ui_zip_members(doc_id: str):
  from app.db import get_db_connection

  did = (doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        "SELECT id, ioffice_doc_id, so_ky_hieu, trich_yeu, han_xu_ly, file_path FROM ioffice_documents WHERE ioffice_doc_id=%s",
        (did,),
      )
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  path = (row.get("file_path") or "").strip()
  if not path or not str(path).lower().endswith(".zip"):
    raise HTTPException(status_code=400, detail="not_zip")
  safe = _normalize_and_validate(path)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="file_not_found")
  try:
    with zipfile.ZipFile(str(full), "r") as z:
      members = [m for m in z.namelist() if m and not m.endswith("/")]
    return {
      "ok": True,
      "doc_id": row.get("ioffice_doc_id"),
      "so_ky_hieu": row.get("so_ky_hieu") or "",
      "trich_yeu": row.get("trich_yeu") or "",
      "han_xu_ly": row.get("han_xu_ly") or "",
      "members": members,
    }
  except zipfile.BadZipFile:
    raise HTTPException(status_code=400, detail="bad_zip")


@router.get("/ui/ai_providers")
def ui_ai_providers(mode: str | None = None):
  from app.services.db_keyring import get_ring
  from app.services.llm_client import resolve_generate_provider, resolve_summary_provider
  from app.services.llm_client import _get_db_config

  is_generate = (mode or "").strip().lower() in ("gen", "generate", "generation")
  models = [{"value": "", "label": "Tự động"}]
  provider = resolve_generate_provider(None) if is_generate else resolve_summary_provider(None)
  model_override = (_get_db_config("AI_GENERATE_MODEL") or "").strip() if is_generate else ""
  has_openai_compat = bool(get_ring("AI_OPENAI_API_KEY").list_keys())
  has_deepseek = bool(get_ring("AI_DEEPSEEK_API_KEY").list_keys())
  has_gemini = bool(get_ring("AI_GEMINI_API_KEY").list_keys())
  llm_enabled = False

  if provider in ("auto", ""):
    if has_openai_compat or has_deepseek or has_gemini:
      llm_enabled = True
      if has_openai_compat:
        configured = (model_override or _get_db_config("AI_OPENAI_MODEL") or "gpt-4o-mini").strip()
        models.append({"value": configured, "label": "OpenAI-compatible (auto)"})
      if has_deepseek:
        configured = (model_override or _get_db_config("AI_DEEPSEEK_MODEL") or "deepseek-chat").strip()
        models.append({"value": configured, "label": "DeepSeek (auto)"})
      if has_gemini:
        configured = (model_override or _get_db_config("AI_GEMINI_MODEL") or "gemini-1.5-flash").strip()
        models.append({"value": configured, "label": "Gemini (auto)"})
      return {"ok": True, "models": models, "provider": "auto", "enabled": True}
    return {"ok": True, "models": models, "provider": "fallback", "enabled": False}
  if provider in ("openai", "openai_compatible") and has_openai_compat:
    llm_enabled = True
    configured = (model_override or _get_db_config("AI_OPENAI_MODEL") or "gpt-4o-mini").strip()
    models.append({"value": configured, "label": "OpenAI-compatible (theo cấu hình)"})
    models.append({"value": "gpt-4o-mini", "label": "gpt-4o-mini"})
    models.append({"value": "gpt-4o", "label": "gpt-4o"})
  if provider == "deepseek" and has_deepseek:
    llm_enabled = True
    configured = (model_override or _get_db_config("AI_DEEPSEEK_MODEL") or "deepseek-chat").strip()
    models.append({"value": configured, "label": "DeepSeek (theo cấu hình)"})
    models.append({"value": "deepseek-chat", "label": "deepseek-chat"})
    models.append({"value": "deepseek-reasoner", "label": "deepseek-reasoner"})
  if provider == "gemini" and has_gemini:
    llm_enabled = True
    configured = (model_override or _get_db_config("AI_GEMINI_MODEL") or "gemini-1.5-flash").strip()
    models.append({"value": configured, "label": "Gemini (theo cấu hình)"})
    models.append({"value": "gemini-1.5-flash", "label": "gemini-1.5-flash"})
    models.append({"value": "gemini-1.5-pro", "label": "gemini-1.5-pro"})
    models.append({"value": "gemini-2.0-flash", "label": "gemini-2.0-flash"})
  return {"ok": True, "models": models, "provider": provider, "enabled": llm_enabled}


@router.get("/ui/local_config_status")
def ui_local_config_status():
  from app.services.db_keyring import get_ring
  from app.services.llm_client import resolve_summary_provider

  openai = len(get_ring("AI_OPENAI_API_KEY").list_keys())
  openrouter = 0
  gemini = len(get_ring("AI_GEMINI_API_KEY").list_keys())
  deepseek = len(get_ring("AI_DEEPSEEK_API_KEY").list_keys())
  provider = resolve_summary_provider(None)
  return {
    "ok": True,
    "provider_resolved": provider,
    "keys": {
      "OPENAI_API_KEYS": openai,
      "OPEN_ROUTER_API_KEYS": openrouter,
      "GEMINI_API_KEYS": gemini,
      "DEEPSEEK_API_KEYS": deepseek,
    },
    "has_any_key": bool(openai or openrouter or gemini or deepseek),
  }


@router.get("/ui/summary_prompts")
def ui_summary_prompts():
  from app.services.ioffice_prompt_store import list_prompt_presets

  rows = list_prompt_presets()
  enabled = [r for r in (rows or []) if isinstance(r, dict) and r.get("id") and r.get("prompt") and bool(r.get("enabled"))]
  meta = [{"id": str(r.get("id")), "label": str(r.get("label") or r.get("id"))} for r in enabled]
  prompts = {str(r.get("id")): str(r.get("prompt") or "") for r in enabled}
  return {"ok": True, "prompts": prompts, "presets": meta}


@router.get("/ui/prompt_presets")
def ui_prompt_presets():
  from app.services.ioffice_prompt_store import list_prompt_presets

  return {"ok": True, "presets": list_prompt_presets()}


class UiPromptPresetBody(BaseModel):
  id: str
  label: str
  prompt: str
  enabled: bool | None = True
  sort_order: int | None = 0


@router.post("/ui/prompt_presets")
def ui_prompt_presets_upsert(payload: UiPromptPresetBody):
  from app.services.ioffice_prompt_store import upsert_prompt_preset

  try:
    upsert_prompt_preset(
      pid=str(payload.id),
      label=str(payload.label),
      prompt=str(payload.prompt),
      enabled=bool(payload.enabled) if payload.enabled is not None else True,
      sort_order=int(payload.sort_order or 0),
    )
    return {"ok": True}
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.delete("/ui/prompt_presets/{preset_id}")
def ui_prompt_presets_delete(preset_id: str):
  from app.services.ioffice_prompt_store import delete_prompt_preset

  try:
    delete_prompt_preset(preset_id)
    return {"ok": True}
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


class UiDocTextBody(BaseModel):
  doc_id: str
  members: list[str] | None = None
  max_chars: int | None = None


@router.post("/ui/doc_text")
def ui_doc_text(payload: UiDocTextBody):
  from app.db import get_db_connection
  from ai_summary_compat import extract_text_from_zip_selected

  did = (payload.doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT ioffice_doc_id, file_path FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  path = (row.get("file_path") or "").strip()
  if not path or not str(path).lower().endswith(".zip"):
    raise HTTPException(status_code=400, detail="not_zip")
  safe = _normalize_and_validate(path)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="file_not_found")
  text = extract_text_from_zip_selected(full, payload.members)
  max_chars = int(payload.max_chars or 50000)
  if max_chars < 2000:
    max_chars = 2000
  truncated = False
  if len(text) > max_chars:
    text = text[:max_chars]
    truncated = True
  return {"ok": True, "doc_id": did, "text": text, "truncated": truncated, "max_chars": max_chars}


@router.get("/ui/tts_status")
def ui_tts_status():
  from app.services.tts_client import tts_available

  provider = (os.getenv("EDUAI_TTS_PROVIDER") or "").strip().lower()
  if not provider:
    provider = "browser"
  return {"ok": True, "available": bool(tts_available()), "provider": provider}


class UiSummaryAudioBody(BaseModel):
  doc_id: str
  voice: str | None = None
  model: str | None = None


@router.post("/ui/summary_audio")
def ui_summary_audio(payload: UiSummaryAudioBody):
  from app.db import get_db_connection
  from app.services.tts_client import tts_available, tts_speak

  did = (payload.doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  if not tts_available():
    raise HTTPException(status_code=400, detail="TTS service requires OpenAI API key. Configure EDUAI_TTS_PROVIDER=openai and provide OpenAI API key in system configuration.")
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(f"SELECT ioffice_doc_id, {select_summary_text} FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  text = (row.get("ai_summary") or "").strip()
  if not text:
    raise HTTPException(status_code=400, detail="missing_summary")
  try:
    audio, mime, fmt = tts_speak(text, voice=payload.voice, model=payload.model, fmt="mp3")
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
  if not audio:
    raise HTTPException(status_code=500, detail="tts_empty_audio")
  filename = f"summary_{did}.{fmt}"
  return Response(content=audio, media_type=mime, headers={"Content-Disposition": f'inline; filename="{filename}"'})


class UiAudioDocBody(BaseModel):
  doc_id: str | int


@router.post("/ui/audio_doc")
def ui_audio_doc(payload: UiAudioDocBody):
  from app.services.ioffice_audio import request_summary_audio

  try:
    return request_summary_audio(str(payload.doc_id))
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.get("/ui/audio_status")
def ui_audio_status(doc_id: str):
  from app.services.ioffice_audio import get_audio_status

  try:
    return get_audio_status(str(doc_id))
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.get("/ui/rag_status")
def ui_rag_status():
  from app.services.embedding_client import embedding_available
  from app.services.qdrant_rest import QdrantRestClient
  from app.services.rag_conventions import collection_for_domain

  qdrant_ok = False
  qdrant_error = None
  collections: list[str] = []
  try:
    q = QdrantRestClient()
    collections = q.list_collections()
    qdrant_ok = True
  except Exception as e:
    qdrant_error = str(e)
  return {
    "ok": True,
    "embedding_available": bool(embedding_available()),
    "qdrant_ok": bool(qdrant_ok),
    "qdrant_error": qdrant_error,
    "management_collection": collection_for_domain("MANAGEMENT"),
    "collections": collections,
  }


@router.get("/ui/rag_worker_status")
def ui_rag_worker_status(doc_id: str | None = None):
  from app.db import get_db_connection
  from app.services.embedding_client import embedding_available
  from app.services.ioffice_rag import SOURCE_IOFFICE, TYPE_IOFFICE_CHUNK, TYPE_IOFFICE_SUMMARY
  from app.services.ioffice_rag_worker import ioffice_rag_worker

  did = (doc_id or "").strip()
  original_id = ""
  if did:
    original_id = f"ioffice:{did.split(':', 1)[1].strip()}" if did.lower().startswith("ioffice:") else f"ioffice:{did}"

  stats2 = {"pending": 0, "processing": 0, "ready": 0, "failed": 0, "deleted": 0}
  stats1 = {"pending": 0, "processing": 0, "ready": 0, "failed": 0, "deleted": 0}
  per_doc2: list[dict] = []
  per_doc1: list[dict] = []
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT status, COUNT(*) AS c
        FROM rag_documents
        WHERE deleted_at IS NULL AND source=%s AND type IN (%s,%s)
        GROUP BY status
        """,
        (SOURCE_IOFFICE, TYPE_IOFFICE_CHUNK, TYPE_IOFFICE_SUMMARY),
      )
      for r in cur.fetchall() or []:
        st = str((r.get("status") or "")).strip().lower()
        c = int(r.get("c") or 0)
        if st in stats2:
          stats2[st] = c
        if st in stats1:
          stats1[st] = c
  if original_id:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          """
          SELECT id, domain, status, chunk_count, last_error, updated_at
          FROM rag_documents
          WHERE source=%s AND type=%s AND original_id=%s
          ORDER BY id DESC
          """,
          (SOURCE_IOFFICE, TYPE_IOFFICE_CHUNK, original_id),
        )
        per_doc2 = list(cur.fetchall() or [])
        cur.execute(
          """
          SELECT id, domain, status, chunk_count, last_error, updated_at
          FROM rag_documents
          WHERE source=%s AND type=%s AND original_id=%s
          ORDER BY id DESC
          """,
          (SOURCE_IOFFICE, TYPE_IOFFICE_SUMMARY, original_id),
        )
        per_doc1 = list(cur.fetchall() or [])

  return {
    "ok": True,
    "embedding_available": bool(embedding_available()),
    "worker": ioffice_rag_worker.status(),
    "level1": {"type": TYPE_IOFFICE_SUMMARY, "stats": stats1, "original_id": (original_id or None), "documents": per_doc1},
    "level2": {"type": TYPE_IOFFICE_CHUNK, "stats": stats2, "original_id": (original_id or None), "documents": per_doc2},
  }


class UiSemanticSearchBody(BaseModel):
  query: str
  limit: int | None = None
  score_threshold: float | None = None
  role: str | None = None


@router.post("/ui/semantic_search")
def ui_semantic_search(payload: UiSemanticSearchBody):
  from app.db import get_db_connection
  from app.services.embedding_client import embedding_available
  from app.services.embedding_client import embed_text_query
  from app.services.qdrant_rest import QdrantRestClient
  from app.services.rag_conventions import collection_for_domain

  q = (payload.query or "").strip()
  if not q:
    raise HTTPException(status_code=400, detail="missing_query")
  if not embedding_available():
    raise HTTPException(status_code=400, detail="embedding_unavailable")
  if payload.limit is None:
    words = len([x for x in q.split() if x.strip()])
    limit = 3 + int(words / 6)
    if limit < 3:
      limit = 3
    if limit > 20:
      limit = 20
  else:
    limit = int(payload.limit or 10)
    if limit < 1:
      limit = 1
    if limit > 50:
      limit = 50
  role = (payload.role or "").strip() or "principal"

  try:
    vector, embed_model = embed_text_query(q)
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
  collection = collection_for_domain("MANAGEMENT")
  qdrant = QdrantRestClient()
  filter_ = {
    "must": [
      {"key": "domain", "match": {"value": "MANAGEMENT"}},
      {"key": "source", "match": {"value": "IOFFICE"}},
      {"key": "type", "match": {"value": "official_document_summary"}},
      {"key": "role_allowed", "match": {"any": [role]}},
    ]
  }
  try:
    hits = qdrant.search_points(
      collection=collection,
      vector=vector,
      limit=limit,
      score_threshold=payload.score_threshold,
      filter_=filter_,
      with_payload=True,
    )
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
  ioffice_ids: list[str] = []
  scores: dict[str, float] = {}
  for h in hits:
    pl = h.get("payload") if isinstance(h, dict) else None
    if not isinstance(pl, dict):
      continue
    oid = str(pl.get("original_id") or "").strip()
    if oid.startswith("ioffice:"):
      did = oid.split(":", 1)[1]
    else:
      did = oid
    if not did:
      continue
    ioffice_ids.append(did)
    try:
      scores[did] = float(h.get("score") or 0.0)
    except Exception:
      scores[did] = 0.0

  if not ioffice_ids:
    return {"ok": True, "embed_model": embed_model, "items": []}

  placeholders = ",".join(["%s"] * len(ioffice_ids))
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  sql = f"""
    SELECT ioffice_doc_id AS doc_id, so_ky_hieu, trich_yeu, ngay_den, han_xu_ly, {select_summary_text}
    FROM ioffice_documents
    WHERE ioffice_doc_id IN ({placeholders})
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(ioffice_ids))
      rows = list(cur.fetchall())

  by_id = {str(r.get("doc_id")): r for r in rows if isinstance(r, dict) and r.get("doc_id")}
  items = []
  for did in ioffice_ids:
    r = by_id.get(str(did))
    if not r:
      continue
    items.append(
      {
        "doc_id": did,
        "score": scores.get(did, 0.0),
        "so_ky_hieu": r.get("so_ky_hieu") or "",
        "trich_yeu": r.get("trich_yeu") or "",
        "ngay_den": r.get("ngay_den") or "",
        "han_xu_ly": r.get("han_xu_ly") or "",
        "summary_text": r.get("ai_summary") or "",
      }
    )

  items.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
  return {"ok": True, "embed_model": embed_model, "items": items}


@router.get("/ui/search_vector")
def ui_search_vector(
  q: str,
  k: int | None = None,
  auto_summ: int = 0,
  score_threshold: float | None = None,
  role: str | None = None,
  work_ids: str | None = None,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection
  from app.services.embedding_client import embedding_available, embed_text_query
  from app.services.qdrant_rest import QdrantRestClient
  from app.services.rag_conventions import collection_for_domain

  query = (q or "").strip()
  if not query:
    raise HTTPException(status_code=400, detail="missing_query")

  if k is None:
    words = len([x for x in query.split() if x.strip()])
    limit = 3 + int(words / 6)
    if limit < 3:
      limit = 3
    if limit > 20:
      limit = 20
  else:
    limit = int(k or 15)
    if limit < 1:
      limit = 1
    if limit > 50:
      limit = 50

  role2 = (role or "").strip() or "principal"

  embed_model = "keyword"
  raw_items: list[dict] = []
  if embedding_available():
    try:
      vector, embed_model = embed_text_query(query)
      collection = collection_for_domain("MANAGEMENT")
      qdrant = QdrantRestClient()
      filter_ = {
        "must": [
          {"key": "domain", "match": {"value": "MANAGEMENT"}},
          {"key": "source", "match": {"value": "IOFFICE"}},
          {"key": "type", "match": {"value": "official_document_summary"}},
          {"key": "role_allowed", "match": {"any": [role2]}},
        ]
      }
      hits = qdrant.search_points(collection=collection, vector=vector, limit=limit, score_threshold=None, filter_=filter_, with_payload=True)
      for h in hits:
        pl = h.get("payload") if isinstance(h, dict) else None
        if not isinstance(pl, dict):
          continue
        oid = str(pl.get("original_id") or "").strip()
        if oid.startswith("ioffice:"):
          did = oid.split(":", 1)[1]
        else:
          did = oid
        if not did:
          continue
        try:
          sc = float(h.get("score") or 0.0)
        except Exception:
          sc = 0.0
        raw_items.append({"doc_id": did, "score": sc})
    except Exception:
      pass # Semantic search failed, but we continue to keyword search

  # ALWAYS run keyword search to supplement semantic results
  # This fixes cases where exact phrases are missed by semantic search
  if True:
    cols = _get_ioffice_document_columns()
    summary_col = "summary_text" if "summary_text" in cols else ("ai_summary" if "ai_summary" in cols else "")
    like = f"%{query}%"

    where_parts = ["(d.ioffice_doc_id LIKE %s OR d.so_ky_hieu LIKE %s OR d.trich_yeu LIKE %s OR d.don_vi_ban_hanh LIKE %s OR d.file_name LIKE %s)"]
    args: list = [like, like, like, like, like]
    if summary_col:
      where_parts.append(f"d.{summary_col} LIKE %s")
      args.append(like)
    where_sql = " OR ".join(where_parts)

    uid = _user_id(x_user_id)
    wids: list[int] = []
    if work_ids:
      for part in str(work_ids).split(","):
        try:
          n = int(part.strip())
        except Exception:
          n = 0
        if n > 0:
          wids.append(n)

    if wids:
      in_w = ",".join(["%s"] * len(wids))
      # Changed: Use LEFT JOIN or move category filter to WHERE clause to allow searching documents even if they might not be in the specific category (if logic permits)
      # But requirements say "work_ids" is a filter. If work_ids is provided, we MUST filter by it.
      # The issue is likely that "ioffice_doc_id" exact match is buried in "LIKE".
      # Let's improve the LIKE to be smarter.
      
      sql_kw = f"""
        SELECT DISTINCT
          d.id AS row_id,
          d.ioffice_doc_id AS doc_id,
          d.so_ky_hieu,
          d.trich_yeu,
          d.don_vi_ban_hanh,
          d.ngay_den,
          d.han_xu_ly,
          d.link_goc,
          d.file_path AS duong_dan_file,
          d.file_name AS ten_file,
          {_sel_optional("summary_text", "ai_summary")}
        FROM ioffice_documents d
        JOIN document_category_items i ON i.ioffice_document_id=d.id
        JOIN document_categories c ON c.id=i.category_id
        WHERE c.user_id=%s AND i.category_id IN ({in_w}) AND ({where_sql})
        ORDER BY 
           (d.ioffice_doc_id LIKE %s) DESC,
           (d.so_ky_hieu LIKE %s) DESC,
           d.updated_at DESC, 
           d.id DESC
        LIMIT %s
      """
      # Prioritize exact-ish matches in sorting
      # We need to add args for the ORDER BY clause
      exact_like = f"{query}%"
      args2 = [uid] + wids + args + [exact_like, exact_like, int(limit)]
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(sql_kw, tuple(args2))
          rows_kw = list(cur.fetchall())
    else:
      # If no work_ids (categories) specified, we search ALL documents the user has access to?
      # OR just search all documents in the system?
      # Original code searched "ioffice_documents" directly without joining categories.
      # This implies "Global Search" if no category selected.
      
      sql_kw = f"""
        SELECT
          d.id AS row_id,
          d.ioffice_doc_id AS doc_id,
          d.so_ky_hieu,
          d.trich_yeu,
          d.don_vi_ban_hanh,
          d.ngay_den,
          d.han_xu_ly,
          d.link_goc,
          d.file_path AS duong_dan_file,
          d.file_name AS ten_file,
          {_sel_optional("summary_text", "ai_summary")}
        FROM ioffice_documents d
        WHERE ({where_sql})
        ORDER BY 
           (d.ioffice_doc_id LIKE %s) DESC,
           (d.so_ky_hieu LIKE %s) DESC,
           d.updated_at DESC, 
           d.id DESC
        LIMIT %s
      """
      exact_like = f"{query}%"
      args2 = args + [exact_like, exact_like, int(limit)]
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(sql_kw, tuple(args2))
          rows_kw = list(cur.fetchall())

    qlow = query.lower()
    existing_docs = {x["doc_id"]: x for x in raw_items}
    
    for r in rows_kw:
      did = str(r.get("doc_id") or "").strip()
      if not did:
        continue
      hay_skh = str(r.get("so_ky_hieu") or "").lower()
      hay_ty = str(r.get("trich_yeu") or "").lower()
      hay_sum = str(r.get("ai_summary") or "").lower()
      
      # Boost score for exact matches
      kw_score = 0.55
      if qlow == did.lower():
          kw_score = 0.99
      elif qlow == hay_skh:
          kw_score = 0.98
      elif qlow in did.lower():
          kw_score = 0.95
      elif qlow in hay_skh:
          kw_score = 0.90
      elif qlow in hay_ty:
        kw_score = 0.75
      elif qlow in hay_sum:
        kw_score = 0.65
      
      # Merge logic: if document already found by semantic search, keep the higher score
      if did in existing_docs:
          existing_docs[did]["score"] = max(existing_docs[did]["score"], kw_score)
      else:
          raw_items.append({"doc_id": did, "score": float(kw_score)})

  if not raw_items:
    return {"ok": True, "embed_model": embed_model, "results": [], "analysis": ""}

  ids = [x["doc_id"] for x in raw_items if x.get("doc_id")]
  placeholders = ",".join(["%s"] * len(ids))
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  sql = f"""
    SELECT
      id AS row_id,
      ioffice_doc_id AS doc_id,
      so_ky_hieu,
      trich_yeu,
      don_vi_ban_hanh,
      ngay_den,
      han_xu_ly,
      link_goc,
      file_path AS duong_dan_file,
      file_name AS ten_file,
      {select_summary_text}
    FROM ioffice_documents
    WHERE ioffice_doc_id IN ({placeholders})
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(ids))
      rows = list(cur.fetchall())
  by_id = {str(r.get("doc_id")): r for r in rows if isinstance(r, dict) and r.get("doc_id")}

  selected_doc_ids = set(ids)
  if work_ids:
    wids: list[int] = []
    for part in str(work_ids).split(","):
      try:
        n = int(part.strip())
      except Exception:
        n = 0
      if n > 0:
        wids.append(n)
    if wids:
      uid = _user_id(x_user_id)
      in_w = ",".join(["%s"] * len(wids))
      sqlw = f"""
        SELECT DISTINCT d.ioffice_doc_id AS doc_id
        FROM document_category_items i
        JOIN document_categories c ON c.id=i.category_id
        JOIN ioffice_documents d ON d.id=i.ioffice_document_id
        WHERE c.user_id=%s AND i.category_id IN ({in_w}) AND d.ioffice_doc_id IN ({placeholders})
      """
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(sqlw, tuple([uid] + wids + ids))
          selected_doc_ids = {str(r.get("doc_id")) for r in (cur.fetchall() or []) if r.get("doc_id")}

  try:
    thr_default = float(os.getenv("EDUAI_IOFFICE_SEARCH_SCORE_THRESHOLD") or "0.45") # Lowered default from 0.60
  except Exception:
    thr_default = 0.45
  try:
    thr_fallback = float(os.getenv("EDUAI_IOFFICE_SEARCH_FALLBACK_THRESHOLD") or "0.35") # Lowered fallback from 0.45
  except Exception:
    thr_fallback = 0.35
  thr = float(score_threshold) if score_threshold is not None else thr_default

  results: list[dict] = []
  for it in raw_items:
    did = str(it.get("doc_id") or "")
    if not did or did not in selected_doc_ids:
      continue
    r = by_id.get(did)
    if not r:
      continue
    fp = (r.get("duong_dan_file") or "").strip()
    view_url = ""
    if fp:
      try:
        safe = make_safe_relative_from_any(fp)
        view_url = f"/api/ioffice/view-zip?path={safe}"
        r["duong_dan_file"] = safe
      except Exception:
        view_url = ""
    results.append(
      {
        "doc_id": did,
        "score": float(it.get("score") or 0.0),
        "so_ky_hieu": r.get("so_ky_hieu") or "",
        "trich_yeu": r.get("trich_yeu") or r.get("ten_file") or "",
        "tom_tat": r.get("ai_summary") or "",
        "link_goc": r.get("link_goc") or "",
        "view_url": view_url,
      }
    )

  results.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
  strong = [x for x in results if float(x.get("score") or 0.0) >= thr]
  if not strong and results:
    fallback = [x for x in results if float(x.get("score") or 0.0) >= thr_fallback]
    strong = fallback[:1] if fallback else []
  analysis = ""
  if int(auto_summ or 0) == 1 and strong:
    try:
      from app.services.llm_client import generate_text

      sys_prompt = (os.getenv("EDUAI_IOFFICE_SEMANTIC_ANALYSIS_PROMPT") or "").strip() or (
        "Bạn là trợ lý AI cho Hiệu trưởng. Nhiệm vụ: phân tích kết quả tìm kiếm theo ngữ nghĩa và đề xuất hành động.\n"
        "Yêu cầu:\n"
        "- Tóm tắt nhanh ý định người dùng.\n"
        "- Chọn 3-5 văn bản phù hợp nhất (nêu lý do ngắn gọn).\n"
        "- Nếu thiếu thông tin, đề xuất câu hỏi làm rõ.\n"
        "- Trả lời bằng tiếng Việt, gạch đầu dòng rõ ràng."
      )
      lines = [f"QUERY: {query}", ""]
      for i, r in enumerate(strong[:10], start=1):
        lines.append(f"[{i}] score={float(r.get('score') or 0.0):.3f}")
        lines.append(f"Số ký hiệu: {r.get('so_ky_hieu') or ''}")
        lines.append(f"Trích yếu: {r.get('trich_yeu') or ''}")
        lines.append(f"Tóm tắt: {(r.get('tom_tat') or '')[:800]}")
        lines.append(f"Link: {r.get('link_goc') or r.get('view_url') or ''}")
        lines.append("")
      user_text = "\n".join(lines).strip()
      analysis, _ = generate_text(user_text, system_prompt=sys_prompt)
    except Exception:
      analysis = ""
  return {"ok": True, "embed_model": embed_model, "results": strong, "analysis": analysis}


class UiReindexBody(BaseModel):
  doc_id: str | None = None
  limit: int = 200


@router.post("/ui/reindex")
def ui_reindex(payload: UiReindexBody, x_user_id: str | None = Header(default=None)):
  from app.db import get_db_connection
  from app.services.ioffice_rag import index_ioffice_summary

  did = (payload.doc_id or "").strip()
  limit = int(payload.limit or 200)
  if limit < 1:
    limit = 1
  if limit > 2000:
    limit = 2000
  sql = "SELECT * FROM ioffice_documents"
  args: list = []
  if did:
    sql += " WHERE ioffice_doc_id=%s"
    args.append(did)
  sql += " ORDER BY updated_at DESC, id DESC LIMIT %s"
  args.append(limit)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(args))
      rows = list(cur.fetchall())
  ok = 0
  skipped = 0
  errors = 0
  for r in rows:
    try:
      res = index_ioffice_summary(r)
      if res.get("skipped"):
        skipped += 1
      else:
        ok += 1
    except Exception:
      errors += 1
  return {"ok": True, "indexed": ok, "skipped": skipped, "errors": errors}


class UiAggregateSummaryBody(BaseModel):
  doc_ids: list[str] = []
  prompt_mode: str | None = None
  custom_prompt: str | None = None
  model: str | None = None
  provider: str | None = None


@router.post("/ui/aggregate_summary")
def ui_aggregate_summary(payload: UiAggregateSummaryBody):
  from app.db import get_db_connection
  from app.services.ioffice_prompt_store import list_prompt_presets
  from app.services.llm_client import generate_text

  ids = [str(x or "").strip() for x in (payload.doc_ids or []) if str(x or "").strip()]
  if not ids:
    raise HTTPException(status_code=400, detail="missing_doc_ids")

  presets = {str(p.get("id")): str(p.get("prompt_text") or "") for p in (list_prompt_presets() or []) if isinstance(p, dict) and p.get("id")}
  prompt_mode = (payload.prompt_mode or "").strip() or "p3"
  sys_prompt = (payload.custom_prompt or "").strip() if prompt_mode == "custom" else (presets.get(prompt_mode) or "")
  if not sys_prompt:
    raise HTTPException(status_code=400, detail="missing_prompt")

  placeholders = ",".join(["%s"] * len(ids))
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  sql = f"""
    SELECT ioffice_doc_id AS doc_id, so_ky_hieu, trich_yeu, don_vi_ban_hanh, ngay_den, han_xu_ly, link_goc, file_path, {select_summary_text}
    FROM ioffice_documents
    WHERE ioffice_doc_id IN ({placeholders})
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(ids))
      rows = list(cur.fetchall() or [])
  by_id = {str(r.get("doc_id")): r for r in rows if r.get("doc_id")}

  blocks: list[str] = []
  for did in ids:
    d = by_id.get(did) or {}
    blocks.append(
      (
        f"---\nDOC_ID: {did}\n"
        f"Số ký hiệu: {d.get('so_ky_hieu') or ''}\n"
        f"Trích yếu: {d.get('trich_yeu') or ''}\n"
        f"Đơn vị: {d.get('don_vi_ban_hanh') or ''}\n"
        f"Ngày đến: {d.get('ngay_den') or ''}\n"
        f"Hạn xử lý: {d.get('han_xu_ly') or ''}\n"
        f"Link gốc: {d.get('link_goc') or ''}\n"
        f"Tóm tắt: {d.get('ai_summary') or ''}\n"
      ).strip()
    )
  context = "\n\n".join(blocks).strip()
  out, model_used = generate_text(context, system_prompt=sys_prompt, model=payload.model, provider=payload.provider)
  return {"ok": True, "text": out, "model": model_used}


class UiGenerateFromDocsBody(BaseModel):
  doc_ids: list[str] = []
  work_ids: list[int] = []
  preset_id: str | None = None
  custom_prompt: str | None = None
  user_request: str | None = None
  use_rag: bool = True
  model: str | None = None
  provider: str | None = None


@router.post("/ui/generate_from_docs")
async def ui_generate_from_docs(payload: UiGenerateFromDocsBody):
  from app.services.core_ai_service import CoreAIService
  from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

  ids = [str(x or "").strip() for x in (payload.doc_ids or []) if str(x or "").strip()]
  if not ids and not payload.work_ids:
    raise HTTPException(status_code=400, detail="missing_context_data")
  
  req = (payload.user_request or "").strip()
  if not req:
    raise HTTPException(status_code=400, detail="missing_user_request")

  if ids:
    try:
      ioffice_rag_ingestor.request_level2_for_doc_ids(ids, priority=True)
    except Exception:
      pass

  core_ai = CoreAIService(domain="MANAGEMENT")
  res = await core_ai.generate_content(
    doc_ids=ids,
    work_ids=payload.work_ids,
    user_request=req,
    preset_id=payload.preset_id,
    custom_prompt=payload.custom_prompt,
    use_rag=payload.use_rag,
    model=payload.model,
    provider=payload.provider
  )
  return res


@router.get("/ui/doc_summary")
def ui_doc_summary(doc_id: str):
  from app.db import get_db_connection

  did = (doc_id or "").strip()
  if not did:
    raise HTTPException(status_code=400, detail="missing_doc_id")
  select_summary_text = _sel_optional("summary_text", "ai_summary")
  select_summary_status = _sel_optional("summary_status", "ai_status")
  select_summary_error = _sel_optional("summary_error", "ai_error")
  select_summary_model = _sel_optional("summary_model", "ai_model")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        f"SELECT ioffice_doc_id AS doc_id, so_ky_hieu, trich_yeu, {select_summary_text}, {select_summary_status}, {select_summary_error}, {select_summary_model} FROM ioffice_documents WHERE ioffice_doc_id=%s",
        (did,),
      )
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  return {"ok": True, **row}


@router.get("/ui/ai_result")
def ui_ai_result(doc_id: str):
  return ui_doc_summary(doc_id)


class UiAiSummaryBody(BaseModel):
  doc_id: str
  model: str | None = None
  prompt_mode: str | None = None
  selected_members: list[str] | None = None


class UiLlmTestBody(BaseModel):
  provider: str | None = None
  model: str | None = None
  prompt_mode: str | None = None
  text: str | None = None
  api_key: str | None = None


@router.post("/ui/llm_test")
def ui_llm_test(payload: UiLlmTestBody):
  from app.services.llm_client import resolve_summary_provider, summarize_text

  provider = resolve_summary_provider(payload.provider)
  text = (payload.text or "").strip() or "Hãy tóm tắt nhanh văn bản sau bằng tiếng Việt, 3-5 gạch đầu dòng:\nXin chào. Đây là một văn bản thử nghiệm."
  if len(text) > 12000:
    text = text[:12000]
  try:
    summary, model_used = summarize_text(
      text,
      model=payload.model,
      prompt_mode=payload.prompt_mode,
      provider=payload.provider,
      api_key=payload.api_key,
    )
    return {"ok": True, "provider": provider, "model": model_used, "summary": summary}
  except Exception as e:
    return {"ok": False, "provider": provider, "error": str(e)}


@router.post("/ui/ai_summary")
def ui_ai_summary(payload: UiAiSummaryBody):
  global _ai_thread

  with _ai_lock:
    if _ai_thread and _ai_thread.is_alive():
      raise HTTPException(status_code=429, detail="already_running")

    did = (payload.doc_id or "").strip()
    if not did:
      raise HTTPException(status_code=400, detail="missing_doc_id")

    def _task():
      from app.db import get_db_connection
      from app.services.ioffice_summary import summarize_document
      from app.services.ioffice_summary import prepare_summary_input

      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
          doc = cur.fetchone()
      if not doc:
        return
      try:
        _, content_hash = prepare_summary_input(
          doc,
          selected_members=payload.selected_members,
          model=(payload.model or None),
          prompt_mode=(payload.prompt_mode or None),
        )
        if doc.get("content_hash") and doc.get("content_hash") == content_hash and (doc.get("summary_text") or "").strip():
          with get_db_connection() as conn:
            with conn.cursor() as cur:
              cur.execute(
                "UPDATE ioffice_documents SET summary_status='READY', summary_error=NULL, summary_updated_at=CURRENT_TIMESTAMP WHERE ioffice_doc_id=%s",
                (did,),
              )
          return
        with get_db_connection() as conn:
          with conn.cursor() as cur:
            cur.execute("UPDATE ioffice_documents SET summary_status='PROCESSING', summary_updated_at=CURRENT_TIMESTAMP WHERE ioffice_doc_id=%s", (did,))
        summary, model_used, content_hash = summarize_document(
          doc,
          selected_members=payload.selected_members,
          model=(payload.model or None),
          prompt_mode=(payload.prompt_mode or None),
        )
        with get_db_connection() as conn:
          with conn.cursor() as cur:
            cur.execute(
              "UPDATE ioffice_documents SET summary_status='READY', summary_text=%s, summary_model=%s, summary_error=NULL, summary_updated_at=CURRENT_TIMESTAMP, content_hash=%s WHERE ioffice_doc_id=%s",
              (summary, model_used, content_hash, did),
            )
        try:
          with get_db_connection() as conn:
            with conn.cursor() as cur:
              cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
              doc2 = cur.fetchone()
          if doc2:
            from app.services.ioffice_rag import index_ioffice_summary

            index_ioffice_summary(doc2)
        except Exception:
          pass
      except Exception as e:
        with get_db_connection() as conn:
          with conn.cursor() as cur:
            cur.execute(
              "UPDATE ioffice_documents SET summary_status='FAILED', summary_error=%s, summary_updated_at=CURRENT_TIMESTAMP WHERE ioffice_doc_id=%s",
              (str(e), did),
            )

    _ai_thread = threading.Thread(target=_task, daemon=True)
    _ai_thread.start()
    return {"ok": True}


@router.get("/ui/stats")
def ui_stats(vb_tab: str | None = None, role: str | None = None):
  from app.db import get_db_connection

  where = []
  args: list = []
  if vb_tab and vb_tab != "ALL":
    where.append("vb_status=%s")
    args.append(vb_tab)
  if role:
    if role == "OTHER":
      where.append("(vai_tro IS NULL OR (UPPER(vai_tro) NOT LIKE %s AND UPPER(vai_tro) NOT LIKE %s))")
      args.extend(["XLC%", "PH%"])
    else:
      where.append("UPPER(vai_tro) LIKE %s")
      args.append(f"{role}%")

  where_sql = f"WHERE {' AND '.join(where)}" if where else ""

  sql = f"""
    SELECT
      COUNT(*) AS total,
      SUM(fetch_status='FAILED') AS fail,
      SUM(UPPER(vai_tro) LIKE %s) AS xlc,
      SUM(UPPER(vai_tro) LIKE %s) AS ph,
      SUM(vai_tro IS NULL OR (UPPER(vai_tro) NOT LIKE %s AND UPPER(vai_tro) NOT LIKE %s)) AS other
    FROM ioffice_documents
    {where_sql}
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(["XLC%", "PH%", "XLC%", "PH%"] + args))
      row = cur.fetchone() or {}
  return {
    "total": int(row.get("total") or 0),
    "fail": int(row.get("fail") or 0),
    "xlc": int(row.get("xlc") or 0),
    "ph": int(row.get("ph") or 0),
    "other": int(row.get("other") or 0),
  }


@router.get("/ui/stats_role")
def ui_stats_role():
  from app.db import get_db_connection

  sql = "SELECT COALESCE(vai_tro,'') AS role, COUNT(*) AS cnt FROM ioffice_documents GROUP BY COALESCE(vai_tro,'') ORDER BY cnt DESC"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql)
      return list(cur.fetchall())


@router.get("/ui/system_status")
def ui_system_status():
  st = ioffice_sync_service.status()
  try:
    from app.services.ioffice_auto_summary import ioffice_auto_summary_worker

    ast = ioffice_auto_summary_worker.status()
    return {
      "ok": True,
      "workers": [
        {"name": "ioffice_sync", "active": bool(st.get("running"))},
        {"name": "ioffice_auto_summary", "active": bool(ast.get("running"))},
      ],
    }
  except Exception:
    return {"ok": True, "workers": [{"name": "ioffice_sync", "active": bool(st.get("running"))}]}


@router.get("/ui/ai_auto_status")
def ui_ai_auto_status():
  try:
    from app.services.ioffice_auto_summary import ioffice_auto_summary_worker

    return {"ok": True, **ioffice_auto_summary_worker.status()}
  except Exception as e:
    return {"ok": False, "error": str(e)}


@router.get("/ui/stream-logs")
def ui_stream_logs(request: Request):
  import time
  from starlette.responses import StreamingResponse

  try:
    since = int(request.headers.get("last-event-id") or "0")
  except Exception:
    since = 0

  def _gen():
    nonlocal since
    while True:
      st = ioffice_sync_service.status()
      logs = st.get("logs") or []
      new_items = [it for it in logs if int(it.get("id") or 0) > since]
      for it in new_items:
        since = int(it.get("id") or since)
        line = str(it.get("line") or "").replace("\r", "").replace("\n", " ")
        yield f"id: {since}\n"
        yield f"data: {line}\n\n"
      if not st.get("running") and not new_items:
        yield "data: ping\n\n"
      time.sleep(0.2)

  return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/view-file/{filepath:path}")
def view_file(filepath: str):
  safe = _normalize_and_validate(filepath)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="not_found")
  low = full.name.lower()
  media_type = mimetypes.guess_type(full.name)[0] or "application/octet-stream"
  if low.endswith(".pdf"):
    media_type = "application/pdf"
  elif low.endswith(".docx"):
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  elif low.endswith(".xlsx"):
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  elif low.endswith(".pptx"):
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
  elif low.endswith(".txt"):
    media_type = "text/plain; charset=utf-8"
  return FileResponse(
    path=str(full),
    filename=full.name,
    media_type=media_type,
    headers={"Content-Disposition": f'inline; filename=\"{full.name}\"', "X-Content-Type-Options": "nosniff"},
  )


@router.get("/download-file/{filepath:path}")
def download_file(filepath: str):
  safe = _normalize_and_validate(filepath)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="not_found")
  return FileResponse(path=str(full), filename=full.name, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename=\"{full.name}\"'})


@router.get("/download-audio/{filepath:path}")
def download_audio(filepath: str):
  safe = _normalize_and_validate(filepath)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="not_found")
  low = full.name.lower()
  media_type = "audio/mpeg" if low.endswith(".mp3") else "audio/wav" if low.endswith(".wav") else "application/octet-stream"
  return FileResponse(path=str(full), filename=full.name, media_type=media_type, headers={"Content-Disposition": f'inline; filename=\"{full.name}\"'})


@router.get("/view-zip")
def view_zip(path: str | None = None, show_list: int | None = None):
  raw = path or ""
  if not raw:
    return PlainTextResponse("Missing path", status_code=400)
  safe = _normalize_and_validate(raw)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="not_found")
  if not str(full).lower().endswith(".zip"):
    return RedirectResponse(url=f"/api/ioffice/view-file/{safe}")

  tmp_root = FILES_ROOT / "temp"
  ensure_dir(tmp_root)
  session_dir = tmp_root / str(uuid.uuid4())
  ensure_dir(session_dir)

  try:
    with zipfile.ZipFile(str(full), "r") as z:
      members = [m for m in z.namelist() if m and not m.endswith("/")]
      if not members:
        return PlainTextResponse("ZIP is empty", status_code=404)

      def _pick_best(ms: list[str]) -> str:
        prio = [".pdf", ".docx", ".doc", ".html", ".htm", ".txt", ".xlsx", ".pptx"]
        base = [(m, os.path.basename(m)) for m in ms]
        base = [(m, b) for (m, b) in base if b]
        if not base:
          return ms[0]
        for ext in prio:
          for m, b in base:
            if b.lower().endswith(ext):
              return m
        return base[0][0]

      extracted: list[str] = []
      if show_list:
        for m in members:
          fname = os.path.basename(m)
          if not fname:
            continue
          target = session_dir / fname
          with open(target, "wb") as f:
            f.write(z.read(m))
          extracted.append(fname)
      else:
        chosen = _pick_best(members)
        fname = os.path.basename(chosen) or os.path.basename(members[0]) or "file"
        target = session_dir / fname
        with open(target, "wb") as f:
          f.write(z.read(chosen))
        extracted.append(fname)
  except zipfile.BadZipFile:
    return PlainTextResponse("Invalid ZIP file", status_code=400)

  if not extracted:
    return PlainTextResponse("ZIP is empty", status_code=404)

  if len(extracted) == 1:
    single = extracted[0]
    rel = f"temp/{session_dir.name}/{single}"
    return RedirectResponse(url=f"/api/ioffice/view-file/{urllib.parse.quote(rel, safe='/')}")

  links_html = ""
  for fn in extracted:
    rel = f"temp/{session_dir.name}/{fn}"
    href = f"/api/ioffice/view-file/{urllib.parse.quote(rel, safe='/')}"
    links_html += f'<li><a target="_blank" href="{href}">{fn}</a></li>'

  page = f"""
  <!doctype html>
  <html>
  <head>
    <meta charset="utf-8">
    <title>Contents of {full.name}</title>
    <style>body{{font-family:sans-serif;padding:12px}}ul{{line-height:1.6}}</style>
  </head>
  <body>
    <h3>Danh sách file trong: {full.name}</h3>
    <p>Click tên file để mở trong tab mới.</p>
    <ul>
      {links_html}
    </ul>
  </body>
  </html>
  """
  return HTMLResponse(page)


@router.get("/documents")
def list_documents(
  limit: int = 50,
  offset: int = 0,
  keyword: str | None = None,
  vb_status: str | None = None,
  fetch_status: str | None = None,
  summary_status: str | None = None,
):
  from app.db import get_db_connection

  where = []
  args: list = []
  if keyword:
    where.append("(trich_yeu LIKE %s OR so_ky_hieu LIKE %s OR don_vi_ban_hanh LIKE %s)")
    k = f"%{keyword}%"
    args.extend([k, k, k])
  if vb_status:
    where.append("vb_status=%s")
    args.append(vb_status)
  if fetch_status:
    where.append("fetch_status=%s")
    args.append(fetch_status)
  if summary_status:
    where.append("summary_status=%s")
    args.append(summary_status)

  where_sql = f"WHERE {' AND '.join(where)}" if where else ""
  sql = f"""
    SELECT id, ioffice_doc_id, so_ky_hieu, trich_yeu, ngay_den, ngay_van_ban, don_vi_ban_hanh, vai_tro, han_xu_ly,
           fetch_status, summary_status, vb_status, synced_at, updated_at
    FROM ioffice_documents
    {where_sql}
    ORDER BY updated_at DESC, id DESC
    LIMIT %s OFFSET %s
  """
  args.extend([int(limit), int(offset)])
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(args))
      return list(cur.fetchall())


@router.get("/documents/{document_id}")
def get_document(document_id: int):
  from app.db import get_db_connection

  sql = "SELECT * FROM ioffice_documents WHERE id=%s"
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (int(document_id),))
      doc = cur.fetchone()
  if not doc:
    raise HTTPException(status_code=404, detail="not_found")
  return doc


@router.post("/documents/{document_id}/summarize")
def summarize(document_id: int, request: Request, x_user_id: str | None = Header(default=None)):
  from app.db import get_db_connection

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM ioffice_documents WHERE id=%s", (int(document_id),))
      doc = cur.fetchone()
  if not doc:
    raise HTTPException(status_code=404, detail="not_found")

  try:
    AuditRepo().log(action="ioffice.document.summarize.start", user_id=_user_id(x_user_id), entity_type="ioffice_document", entity_id=str(document_id), payload={}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    from app.services.ioffice_summary import prepare_summary_input

    _, content_hash = prepare_summary_input(doc, model=None, prompt_mode=None)
    if doc.get("content_hash") and doc.get("content_hash") == content_hash and (doc.get("summary_text") or "").strip():
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(
            "UPDATE ioffice_documents SET summary_status='READY', summary_error=NULL, summary_updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (int(document_id),),
          )
      AuditRepo().log(action="ioffice.document.summarize.ready", user_id=_user_id(x_user_id), entity_type="ioffice_document", entity_id=str(document_id), payload={"cached": True}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
      return {"status": "READY", "summary": doc.get("summary_text"), "model": doc.get("summary_model")}
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "UPDATE ioffice_documents SET summary_status='PROCESSING', summary_updated_at=CURRENT_TIMESTAMP WHERE id=%s",
          (int(document_id),),
        )
    summary, model, content_hash = summarize_document(doc)
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "UPDATE ioffice_documents SET summary_status='READY', summary_text=%s, summary_model=%s, summary_error=NULL, summary_updated_at=CURRENT_TIMESTAMP, content_hash=%s WHERE id=%s",
          (summary, model, content_hash, int(document_id)),
        )
    try:
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT * FROM ioffice_documents WHERE id=%s", (int(document_id),))
          doc2 = cur.fetchone()
      if doc2:
        from app.services.ioffice_rag import index_ioffice_summary

        index_ioffice_summary(doc2)
    except Exception:
      pass
    AuditRepo().log(action="ioffice.document.summarize.ready", user_id=_user_id(x_user_id), entity_type="ioffice_document", entity_id=str(document_id), payload={"cached": False, "model": model}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    return {"status": "READY", "summary": summary, "model": model}
  except Exception as e:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          "UPDATE ioffice_documents SET summary_status='FAILED', summary_error=%s, summary_updated_at=CURRENT_TIMESTAMP WHERE id=%s",
          (str(e), int(document_id)),
        )
    AuditRepo().log(action="ioffice.document.summarize.failed", user_id=_user_id(x_user_id), entity_type="ioffice_document", entity_id=str(document_id), payload={"error": str(e)}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/zip-members")
def zip_members(document_id: int):
  from app.db import get_db_connection

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT id, so_ky_hieu, trich_yeu, han_xu_ly, file_path, file_name FROM ioffice_documents WHERE id=%s", (int(document_id),))
      row = cur.fetchone()
  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  path = (row.get("file_path") or "").strip()
  if not path or not str(path).lower().endswith(".zip"):
    raise HTTPException(status_code=400, detail="not_zip")
  safe = _normalize_and_validate(path)
  full = (FILES_ROOT / safe).resolve()
  root = FILES_ROOT.resolve()
  if not str(full).startswith(str(root)):
    raise HTTPException(status_code=403, detail="forbidden")
  if not full.exists():
    raise HTTPException(status_code=404, detail="file_not_found")
  try:
    with zipfile.ZipFile(str(full), "r") as z:
      members = [m for m in z.namelist() if m and not m.endswith("/")]
    return {
      "ok": True,
      "members": members,
      "so_ky_hieu": row.get("so_ky_hieu") or "",
      "trich_yeu": row.get("trich_yeu") or "",
      "han_xu_ly": row.get("han_xu_ly") or "",
      "view_zip_url": f"/api/ioffice/view-zip?path={urllib.parse.quote(path)}",
      "download_zip_url": f"/api/ioffice/download-file/{safe}",
    }
  except zipfile.BadZipFile:
    raise HTTPException(status_code=400, detail="bad_zip")


class CategoryCreate(BaseModel):
  school_id: int | None = None
  name: str
  description: str | None = None
  parent_id: int | None = None
  sort_order: int = 0


class CategoryUpdate(BaseModel):
  name: str
  description: str | None = None
  parent_id: int | None = None
  sort_order: int = 0


@router.get("/categories")
def list_categories(x_user_id: str | None = Header(default=None)):
  repo = DocumentCategoriesRepo()
  return repo.list_categories(user_id=_user_id(x_user_id))


@router.post("/categories")
def create_category(payload: CategoryCreate, request: Request, x_user_id: str | None = Header(default=None)):
  if not payload.name.strip():
    raise HTTPException(status_code=400, detail="missing_name")
  repo = DocumentCategoriesRepo()
  uid = _user_id(x_user_id)
  cid = repo.create_category(
    user_id=uid,
    school_id=payload.school_id,
    name=payload.name.strip(),
    description=(payload.description or "").strip() or None,
    parent_id=payload.parent_id,
    sort_order=int(payload.sort_order or 0),
  )
  AuditRepo().log(action="ioffice.category.create", user_id=uid, entity_type="document_category", entity_id=str(cid), payload={"name": payload.name.strip()}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"id": cid}


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryUpdate, request: Request, x_user_id: str | None = Header(default=None)):
  repo = DocumentCategoriesRepo()
  uid = _user_id(x_user_id)
  repo.update_category(
    user_id=uid,
    category_id=category_id,
    name=payload.name.strip(),
    description=(payload.description or "").strip() or None,
    parent_id=payload.parent_id,
    sort_order=int(payload.sort_order or 0),
  )
  AuditRepo().log(action="ioffice.category.update", user_id=uid, entity_type="document_category", entity_id=str(category_id), payload={"name": payload.name.strip(), "sort_order": int(payload.sort_order or 0)}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"ok": True}


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, request: Request, x_user_id: str | None = Header(default=None)):
  repo = DocumentCategoriesRepo()
  uid = _user_id(x_user_id)
  repo.delete_category(user_id=uid, category_id=category_id)
  AuditRepo().log(action="ioffice.category.delete", user_id=uid, entity_type="document_category", entity_id=str(category_id), payload={}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"ok": True}


@router.get("/documents/{document_id}/categories")
def list_doc_categories(document_id: int, x_user_id: str | None = Header(default=None)):
  repo = DocumentCategoriesRepo()
  return repo.list_document_categories(user_id=_user_id(x_user_id), ioffice_document_id=document_id)


@router.post("/documents/{document_id}/categories/{category_id}")
def add_doc_category(document_id: int, category_id: int, request: Request, x_user_id: str | None = Header(default=None)):
  repo = DocumentCategoriesRepo()
  repo.add_document_to_category(category_id=category_id, ioffice_document_id=document_id)
  rag = {"level1": {"ok": True, "skipped": True, "reason": "not_run"}, "level2": {"ok": True, "skipped": True, "reason": "not_run"}}
  try:
    from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

    rag["level1"] = ioffice_rag_ingestor.queue_level1_for_doc_id(int(document_id))
    rag["level2"] = ioffice_rag_ingestor.queue_level2_for_doc_id(int(document_id), priority=False)
  except Exception:
    rag = {"ok": False, "error": "queue_failed"}
  AuditRepo().log(action="ioffice.category.assign", user_id=_user_id(x_user_id), entity_type="ioffice_document", entity_id=str(document_id), payload={"category_id": category_id}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"ok": True, "rag": rag}


@router.delete("/documents/{document_id}/categories/{category_id}")
def remove_doc_category(document_id: int, category_id: int, request: Request, x_user_id: str | None = Header(default=None)):
  repo = DocumentCategoriesRepo()
  repo.remove_document_from_category(category_id=category_id, ioffice_document_id=document_id)
  try:
    prune = (os.getenv("EDUAI_IOFFICE_RAG_LEVEL2_PRUNE_ON_UNASSIGN") or "1").strip().lower()
    delete_qdrant = (os.getenv("EDUAI_IOFFICE_RAG_LEVEL2_PRUNE_DELETE_QDRANT") or "0").strip().lower()
    if prune not in ("0", "false", "no", "off"):
      from app.services.ioffice_rag_ingest import ioffice_rag_ingestor

      ioffice_rag_ingestor.prune_level2_for_document_row(int(document_id), delete_qdrant=delete_qdrant in ("1", "true", "yes", "on"))
  except Exception:
    pass
  AuditRepo().log(action="ioffice.category.unassign", user_id=_user_id(x_user_id), entity_type="ioffice_document", entity_id=str(document_id), payload={"category_id": category_id}, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
  return {"ok": True}
