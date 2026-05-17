import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote


BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "fetch.log"
_storage = (__import__("os").environ.get("EDUAI_STORAGE_ROOT") or str(BASE_DIR / "storage")).strip()
FILES_ROOT = Path(_storage) / "ioffice"
RAG_FILES_ROOT = Path(_storage) / "rag_uploads"


def slugify_filename(value, allow_unicode=False):
  value = str(value)
  if allow_unicode:
    value = unicodedata.normalize("NFC", value)
  else:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
  value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value)
  value = re.sub(r"\s+", "_", value)
  return value[:200]


def ensure_dir(p: Path):
  if not p.exists():
    p.mkdir(parents=True, exist_ok=True)


def write_log_file(text: str):
  try:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
      f.write(text + "\n")
  except Exception:
    pass


def log_to_queue(line: str, q):
  ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
  out = f"{ts} {line}"
  try:
    if q is None:
      write_log_file(out)
      return
    q.put_nowait(out)
  except Exception:
    write_log_file(out)


def make_safe_relative_from_any(path_like: str) -> str:
  if not path_like:
    return ""
  try:
    s = unquote(str(path_like))
  except Exception:
    s = str(path_like)
  s = s.replace("\\", "/")
  s = s.lstrip("/")
  low = s.lower()
  if "ioffice/" in low:
    idx = low.find("ioffice/")
    rel = s[idx + 7 :]
  elif "files/" in low:
    idx = low.find("files/")
    rel = s[idx + 6 :]
  elif "file:manual/" in low:
      # Support for file:manual/... prefix
      idx = low.find("file:manual/")
      # We want to keep "manual/..." part, so we skip "file:" (5 chars)
      rel = s[idx + 5 :]
  elif "manual/" in low:
      # Support for manual uploads directly
      idx = low.find("manual/")
      rel = s[idx:]
  else:
    if ":" in s:
      parts = s.split("/")
      found = None
      for i, part in enumerate(parts):
        if part.upper() in ("PH", "XLC"):
          found = parts[i:]
          break
      if found:
        rel = "/".join(found)
      else:
        rel = parts[-1]
    else:
      rel = s
  rel = rel.strip("/ ")
  rel_path = Path(rel)
  safe = "/".join(rel_path.parts)
  return safe
