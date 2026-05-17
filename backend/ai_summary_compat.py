import re
from io import BytesIO
from pathlib import Path
import zipfile


def _norm(s: str) -> str:
  try:
    return (s or "").strip()
  except Exception:
    return s or ""


def _normalize_text(s: str) -> str:
  t = (s or "").replace("\r\n", "\n").replace("\r", "\n")
  t = re.sub(r"[ \t]+", " ", t)
  t = re.sub(r"\n{3,}", "\n\n", t)
  return t.strip()


def _is_pdf_garbage(s: str) -> bool:
  t = (s or "").strip()
  if not t:
    return True
  if len(t) < 60:
    return True
  printable = sum(1 for ch in t if ch.isprintable())
  if printable / max(1, len(t)) < 0.85:
    return True
  letters = sum(1 for ch in t if ch.isalnum())
  if letters / max(1, len(t)) < 0.15:
    return True
  return False


def extract_text_from_zip(zip_path: Path) -> str:
  try:
    with zipfile.ZipFile(zip_path, "r") as z:
      for member in z.namelist():
        text = _extract_text_from_member(z, member)
        if text and text.strip():
          return _normalize_text(text)
  except Exception:
    return ""
  return ""


def extract_text_from_zip_selected(zip_path: Path, selected_members: list[str] | None) -> str:
  picked = [str(x) for x in (selected_members or []) if str(x).strip()]
  if not picked:
    return extract_text_from_zip(zip_path)
  try:
    with zipfile.ZipFile(zip_path, "r") as z:
      texts: list[str] = []
      for member in picked:
        if member not in z.namelist():
          continue
        t = _extract_text_from_member(z, member)
        if t and t.strip():
          texts.append(_normalize_text(t))
      return _normalize_text("\n\n".join([x for x in texts if x]))
  except Exception:
    return ""


def _extract_text_from_member(z: zipfile.ZipFile, member: str) -> str:
  try:
    ext = Path(member).suffix.lower()
    if ext in (".txt", ".md", ".html", ".htm"):
      data = z.read(member)
      try:
        return data.decode("utf-8", errors="ignore")
      except Exception:
        return data.decode("latin-1", errors="ignore")
    if ext == ".pdf":
      try:
        import pypdf
        data = z.read(member)
        reader = pypdf.PdfReader(BytesIO(data))
        texts = []
        for pg in reader.pages:
          t = pg.extract_text() or ""
          if t.strip():
            texts.append(t)
        val = _normalize_text("\n".join(texts))
        if val and not _is_pdf_garbage(val):
          return val
      except Exception:
        pass
      try:
        import PyPDF2
        data = z.read(member)
        reader = PyPDF2.PdfReader(BytesIO(data))
        texts = []
        for pg in reader.pages:
          t = pg.extract_text() or ""
          if t.strip():
            texts.append(t)
        val = _normalize_text("\n".join(texts))
        if val and not _is_pdf_garbage(val):
          return val
      except Exception:
        pass
      try:
        from pdfminer.high_level import extract_text as _pdfminer_extract
        data = z.read(member)
        val = _normalize_text(_pdfminer_extract(BytesIO(data)) or "")
        if val and not _is_pdf_garbage(val):
          return val
      except Exception:
        pass
      try:
        import fitz
        data = z.read(member)
        doc = fitz.open(stream=data, filetype="pdf")
        texts = []
        for pg in doc:
          t = pg.get_text() or ""
          if t.strip():
            texts.append(t)
        val = _normalize_text("\n".join(texts))
        if val and not _is_pdf_garbage(val):
          return val
      except Exception:
        pass
      try:
        import pdfplumber
        data = z.read(member)
        with pdfplumber.open(BytesIO(data)) as pdf:
          texts = []
          for pg in pdf.pages:
            t = pg.extract_text() or ""
            if t.strip():
              texts.append(t)
          val = _normalize_text("\n".join(texts))
          if val and not _is_pdf_garbage(val):
            return val
      except Exception:
        pass
      try:
        data = z.read(member)
        val = _ocr_pdf_images(data)
        if val:
          return val
      except Exception:
        pass
      return ""
    if ext == ".docx":
      try:
        data = z.read(member)
        with zipfile.ZipFile(BytesIO(data)) as dz:
          xml = dz.read("word/document.xml")
        s = xml.decode("utf-8", errors="ignore")
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()
      except Exception:
        return ""
    return ""
  except Exception:
    return ""
