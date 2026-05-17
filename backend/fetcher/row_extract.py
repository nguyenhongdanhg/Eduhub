def extract_row_fields(row):
  def safe(el):
    try:
      return el.inner_text().strip()
    except Exception:
      return ""

  raw_id = (row.get_attribute("flyid") or row.get_attribute("id") or "").strip()
  docid = ""
  try:
    import re
    m = re.search(r"(\d{5,})$", raw_id)
    if m:
      docid = m.group(1)
    else:
      if raw_id.startswith("vb_"):
        docid = raw_id.replace("vb_", "")
      else:
        for el in row.query_selector_all('[onclick*="showDocDetail"]'):
          oc = (el.get_attribute("onclick") or "").strip()
          m2 = re.search(r"showDocDetail\([^,]*,\s*(\d+)\b", oc)
          if m2:
            docid = m2.group(1)
            break
  except Exception:
    docid = raw_id or ""
  try:
    so_ky_hieu = row.get_attribute("so_ky_hieu") or row.get_attribute("data-so_ky_hieu") or safe(row.query_selector(".so_ky_hieu")) or ""
  except Exception:
    so_ky_hieu = ""
  trich = ""
  try:
    if docid:
      el = row.query_selector(f"#vbden_trichyeu_{docid}") or row.query_selector(f"#dsvb_trichyeu_{docid}")
      if el:
        trich = safe(el)
  except Exception:
    trich = ""
  if not trich:
    trich = row.get_attribute("trich_yeu") or safe(row.query_selector(".trich_yeu") or row)
  hinh_thuc = row.get_attribute("hinh_thuc") or safe(row.query_selector(".hideHTVB") or row)
  ngay_van_ban = row.get_attribute("ngay_van_ban") or safe(row.query_selector(".td_ngay_van_ban") or row)
  ngay_den = row.get_attribute("ngay_den") or safe(row.query_selector(".hide_ngayden_bte") or row)
  don_vi = row.get_attribute("don_vi_ban_hanh") or row.get_attribute("don_vi_soan_thao") or safe(row.query_selector(".vanbanden_hienthi1") or row)
  vai_tro = row.get_attribute("role_type_code") or safe(row.query_selector("#col_doc_vaitro") or row.query_selector("td#col_doc_vaitro") or row)
  try:
    st_cell = row.query_selector(".hidetrangthaiXLCC, .hidetrangthai, .hidetrangthai_xl")
    trang_thai = st_cell.inner_text().strip() if st_cell else ""
  except Exception:
    trang_thai = ""
  return dict(
    doc_id=docid,
    so_ky_hieu=so_ky_hieu,
    trich_yeu=trich,
    hinh_thuc=hinh_thuc,
    ngay_van_ban=ngay_van_ban,
    ngay_den=ngay_den,
    don_vi_ban_hanh=don_vi,
    vai_tro=vai_tro,
    trang_thai_xu_ly=trang_thai,
  )
