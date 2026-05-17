def pick_visible_element(page_or_frame, css_list):
  for sel in css_list:
    try:
      els = page_or_frame.query_selector_all(sel)
      for e in els:
        try:
          box = e.bounding_box()
          if box and box.get("width", 0) > 1 and box.get("height", 0) > 1:
            return e
        except Exception:
          continue
    except Exception:
      continue
  return None


def safe_inner_text(el):
  try:
    return el.inner_text().strip()
  except Exception:
    return ""


def find_table_context(page, logger=None):
  try:
    from fetcher.selectors import TABLE_SELECTOR, ROW_SELECTOR
    try:
      if page.query_selector(TABLE_SELECTOR) or page.query_selector(ROW_SELECTOR):
        return page
    except Exception:
      pass
    try:
      for fr in getattr(page, "frames", []):
        try:
          if fr.query_selector(TABLE_SELECTOR) or fr.query_selector(ROW_SELECTOR):
            return fr
        except Exception:
          continue
    except Exception:
      pass
  except Exception as e:
    if logger:
      try:
        logger(f"find_table_context err: {e}")
      except Exception:
        pass
  return page


def robust_goto(page, url, logger=None, retries=3):
  import time
  last_err = None
  for i in range(1, int(retries) + 1):
    try:
      page.goto(url, wait_until="domcontentloaded", timeout=30000)
      try:
        page.wait_for_load_state("networkidle", timeout=20000)
      except Exception:
        pass
      return True
    except Exception as e:
      last_err = e
      if logger:
        try:
          logger(f"goto attempt {i} failed: {e}")
        except Exception:
          pass
      time.sleep(min(2.0 * i, 6.0))
      try:
        page.close()
      except Exception:
        pass
      try:
        page = page.context.new_page()
        page.set_default_timeout(20000)
      except Exception:
        pass
  if logger:
    try:
      logger(f"goto failed after {retries} attempts: {last_err}")
    except Exception:
      pass
  return False


def trigger_row_detail(ctx, row, logger=None):
  try:
    td = None
    try:
      cand = row.query_selector_all('td[onclick*="showDocDetail"]')
      if cand:
        td = cand[0]
    except Exception:
      td = None
    onclick = None
    if td:
      try:
        onclick = (td.get_attribute("onclick") or "").strip()
      except Exception:
        onclick = None
    if not onclick:
      try:
        cand2 = row.query_selector_all('[onclick*="showDocDetail"]')
        if cand2:
          onclick = (cand2[0].get_attribute("onclick") or "").strip()
      except Exception:
        onclick = None
    if onclick:
      js = onclick.replace("javascript:", "").strip()
      if js.endswith(";"):
        js = js[:-1]
      try:
        ctx.evaluate(f"(function(){{try{{ {js} }}catch(e){{}} }})()")
        return True
      except Exception as e:
        if logger:
          try:
            logger(f"trigger_row_detail eval err: {e}")
          except Exception:
            pass
    try:
      row.click()
      return True
    except Exception as e:
      if logger:
        try:
          logger(f"trigger_row_detail click err: {e}")
        except Exception:
          pass
  except Exception:
    pass
  return False
