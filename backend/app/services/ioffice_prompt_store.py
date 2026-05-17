from app.db import get_db_connection
from app.services.ioffice_prompt_schema import ensure_ioffice_prompt_tables


RESERVED_PRESET_IDS = {"default", "p1", "p3"}


def purge_reserved_prompt_presets() -> None:
  ensure_ioffice_prompt_tables()
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        for pid in RESERVED_PRESET_IDS:
          cur.execute("DELETE FROM ioffice_prompt_presets WHERE id=%s", (pid,))
  except Exception:
    return


def list_prompt_presets() -> list[dict]:
  ensure_ioffice_prompt_tables()
  purge_reserved_prompt_presets()
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT id, label, prompt, enabled, sort_order, created_at, updated_at
        FROM ioffice_prompt_presets
        ORDER BY sort_order ASC, id ASC
        """
      )
      rows = cur.fetchall() or []
  out: list[dict] = []
  for r in rows:
    if str(r.get("id") or "") in RESERVED_PRESET_IDS:
      continue
    out.append(
      {
        "id": str(r.get("id") or ""),
        "label": str(r.get("label") or ""),
        "prompt": str(r.get("prompt") or ""),
        "enabled": bool(r.get("enabled")),
        "sort_order": int(r.get("sort_order") or 0),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
      }
    )
  return out


def upsert_prompt_preset(*, pid: str, label: str, prompt: str, enabled: bool = True, sort_order: int = 0) -> None:
  ensure_ioffice_prompt_tables()
  pid2 = (pid or "").strip()
  if not pid2:
    raise RuntimeError("missing_id")
  if pid2 in RESERVED_PRESET_IDS:
    raise RuntimeError("reserved_id")
  label2 = (label or "").strip()
  if not label2:
    raise RuntimeError("missing_label")
  prompt2 = (prompt or "").strip()
  if not prompt2:
    raise RuntimeError("missing_prompt")
  en = 1 if enabled else 0
  so = int(sort_order or 0)

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        INSERT INTO ioffice_prompt_presets (id, label, prompt, enabled, sort_order)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          label=VALUES(label),
          prompt=VALUES(prompt),
          enabled=VALUES(enabled),
          sort_order=VALUES(sort_order)
        """,
        (pid2, label2, prompt2, en, so),
      )


def delete_prompt_preset(pid: str) -> None:
  ensure_ioffice_prompt_tables()
  pid2 = (pid or "").strip()
  if not pid2:
    raise RuntimeError("missing_id")
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("DELETE FROM ioffice_prompt_presets WHERE id=%s", (pid2,))
