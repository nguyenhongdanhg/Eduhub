import time
from playwright.sync_api import TimeoutError as PlayTimeout

from fetcher.selectors import ZIP_SELECTORS, VIEW_FILE_SELECTORS
from fetcher.utils_playwright import pick_visible_element
from utils import slugify_filename, ensure_dir, FILES_ROOT

from fetcher.control import MAX_DOWNLOAD_TRIES


def download_zip_from_modal(page, doc_id, so_ky_hieu, trich_yeu, save_dir, logger):
  saved = []
  last_err = None
  for attempt in range(1, MAX_DOWNLOAD_TRIES + 1):
    try:
      time.sleep(0.35)
      zip_el = pick_visible_element(page, ZIP_SELECTORS)
      if not zip_el:
        for vtry in range(2):
          vb = pick_visible_element(page, VIEW_FILE_SELECTORS)
          if not vb:
            break
          try:
            vb.click()
            logger(f"[{doc_id}] Clicked view-file fallback (try {vtry+1})")
          except Exception as e:
            logger(f"[{doc_id}] view-file click err: {e}")
          time.sleep(0.7)
          zip_el = pick_visible_element(page, ZIP_SELECTORS)
          if zip_el:
            break
      if not zip_el:
        frames = page.query_selector_all("div.modal-content iframe")
        for ifr in frames:
          try:
            fr = ifr.content_frame()
            if not fr:
              continue
            zip_el = pick_visible_element(fr, ZIP_SELECTORS)
            if zip_el:
              logger(f"[{doc_id}] Found ZIP inside iframe")
              with page.expect_download(timeout=45000) as dl:
                zip_el.click()
              d = dl.value
              base = so_ky_hieu or f"VB_{doc_id}"
              short = (trich_yeu or "")[:50]
              fname = slugify_filename(f"{base}_{short}.zip")
              zipper = save_dir / fname
              ensure_dir(zipper.parent)
              d.save_as(zipper.as_posix())
              rel = zipper.relative_to(FILES_ROOT).as_posix()
              saved.append(rel)
              logger(f"[{doc_id}] Downloaded from iframe → {rel}")
              return saved
          except Exception as e:
            logger(f"[{doc_id}] iframe zip err: {e}")
            continue
      if not zip_el:
        last_err = "ZIP_NOT_FOUND"
        logger(f"[{doc_id}] ZIP not found attempt {attempt}")
        time.sleep(0.5)
        continue
      try:
        with page.expect_download(timeout=45000) as dl:
          zip_el.click()
        d = dl.value
        base = so_ky_hieu or f"VB_{doc_id}"
        short = (trich_yeu or "")[:50]
        fname = slugify_filename(f"{base}_{short}.zip")
        zipper = save_dir / fname
        ensure_dir(zipper.parent)
        d.save_as(zipper.as_posix())
        rel = zipper.relative_to(FILES_ROOT).as_posix()
        saved.append(rel)
        logger(f"[{doc_id}] ✔ Downloaded ZIP → {rel}")
        return saved
      except PlayTimeout as e:
        last_err = f"DOWNLOAD_TIMEOUT:{e}"
        logger(f"[{doc_id}] download timeout attempt {attempt}: {e}")
        time.sleep(0.5)
        continue
      except Exception as e:
        last_err = f"DOWNLOAD_ERR:{e}"
        logger(f"[{doc_id}] download err attempt {attempt}: {e}")
        time.sleep(0.5)
        continue
    except Exception as e:
      last_err = str(e)
      logger(f"[{doc_id}] download_zip exception attempt {attempt}: {e}")
      time.sleep(0.5)
      continue
  logger(f"[{doc_id}] download failed after {MAX_DOWNLOAD_TRIES} tries: {last_err}")
  return saved
