import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from fetcher.control import read_config, make_logger, request_stop, reset_stop, BASE_IOFFICE
from fetcher.selectors import TABLE_SELECTOR, ROW_SELECTOR
from fetcher.process_row import process_row
from fetcher.pagination import go_next_page
from fetcher.utils_playwright import pick_visible_element, find_table_context, robust_goto, trigger_row_detail
from fetcher.row_extract import extract_row_fields
from database import get_document

STATE_PATH = Path(__file__).parent.parent / "fetch_state.json"


def _load_state():
  try:
    if STATE_PATH.exists():
      return json.loads(STATE_PATH.read_text(encoding="utf-8"))
  except Exception:
    pass
  return {"last_cat": None, "last_page": 1, "last_run": None}


def _save_state(cat, page):
  try:
    data = {"last_cat": cat, "last_page": int(page or 1), "last_run": int(time.time())}
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
  except Exception:
    pass


def _parse_date(s):
  try:
    t = (s or "").strip()
    if not t:
      return None
    import datetime as _dt
    for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
      try:
        return _dt.datetime.strptime(t, fmt)
      except Exception:
        continue
  except Exception:
    return None
  return None


def _order_cats_by_state(cats, st):
  try:
    lc = st.get("last_cat")
    if not lc:
      return cats
    seq = list(cats or [])
    if lc in seq:
      i = seq.index(lc)
      return seq[i:] + seq[:i]
    return cats
  except Exception:
    return cats


def _open_category(page, cat_key, logger):
  try:
    key = str(cat_key or "").upper()
    logger(f"Switch category: {key}")
    mapping = {
      "CHO_XU_LY": ["Chờ xử lý", "CHỜ XỬ LÝ", "Văn bản đến chờ xử lý"],
      "XEM_DE_BIET": ["Xem để biết", "XEM ĐỂ BIẾT"],
      "DA_XU_LY": ["Đã xử lý", "ĐÃ XỬ LÝ", "Văn bản đến đã xử lý"],
    }
    by_param = {
      "XEM_DE_BIET": ["VANBAN_THONGBAO"],
      "DA_XU_LY": ["VAN_BAN_DA_XU_LY"],
    }

    def _ensure_inbox_open():
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
            logger("Opened parent menu: Văn bản đến")
          except Exception:
            pass
      except Exception:
        pass

    _ensure_inbox_open()
    texts = mapping.get(key, [])
    for t in texts:
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
              logger(f"Execute JS nav: {t}")
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
    params = by_param.get(key, [])
    for p in params:
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
                logger(f"Execute JS nav by param: {p}")
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
  except Exception as e:
    try:
      logger(f"Switch category err: {e}")
    except Exception:
      pass
  return False


def run_fetch_all_with_queue(log_q, headless=True, cats=None, mode="update", max_pages=None):
  reset_stop()
  logger = make_logger(log_q)
  cfg = read_config()
  if not cfg.get("username") or not cfg.get("password"):
    logger("⚠ Missing username/password in config.json")
    return

  logger(f"=== START FETCH === mode={mode} cats={','.join(cats or [])}")
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=headless, args=["--disable-features=IsolateOrigins,site-per-process"])
    context = browser.new_context(
      accept_downloads=True,
      ignore_https_errors=True,
      user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    page.set_default_timeout(20000)
    try:
      if robust_goto(page, f"{BASE_IOFFICE}/", logger, retries=3):
        pass
      else:
        raise Exception("Unable to open login page")
      logger("Opened login page")
      try:
        page.fill("#userName", cfg["username"])
        page.fill("#passWord", cfg["password"])
      except Exception as e:
        logger(f"Fill login err: {e}")
      try:
        if page.query_selector("#loginBtn"):
          page.click("#loginBtn")
        else:
          page.keyboard.press("Enter")
      except Exception:
        pass
      time.sleep(2)
      cats = cats or ["CHO_XU_LY", "XEM_DE_BIET", "DA_XU_LY"]
      st = _load_state()
      if str(mode).lower() == "continue":
        cats = _order_cats_by_state(cats, st)
      pages = 0
      total_docs = 0
      total_fail = 0
      if max_pages is None:
        max_pages = 200 if str(mode).lower() in ("full", "continue") else 3
      for cat in cats:
        if getattr(__import__("fetcher.control", fromlist=["_stop_flag"]), "_stop_flag").is_set():
          break
        try:
          opened = _open_category(page, cat, logger)
          if not opened:
            logger(f"Category '{cat}' fallback: use current inbox")
          ctx = find_table_context(page, logger)
          try:
            ctx.wait_for_selector(TABLE_SELECTOR, timeout=15000)
          except Exception:
            logger("Warning: table not found for category")
          current = 1
          if str(mode).lower() == "continue" and st.get("last_cat") == cat:
            current = int(st.get("last_page") or 1)
            logger(f"Continue from page {current} for {cat}")
          while True:
            if getattr(__import__("fetcher.control", fromlist=["_stop_flag"]), "_stop_flag").is_set():
              logger("STOP requested, exiting loop")
              break
            logger(f"[{cat}] --- Scanning page {current} ---")
            try:
              logger(f"[UI_PAGE] {current}")
            except Exception:
              pass
            time.sleep(0.6)
            ctx = find_table_context(page, logger)
            rows = ctx.query_selector_all(ROW_SELECTOR)
            if not rows:
              logger("No rows found, trying to refresh context")
              try:
                page.evaluate("window.location.reload()")
                time.sleep(1.2)
                ctx = find_table_context(page, logger)
                rows = ctx.query_selector_all(ROW_SELECTOR)
              except Exception:
                pass
              if not rows:
                logger("Still empty, break category")
                break
            page_total = len(rows)
            page_fail = 0
            page_processed = 0
            for r in rows:
              if getattr(__import__("fetcher.control", fromlist=["_stop_flag"]), "_stop_flag").is_set():
                break
              try:
                info0 = extract_row_fields(r)
                try:
                  skh0 = (info0.get("so_ky_hieu") or info0.get("ten_file") or info0.get("doc_id") or "").strip()
                  if skh0:
                    logger(f"[UI_STATUS] page={current} skh={skh0}")
                except Exception:
                  pass
                if str(mode).lower() == "update":
                  try:
                    docid0 = str(info0.get("doc_id") or "")
                    if docid0:
                      existing = get_document(docid0)
                      if existing:
                        fp = (existing.get("file_path") or "").strip()
                        st = (existing.get("fetch_status") or "").strip().upper()
                        if fp and st == "OK":
                          continue
                  except Exception:
                    pass
                elif str(mode).lower() == "continue":
                  try:
                    docid0 = str(info0.get("doc_id") or "")
                    if docid0 and get_document(docid0):
                      continue
                  except Exception:
                    pass
                status = process_row(
                  page,
                  r,
                  logger,
                  context=context,
                  vb_status_hint=cat,
                  update_only_existing=False,
                  skip_if_exists=(str(mode).lower() == "continue"),
                )
                if status == "fail":
                  page_fail += 1
                if status and status != "skip":
                  page_processed += 1
              except Exception as e:
                logger(f"process_row exception: {e}")
                page_fail += 1
            total_docs += page_total
            total_fail += page_fail
            pages += 1
            _save_state(cat, current)
            logger(f"[{cat}] Page {current} summary: total={page_total}, fail={page_fail}")
            if getattr(__import__("fetcher.control", fromlist=["_stop_flag"]), "_stop_flag").is_set():
              break
            if current >= max_pages:
              logger("Reached max_pages for mode, stop")
              break
            if go_next_page(ctx, current, logger) or go_next_page(page, current, logger):
              current += 1
              time.sleep(1.0)
              continue
            else:
              logger("No more pages in category, done")
              break
        except Exception as e:
          logger(f"Category loop error: {e}")
    except Exception as e:
      logger(f"FATAL: {e}")
    finally:
      try:
        browser.close()
      except Exception:
        pass
      ok_docs = max(0, total_docs - total_fail)
      logger(f"=== FETCH COMPLETE === pages={pages} docs={total_docs} ok={ok_docs} fail={total_fail}")
