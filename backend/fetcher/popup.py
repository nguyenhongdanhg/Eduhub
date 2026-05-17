import time

from fetcher.control import MAX_POPUP_TRIES
from fetcher.control import BASE_IOFFICE


def build_link_goc(doc_id):
  return (
    "https://vpdttq.vnptioffice.vn/qlvbdh/main?"
    "IzL1Dx9w5BxmCEtw5A9c6Bnb=CEt1CzAwJyHx4yjbTq9vCBtuTt9fCcPbUo..&"
    "IyLlCc5f5w5fCES.=DBny4Y9y4B1V4ctk3yPbCY9aDz5Y3yPbCY9fCcPbUo..&"
    "CBAkTA9f5o..=m2766&"
    "4c9lTFLwDctm=2&"
    "6yXl=VAN_BAN_DEN_CA_NHAN&"
    f"Cc9m={doc_id}&"
    "TFbm5B5xCcLw6B9k=0"
  )


def get_link_goc_from_row_popup(page, row, context, logger, doc_id):
  last_err = None
  for attempt in range(1, MAX_POPUP_TRIES + 1):
    try:
      btn = row.query_selector("a.xem_tab_moi")
      if not btn:
        if doc_id:
          q = page.query_selector(f"tr[id='vb_{doc_id}'], tr[flyid='{doc_id}']")
          if q:
            btn = q.query_selector("a.xem_tab_moi")
      if not btn:
        return ""
      with context.expect_page(timeout=5000) as popup_info:
        btn.click()
      new_page = popup_info.value
      new_page.wait_for_load_state("load", timeout=8000)
      url = new_page.url
      try:
        new_page.close()
      except Exception:
        pass
      logger(f"[{doc_id}] link_goc popup OK: {url}")
      return url
    except Exception as e:
      last_err = e
      logger(f"[{doc_id}] popup try {attempt} err: {e}")
      time.sleep(0.3)
      continue
  logger(f"[{doc_id}] popup failed after {MAX_POPUP_TRIES} tries: {last_err}")
  return ""
