from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
  from zoneinfo import ZoneInfo
except Exception:
  ZoneInfo = None


_VN_TZ = None
if ZoneInfo:
  try:
    _VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
  except Exception:
    _VN_TZ = None
if _VN_TZ is None:
  _VN_TZ = timezone(timedelta(hours=7))


def now_vn() -> datetime:
  if _VN_TZ is None:
    return datetime.now()
  return datetime.now(_VN_TZ)


def now_vn_iso() -> str:
  return now_vn().isoformat()
