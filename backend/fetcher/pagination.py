import time

from fetcher.selectors import TABLE_SELECTOR, ROW_SELECTOR


def go_next_page(page_or_frame, current_page, logger):
  try:
    next_page_num = current_page + 1
    selectors = [
      "ul.pagination a",
      ".pagination a",
      "a[onclick*='gotoPage']",
      "a[onclick*='page.gotoPage']",
    ]
    for sel in selectors:
      try:
        anchors = page_or_frame.query_selector_all(sel)
      except Exception:
        anchors = []
      for a in anchors:
        try:
          onclick = a.get_attribute("onclick") or ""
          href = a.get_attribute("href") or ""
          text = (a.inner_text() or "").strip()
          import re
          m = re.search(r"gotoPage\((\d+)\)", onclick)
          target = None
          if m:
            try:
              target = int(m.group(1))
            except Exception:
              target = None
          if target == next_page_num or text == str(next_page_num) or text.lower() in ("sau", "next", ">", "»"):
            logger(f"→ Đi tới trang {next_page_num}")
            js = onclick.replace("javascript:", "").strip()
            if js:
              try:
                page_or_frame.evaluate(f"(function(){{try{{ {js} }}catch(e){{}} }})()")
                time.sleep(1.0)
                return True
              except Exception:
                pass
            try:
              a.click()
              time.sleep(1.0)
              return True
            except Exception:
              continue
        except Exception:
          continue
    try:
      page_or_frame.evaluate(f"(function(){{try{{ window.top && window.top.page && window.top.page.gotoPage({next_page_num}); }}catch(e){{}} }})()")
      time.sleep(1.0)
      return True
    except Exception:
      pass
  except Exception as e:
    logger(f"Paging error: {e}")
  return False
