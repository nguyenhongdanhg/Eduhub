from fetcher.utils_playwright import safe_inner_text
from database import get_account


def _collect_rows_from(page_like):
  try:
    return page_like.query_selector_all("tr.log_role_type_received, tr[act_id]") or []
  except Exception:
    return []


def _try_text(el, sel_list):
  for sel in sel_list:
    try:
      node = el.query_selector(sel)
      if node:
        t = safe_inner_text(node)
        if t:
          return t.strip()
    except Exception:
      continue
  return ""


def _find_assigned_text(el):
  try:
    ps = el.query_selector_all("p, td p") or []
    for p in ps:
      try:
        txt = safe_inner_text(p) or ""
        if txt and ("Chuyển tới:" in txt or "CHUYỂN TỚI:" in txt.upper()):
          return txt.strip()
      except Exception:
        continue
  except Exception:
    pass
  return ""


def extract_latest_instruction(page, logger, doc_id):
  try:
    rows = page.query_selector_all("tr.log_role_type_received, tr[act_id]")
    if rows:
      r0 = rows[0]
      cmt = r0.query_selector("span[name='comment']")
      if cmt:
        txt = safe_inner_text(cmt)
        if txt:
          return txt
      p = r0.query_selector("p")
      if p:
        txt = safe_inner_text(p)
        if txt:
          return txt
    frames = page.query_selector_all("div.modal-content iframe")
    for ifr in frames:
      try:
        fr = ifr.content_frame()
        if not fr:
          continue
        rows = fr.query_selector_all("tr.log_role_type_received, tr[act_id]")
        if not rows:
          continue
        r0 = rows[0]
        cmt = r0.query_selector("span[name='comment']")
        if cmt:
          txt = safe_inner_text(cmt)
          if txt:
            return txt
        p = r0.query_selector("p")
        if p:
          txt = safe_inner_text(p)
          if txt:
            return txt
        td = r0.query_selector("td[link_param], td")
        if td:
          txt = safe_inner_text(td)
          if txt:
            return txt
      except Exception:
        continue
    return ""
  except Exception as e:
    logger(f"[{doc_id}] extract_latest_instruction err: {e}")
    return ""


def extract_account_task_summary(page, logger, doc_id):
  try:
    acc = get_account()
    user = (acc.get("username") or "").strip()
    if not user:
      return {"summary": "", "more": 0}

    rows = _collect_rows_from(page)
    if not rows:
      frames = page.query_selector_all("div.modal-content iframe")
      for ifr in frames:
        try:
          fr = ifr.content_frame()
          if not fr:
            continue
          rows = _collect_rows_from(fr)
          if rows:
            break
        except Exception:
          continue

    related = []
    for r in rows:
      try:
        who = _try_text(r, ["span.log_user_xuly", "#hid_lux_user_xuly", "#hid_lux_updated_by"])
        who = (who or "").strip()
        primary = _try_text(r, ["span[name='comment']", "td[link_param]", "p"])
        assigned = _find_assigned_text(r)
        text = (assigned or primary or "").strip()
        cond = user and (user in who or f"({user})" in who or user in text)
        if not cond:
          if "Chuyển tới:" in text or "Đồng xử lý:" in text or "chỉ đạo" in text.lower():
            cond = user in text
        if cond:
          directive = ""
          sender = ""
          if "chỉ đạo" in text.lower():
            directive = text
          if who:
            sender = who
          related.append({"sender": sender, "text": text})
      except Exception:
        continue

    if not related:
      return {"summary": "", "more": 0}

    last = related[0]
    parts = []
    if last.get("sender"):
      parts.append(f"Người gửi: {last['sender']}")
    if last.get("text"):
      parts.append(last["text"])
    summary = " | ".join(parts)
    return {"summary": summary[:300], "more": max(0, len(related) - 1)}
  except Exception as e:
    logger(f"[{doc_id}] extract_account_task_summary err: {e}")
    return {"summary": "", "more": 0}


def extract_deadline(page, logger, doc_id):
  try:
    def _get_from(p):
      try:
        el = p.query_selector("#spanNhacNhoHanXuLy span, #spanNhacNhoHanXuLy")
        if el:
          txt = safe_inner_text(el)
          if txt:
            return txt
      except Exception:
        pass
      try:
        el2 = p.query_selector("#dt_thongtin_vanban tbody tr:nth-child(8) td:nth-child(6)")
        if el2:
          txt = safe_inner_text(el2)
          if txt:
            return txt
      except Exception:
        pass
      return ""

    import re

    def pick_date(s: str) -> str:
      if not s:
        return ""
      m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", s)
      return m.group(1) if m else ""

    val = pick_date(_get_from(page))
    if val:
      return val
    frames = page.query_selector_all("div.modal-content iframe")
    for ifr in frames:
      try:
        fr = ifr.content_frame()
        if not fr:
          continue
        val = pick_date(_get_from(fr))
        if val:
          return val
      except Exception:
        continue
    return ""
  except Exception as e:
    logger(f"[{doc_id}] extract_deadline err: {e}")
    return ""
