import json
import os
import threading
import time
from pathlib import Path

from app.integrations.ioffice.selectors import ROW_SELECTOR, TABLE_SELECTOR


def _state_path() -> Path:
  root = Path(os.getenv("EDUAI_STATE_DIR", Path(__file__).resolve().parents[3] / ".state"))
  root.mkdir(parents=True, exist_ok=True)
  return root / "ioffice_fetch_state.json"


def _load_state() -> dict:
  p = _state_path()
  try:
    if p.exists():
      return json.loads(p.read_text(encoding="utf-8"))
  except Exception:
    return {"last_cat": None, "last_page": 1, "last_run": None}
  return {"last_cat": None, "last_page": 1, "last_run": None}


def _save_state(cat: str | None, page: int | None) -> None:
  p = _state_path()
  try:
    p.write_text(json.dumps({"last_cat": cat, "last_page": int(page or 1), "last_run": int(time.time())}), encoding="utf-8")
  except Exception:
    return


def _base_url() -> str:
  return (os.getenv("EDUAI_IOFFICE_BASE_URL") or "").strip().rstrip("/")


def _open_category(page, cat_key: str, log):
  key = str(cat_key or "").upper()
  mapping = {
    "CHO_XU_LY": ["Chờ xử lý", "CHỜ XỬ LÝ", "Văn bản đến chờ xử lý"],
    "XEM_DE_BIET": ["Xem để biết", "XEM ĐỂ BIẾT"],
    "DA_XU_LY": ["Đã xử lý", "ĐÃ XỬ LÝ", "Văn bản đến đã xử lý"],
  }
  by_param = {
    "XEM_DE_BIET": ["VANBAN_THONGBAO"],
    "DA_XU_LY": ["VAN_BAN_DA_XU_LY"],
  }

  def ensure_inbox_open():
    try:
      el = page.query_selector("span#m2765")
      a = None
      if el:
        try:
          a = el.evaluate_handle("(s)=>s.closest('a')")
        except Exception:
          a = None
      if not a:
        for anchor in page.query_selector_all("a"):
          try:
            txt = (anchor.inner_text() or "").strip()
            if "Văn bản đến".lower() in txt.lower():
              a = anchor
              break
          except Exception:
            continue
      if a:
        try:
          a.click()
          time.sleep(0.8)
        except Exception:
          return
    except Exception:
      return

  ensure_inbox_open()
  for t in mapping.get(key, []):
    try:
      a = None
      for el in page.query_selector_all("a, button"):
        try:
          tx = (el.inner_text() or "").strip()
          if t.lower() in tx.lower():
            a = el
            break
        except Exception:
          continue
      if a:
        href = (a.get_attribute("href") or "").strip()
        onclick = (a.get_attribute("onclick") or "").strip()
        js = None
        for cand in (href, onclick):
          if cand and "link(" in cand:
            js = cand.replace("javascript:", "").strip()
            if js.endswith(";"):
              js = js[:-1]
            break
        if js:
          try:
            page.evaluate(f"(function(){{ try{{ {js} }}catch(e){{}} }})()")
            time.sleep(1.0)
            return True
          except Exception:
            pass
        try:
          a.click()
          time.sleep(1.0)
          return True
        except Exception:
          pass
    except Exception:
      continue
  for p in by_param.get(key, []):
    try:
      for el in page.query_selector_all("a, button"):
        try:
          href = (el.get_attribute("href") or "").strip()
          onclick = (el.get_attribute("onclick") or "").strip()
          cand = href or onclick
          if cand and p in cand:
            js = cand.replace("javascript:", "").strip()
            if js.endswith(";"):
              js = js[:-1]
            try:
              page.evaluate(f"(function(){{ try{{ {js} }}catch(e){{}} }})()")
              time.sleep(1.0)
              return True
            except Exception:
              try:
                el.click()
                time.sleep(1.0)
                return True
              except Exception:
                pass
        except Exception:
          continue
    except Exception:
      continue
  try:
    log(f"Không mở được category: {key}")
  except Exception:
    pass
  return False


def _extract_row_texts(row):
  try:
    cells = row.query_selector_all("td")
    return [((c.inner_text() or "").strip()) for c in cells]
  except Exception:
    return []


def _extract_doc_id(row) -> str | None:
  for attr in ("data-id", "data-docid", "data-doc-id"):
    try:
      v = (row.get_attribute(attr) or "").strip()
      if v:
        return v
    except Exception:
      continue
  try:
    a = row.query_selector("a")
    if a:
      href = (a.get_attribute("href") or "").strip()
      if "docId=" in href:
        return href.split("docId=")[-1].split("&")[0]
  except Exception:
    return None
  return None


def fetch_documents(
  *,
  username: str,
  password: str,
  headless: bool,
  cats: list[str],
  mode: str,
  log,
  stop_event: threading.Event,
  max_pages: int | None = None,
) -> list[dict]:
  from playwright.sync_api import sync_playwright

  base = _base_url()
  if not base:
    raise RuntimeError("Missing EDUAI_IOFFICE_BASE_URL")

  st = _load_state()
  if mode == "continue" and st.get("last_cat") in cats:
    i = cats.index(st.get("last_cat"))
    cats = cats[i:] + cats[:i]

  docs: list[dict] = []
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=headless, args=["--disable-features=IsolateOrigins,site-per-process"])
    context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
    page = context.new_page()
    page.set_default_timeout(20000)
    page.goto(f"{base}/")
    try:
      page.fill("#userName", username)
      page.fill("#passWord", password)
      if page.query_selector("#loginBtn"):
        page.click("#loginBtn")
      else:
        page.keyboard.press("Enter")
    except Exception as e:
      raise RuntimeError(f"Login failed: {e}") from e

    time.sleep(2)
    pages = 0
    for cat in cats:
      if stop_event.is_set():
        break
      _open_category(page, cat, log)
      time.sleep(1.2)
      page_num = 1
      while True:
        if stop_event.is_set():
          break
        pages += 1
        _save_state(cat, page_num)
        tbl = page.query_selector(TABLE_SELECTOR)
        if not tbl:
          break
        rows = page.query_selector_all(f"{TABLE_SELECTOR} {ROW_SELECTOR}")
        for r in rows:
          if stop_event.is_set():
            break
          doc_id = _extract_doc_id(r) or None
          cells = _extract_row_texts(r)
          docs.append(
            {
              "ioffice_doc_id": doc_id or (cells[0] if cells else None) or str(uuid_from_row(cells)),
              "cat": cat,
              "cells": cells,
            }
          )
        if max_pages and pages >= max_pages:
          break
        next_btn = page.query_selector("a[title*='Trang sau'], a[aria-label*='Next'], .pagination a[rel='next']")
        if not next_btn:
          break
        try:
          next_btn.click()
          time.sleep(1.0)
          page_num += 1
        except Exception:
          break
      if max_pages and pages >= max_pages:
        break
    context.close()
    browser.close()
  return docs


def uuid_from_row(cells: list[str]) -> str:
  import hashlib
  import uuid

  h = hashlib.sha1(("|".join(cells or [])).encode("utf-8", errors="ignore")).hexdigest()
  return str(uuid.UUID(h[:32]))
