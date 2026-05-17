import os
import time
from datetime import datetime
import traceback

from database import upsert_document, get_account, get_document
from embed_worker import start_worker, notify_doc_changed
from utils import slugify_filename, ensure_dir, log_to_queue, FILES_ROOT

from fetcher.popup import get_link_goc_from_row_popup, build_link_goc
from fetcher.row_extract import extract_row_fields
from fetcher.modal_extract import extract_latest_instruction, extract_account_task_summary, extract_deadline
from fetcher.download import download_zip_from_modal

from fetcher.control import _stop_flag


def process_row(page, row, logger, context=None, vb_status_hint=None, update_only_existing=False, skip_if_exists=False):
  from fetcher.control import _stop_flag as _sf
  if getattr(_sf, "is_set", lambda: False)():
    logger("[process_row] Stop requested")
    return

  info = extract_row_fields(row)
  doc_id = info.get("doc_id") or ""
  so_ky_hieu = info.get("so_ky_hieu") or ""
  trich_yeu = info.get("trich_yeu") or ""
  don_vi = info.get("don_vi_ban_hanh") or "UNKNOWN"
  vai_tro = (info.get("vai_tro") or "").strip()
  trang_thai = info.get("trang_thai_xu_ly") or ""

  logger(f"[{doc_id}] START process | skh={so_ky_hieu}")
  if skip_if_exists:
    try:
      if doc_id and get_document(str(doc_id)):
        logger(f"[{doc_id}] skip continue: already in DB")
        return "skip"
    except Exception:
      pass
  if update_only_existing:
    try:
      if not doc_id or not get_document(str(doc_id)):
        logger(f"[{doc_id}] skip update-only: not in DB")
        return "skip"
    except Exception:
      return "skip"

  link_goc = ""
  try:
    link_goc = get_link_goc_from_row_popup(page, row, context, logger, doc_id)
  except Exception as e:
    logger(f"[{doc_id}] popup link err: {e}")
  if not link_goc:
    link_goc = build_link_goc(doc_id)

  role_key = "OTHER"
  v = (vai_tro or "").upper()
  if "XLC" in v:
    role_key = "XLC"
  elif v.startswith("PH") or "PHỤ" in v:
    role_key = "PH"
  else:
    role_key = slugify_filename(v)[:30] if v else "OTHER"

  donvi_safe = slugify_filename(don_vi or "DONVI")
  save_dir = FILES_ROOT / role_key / donvi_safe
  ensure_dir(save_dir)

  opened = False
  try:
    try:
      row.click()
      time.sleep(0.6)
      opened = True
      logger(f"[{doc_id}] clicked row -> opened={opened}")
    except Exception as e:
      logger(f"[{doc_id}] click row err: {e}")
      opened = False
  except Exception:
    opened = False

  chi_dao = ""
  try:
    chi_dao = extract_latest_instruction(page, logger, doc_id)
  except Exception as e:
    logger(f"[{doc_id}] extract instruction err: {e}")

  nv_sum = {"summary": "", "more": 0}
  try:
    nv_sum = extract_account_task_summary(page, logger, doc_id)
  except Exception as e:
    logger(f"[{doc_id}] extract task summary err: {e}")

  han_xu_ly = ""
  try:
    han_xu_ly = extract_deadline(page, logger, doc_id)
  except Exception as e:
    logger(f"[{doc_id}] extract deadline err: {e}")

  saved_paths = []
  try:
    saved_paths = download_zip_from_modal(page, doc_id, so_ky_hieu, trich_yeu, save_dir, logger)
  except Exception as e:
    logger(f"[{doc_id}] download exception: {e}\n{traceback.format_exc()}")

  file_rel = saved_paths[0] if saved_paths else ""
  file_name = os.path.basename(file_rel) if file_rel else ""

  v_vb = None
  if vb_status_hint:
    try:
      v_vb = str(vb_status_hint).upper()
    except Exception:
      v_vb = None
  if not v_vb:
    v_vb = "XEM_DE_BIET"
    try:
      v_upper = (vai_tro or "").upper()
      st_low = (trang_thai or "").lower()
      if "XLC" in v_upper:
        if ("đã" in st_low) or ("hoàn" in st_low):
          v_vb = "DA_XU_LY"
        else:
          v_vb = "CHO_XU_LY"
      elif v_upper.startswith("PH") or ("PHỤ" in v_upper):
        v_vb = "XEM_DE_BIET"
      else:
        v_vb = "XEM_DE_BIET"
    except Exception:
      v_vb = "XEM_DE_BIET"

  try:
    acc = None
    try:
      acc = get_account()
    except Exception:
      acc = None
    s = (nv_sum.get("summary") or "").strip()
    import re as _re
    sender_user = None
    sender_line_low = ""
    assigned_user = None
    try:
      muser = _re.search(r"Người gửi:\s*.*?\(([^)]+)\)", s, flags=_re.IGNORECASE)
      if muser:
        sender_user = (muser.group(1) or "").strip().lower()
      else:
        mline = _re.search(r"Người gửi:\s*([^|\n]+)", s, flags=_re.IGNORECASE)
        if mline:
          sender_line_low = (mline.group(1) or "").strip().lower()
      massigned = _re.search(r"Chuyển tới:\s*.*?\(([^)]+)\)", s, flags=_re.IGNORECASE)
      if massigned:
        assigned_user = (massigned.group(1) or "").strip().lower()
    except Exception:
      sender_user = None
      assigned_user = None
    action_ok = False
    try:
      if _re.search(r"Thao tác:\s*Đã tạo phúc đáp", s, flags=_re.IGNORECASE):
        action_ok = True
    except Exception:
      action_ok = False
    try:
      user = ((acc.get("username") or "").strip().lower()) if acc else ""
      if user and action_ok:
        if (sender_user and sender_user == user) or (sender_line_low and (user in sender_line_low)):
          vai_tro = "XLC"
      if user and assigned_user and assigned_user == user:
        vai_tro = "XLC"
    except Exception:
      pass
  except Exception:
    pass

  if file_rel:
    fetch_status = "ok"
    error_msg = ""
  else:
    has_file_btn = False
    try:
      if row.query_selector("a.btnDownloadAllFileVBDen, a.btn_xem_file_, a.btn_xem"):
        has_file_btn = True
      else:
        from fetcher.utils_playwright import pick_visible_element
        from fetcher.selectors import ZIP_SELECTORS, VIEW_FILE_SELECTORS
        if pick_visible_element(page, ZIP_SELECTORS) or pick_visible_element(page, VIEW_FILE_SELECTORS):
          has_file_btn = True
        else:
          frames = page.query_selector_all("div.modal-content iframe")
          for ifr in frames:
            try:
              fr = ifr.content_frame()
              if not fr:
                continue
              if pick_visible_element(fr, ZIP_SELECTORS) or pick_visible_element(fr, VIEW_FILE_SELECTORS):
                has_file_btn = True
                break
            except Exception:
              continue
    except Exception:
      has_file_btn = True

    fetch_status = "fail"
    error_msg = "No attachment or download failed"

  rec = {
    "doc_id": doc_id,
    "stt": info.get("stt"),
    "so_ky_hieu": so_ky_hieu,
    "trich_yeu": trich_yeu,
    "hinh_thuc": info.get("hinh_thuc"),
    "ngay_van_ban": info.get("ngay_van_ban"),
    "ngay_den": info.get("ngay_den"),
    "don_vi_ban_hanh": don_vi,
    "vai_tro": vai_tro,
    "duong_dan_file": file_rel,
    "ten_file": file_name,
    "tom_tat": None,
    "trang_thai_xu_ly": trang_thai or ("Đã tải" if file_rel else "Chưa tải"),
    "chi_dao_xl": chi_dao,
    "nhiem_vu": nv_sum.get("summary") or "",
    "nhiem_vu_more": int(bool(nv_sum.get("more", 0))),
    "han_xu_ly": han_xu_ly,
    "link_goc": link_goc,
    "fetch_status": fetch_status,
    "error_msg": error_msg,
    "vb_status": v_vb,
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  }
  try:
    if update_only_existing:
      try:
        if not get_document(str(doc_id)):
          logger(f"[{doc_id}] skip upsert: not in DB (update-only)")
          return "skip"
      except Exception:
        return "skip"
    upsert_document(rec)
    try:
      start_worker()
      notify_doc_changed(str(doc_id))
    except Exception:
      pass
  except Exception as e:
    logger(f"[{doc_id}] DB upsert err: {e}")

  t = datetime.now().strftime("%H:%M:%S")
  short_trich = (trich_yeu or "")[:80].replace("\n", " ")
  logger(f"[{doc_id}] [{t}] {so_ky_hieu} | {short_trich} | status={fetch_status} | err={error_msg}")
  return fetch_status
