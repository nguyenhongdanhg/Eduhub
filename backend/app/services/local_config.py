import json
import os
from pathlib import Path

_cache: dict | None = None
_cache_path: Path | None = None
_cache_mtime_ns: int | None = None


def _default_path() -> Path:
  root = Path(__file__).resolve().parents[3]
  return root / ".eduai.local.json"


def _load_file(path: Path) -> dict:
  try:
    raw = path.read_text(encoding="utf-8")
  except Exception:
    return {}
  try:
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}
  except Exception:
    return {}


def load_local_config() -> dict:
  p = (os.getenv("EDUAI_LOCAL_CONFIG_PATH") or "").strip()
  path = Path(p).expanduser() if p else _default_path()
  global _cache, _cache_path, _cache_mtime_ns
  mtime_ns: int | None = None
  try:
    mtime_ns = int(path.stat().st_mtime_ns)
  except Exception:
    mtime_ns = None

  if _cache is not None and _cache_path == path and _cache_mtime_ns == mtime_ns:
    return _cache

  _cache_path = path
  _cache_mtime_ns = mtime_ns
  _cache = _load_file(path)
  return _cache


def get_list(key: str) -> list[str]:
  cfg = load_local_config()
  v = cfg.get(key)
  if not isinstance(v, list):
    return []
  out: list[str] = []
  for it in v:
    if isinstance(it, str) and it.strip():
      out.append(it.strip())
  return out


def pick_key(key: str) -> str | None:
  items = get_list(key)
  return items[0] if items else None
