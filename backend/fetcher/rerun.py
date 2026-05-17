import time
from playwright.sync_api import sync_playwright
from fetcher.control import read_config, make_logger, reset_stop, BASE_IOFFICE
from fetcher.selectors import ROW_SELECTOR
from fetcher.process_row import process_row
from fetcher.pagination import go_next_page
from fetcher.utils_playwright import robust_goto


def run_rerun_list(doc_ids, log_q, headless=True):
  reset_stop()
  logger = make_logger(log_q)
  cfg = read_config()
  if not cfg.get("username") or not cfg.get("password"):
    logger("⚠ Missing username/password")
    return
  logger(f"=== RERUN START for {len(doc_ids)} docs ===")
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
      if not robust_goto(page, f"{BASE_IOFFICE}/", logger, retries=3):
        raise Exception("Unable to open iOffice")
      try:
        page.fill("#userName", cfg["username"])
        page.fill("#passWord", cfg["password"])
      except Exception:
        pass
      try:
        if page.query_selector("#loginBtn"):
          page.click("#loginBtn")
        else:
          page.keyboard.press("Enter")
      except Exception:
        pass
      time.sleep(2)
      try:
        page.evaluate(
          """(function(){
                    if (typeof link === 'function') {
                        try {
                            link("m2766",
                                 "DBny4Y9y4B1V4ctk3yPbCY9aDz5Y3yPbCY9fCcPbUo..",
                                 "", " ", 0,0,
                                 "&4c9lTFLwDctm=2&6yXl=VAN_BAN_DEN_CA_NHAN&Cc9m=20&TFbm5B5xCcLw6B9k=0");
                        } catch(e){}
                    }
                })()"""
        )
      except Exception:
        pass
      time.sleep(1.2)
      for doc_id in doc_ids:
        if getattr(__import__("fetcher.control", fromlist=["_stop_flag"]), "_stop_flag").is_set():
          break
        try:
          logger(f"Rerun doc {doc_id}")
          rows = page.query_selector_all(ROW_SELECTOR)
          target = None
          for r in rows:
            try:
              rid = (r.get_attribute("flyid") or r.get_attribute("id") or "").replace("vb_", "")
              if rid == str(doc_id):
                target = r
                break
            except Exception:
              continue
          if not target:
            logger(f"Doc {doc_id} not in current page; scanning subsequent pages")
            found = False
            cur = 1
            while True:
              rows = page.query_selector_all(ROW_SELECTOR)
              for r in rows:
                try:
                  rid = (r.get_attribute("flyid") or r.get_attribute("id") or "").replace("vb_", "")
                  if rid == str(doc_id):
                    target = r
                    found = True
                    break
                except Exception:
                  continue
              if found:
                break
              if not go_next_page(page, cur, logger):
                break
              cur += 1
              time.sleep(0.8)
          if target:
            process_row(page, target, logger, context=context)
          else:
            logger(f"Doc {doc_id} not found in paged scan")
        except Exception as e:
          logger(f"Rerun doc {doc_id} err: {e}")
    except Exception as e:
      logger(f"RERUN FATAL: {e}")
    finally:
      try:
        browser.close()
      except Exception:
        pass
      logger("=== RERUN COMPLETE ===")
