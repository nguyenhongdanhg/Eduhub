import re
import time
from dataclasses import dataclass
from typing import Optional

from app.db import get_db_connection


def _split_keys(raw: str) -> list[str]:
  s = str(raw or "").strip()
  if not s:
    return []
  parts = re.split(r"[\s,;]+", s)
  out: list[str] = []
  seen: set[str] = set()
  for p in parts:
    k = str(p or "").strip()
    if not k:
      continue
    if k in seen:
      continue
    seen.add(k)
    out.append(k)
  return out


def list_db_keys(base_conf_key: str) -> list[str]:
  base = str(base_conf_key or "").strip()
  if not base:
    return []
  rows: list[dict] = []
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          """
          SELECT conf_key, conf_value
          FROM system_configs
          WHERE conf_key=%s OR conf_key LIKE %s
          ORDER BY conf_key ASC
          """,
          (base, f"{base}_%"),
        )
        rows = cur.fetchall() or []
  except Exception:
    rows = []
  all_keys: list[str] = []
  for r in rows:
    all_keys.extend(_split_keys((r or {}).get("conf_value")))
  return all_keys


def _parse_http_code(msg: str) -> Optional[int]:
  m = re.search(r"\bHTTP\s+(\d{3})\b", str(msg or ""))
  if not m:
    return None
  try:
    return int(m.group(1))
  except Exception:
    return None


def is_key_exhausted_error(err: Exception) -> bool:
  msg = str(err or "")
  code = _parse_http_code(msg)
  if code in (401, 402, 403, 408, 429, 500, 502, 503, 504):
    return True
  hay = msg.lower()
  return any(
    x in hay
    for x in (
      "api_key_invalid",
      "api key invalid",
      "invalid api key",
      "api key expired",
      "insufficient_quota",
      "quota",
      "rate limit",
      "rate_limit",
      "resource_exhausted",
      "billing",
      "overloaded",
    )
  )


@dataclass
class _KeyState:
  key: str
  blocked_until: float = 0.0


class DbKeyRing:
  def __init__(self, base_conf_key: str) -> None:
    self.base_conf_key = str(base_conf_key or "").strip()
    self._states: list[_KeyState] = []
    self._idx = 0
    self._loaded_at = 0.0

  def _refresh_if_needed(self) -> None:
    now = time.time()
    if self._states and (now - self._loaded_at) < 60:
      return
    keys = list_db_keys(self.base_conf_key)
    self._loaded_at = now
    prev = {s.key: s for s in self._states}
    self._states = [prev.get(k, _KeyState(key=k)) for k in keys]
    if self._idx >= len(self._states):
      self._idx = 0

  def list_keys(self) -> list[str]:
    self._refresh_if_needed()
    return [s.key for s in self._states]

  def pick(self) -> Optional[str]:
    self._refresh_if_needed()
    if not self._states:
      return None
    now = time.time()
    n = len(self._states)
    for _ in range(n):
      s = self._states[self._idx % n]
      self._idx = (self._idx + 1) % n
      if s.blocked_until <= now:
        return s.key
    return None

  def mark_bad(self, key: str, *, cooldown_seconds: int) -> None:
    k = str(key or "").strip()
    if not k:
      return
    now = time.time()
    for s in self._states:
      if s.key == k:
        s.blocked_until = max(s.blocked_until, now + float(cooldown_seconds))
        return


_rings: dict[str, DbKeyRing] = {}


def get_ring(base_conf_key: str) -> DbKeyRing:
  k = str(base_conf_key or "").strip()
  if not k:
    return DbKeyRing("")
  if k not in _rings:
    _rings[k] = DbKeyRing(k)
  return _rings[k]
