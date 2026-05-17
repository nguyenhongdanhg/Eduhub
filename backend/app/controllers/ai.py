import asyncio
import json
import urllib.parse
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

router = APIRouter()
_RUNS: dict[str, dict] = {}

def _user_id(x_user_id: str | None) -> int:
  try:
    return int(x_user_id or "1")
  except Exception:
    return 1


def _now_utc() -> datetime:
  return datetime.now(timezone.utc)


def _content_disposition(filename: str) -> str:
  safe = str(filename or "document.docx").replace("\\", "_").replace("/", "_").replace('"', "'")
  ascii_name = "".join(ch if 32 <= ord(ch) < 127 else "_" for ch in safe) or "document.docx"
  quoted = urllib.parse.quote(safe, safe="")
  return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}"


def _truncate(s: str, max_len: int) -> str:
  t = str(s or "")
  if len(t) <= max_len:
    return t
  return t[: max_len - 1] + "…"


def _safe_json(obj) -> str:
  try:
    return json.dumps(obj, ensure_ascii=False)
  except Exception:
    return "{}"


def _parse_json(raw):
  if raw is None:
    return None
  if isinstance(raw, (dict, list)):
    return raw
  try:
    return json.loads(raw)
  except Exception:
    return None


def _fetch_ioffice_docs_snapshot(doc_ids: list[str]) -> list[dict]:
  from app.db import get_db_connection

  ids = [str(x or "").strip() for x in (doc_ids or []) if str(x or "").strip()]
  if not ids:
    return []
  placeholders = ",".join(["%s"] * len(ids))
  sql = f"""
    SELECT
      ioffice_doc_id AS doc_id,
      so_ky_hieu,
      trich_yeu,
      don_vi_ban_hanh,
      ngay_den,
      han_xu_ly,
      link_goc,
      file_path,
      file_name
    FROM ioffice_documents
    WHERE ioffice_doc_id IN ({placeholders})
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, tuple(ids))
      rows = list(cur.fetchall() or [])
  by_id = {str(r.get("doc_id") or ""): r for r in rows if isinstance(r, dict) and r.get("doc_id")}
  out = []
  for did in ids:
    r = by_id.get(did) or {"doc_id": did}
    out.append(
      {
        "doc_id": str(r.get("doc_id") or did),
        "so_ky_hieu": r.get("so_ky_hieu") or "",
        "trich_yeu": r.get("trich_yeu") or "",
        "link_goc": r.get("link_goc") or "",
        "duong_dan_file": r.get("file_path") or "",
        "file_name": r.get("file_name") or "",
      }
    )
  return out


class PrincipalDecisionCreateBody(BaseModel):
  source: str | None = None
  title: str | None = None
  semantic_query: str | None = None
  doc_ids: list[str] = []
  work_ids: list[int] = []
  preset_id: str | None = None
  mode: str | None = None
  custom_prompt: str | None = None
  user_request: str
  use_rag: bool = True
  model: str | None = None
  provider: str | None = None
  generated_text: str
  citations: dict | None = None
  docs_snapshot: list[dict] | None = None


class PrincipalDecisionUpdateBody(BaseModel):
  title: str | None = None
  semantic_query: str | None = None
  doc_ids: list[str] | None = None
  work_ids: list[int] | None = None
  preset_id: str | None = None
  mode: str | None = None
  custom_prompt: str | None = None
  user_request: str | None = None
  use_rag: bool | None = None
  use_web: bool | None = None
  deep_research: bool | None = None
  web_provider: str | None = None
  make_podcast: bool | None = None
  model: str | None = None
  provider: str | None = None
  uploaded_rag_documents: list[dict] | None = None
  ai_suggestion: str | None = None
  thinking: str | None = None
  thinking_log: str | None = None
  citations: dict | None = None
  podcast_script: str | None = None
  pending_questions: list[str] | None = None
  reasoning_turns: list[dict] | None = None
  ui_layout: str | None = None
  request_collapsed: bool | None = None
  workspace_id: str | None = None
  workflow_status: str | None = None


class PrincipalDecisionRegenerateBody(BaseModel):
  doc_ids: list[str] | None = None
  work_ids: list[int] | None = None
  preset_id: str | None = None
  mode: str | None = None
  custom_prompt: str | None = None
  user_request: str | None = None
  use_rag: bool | None = None
  use_web: bool | None = None
  deep_research: bool | None = None
  web_provider: str | None = None
  make_podcast: bool | None = None
  uploaded_rag_documents: list[dict] | None = None
  model: str | None = None
  provider: str | None = None


class PrincipalDecisionDraftBody(BaseModel):
  source: str | None = None
  title: str | None = None
  semantic_query: str | None = None
  doc_ids: list[str] = []
  work_ids: list[int] = []
  preset_id: str | None = None
  mode: str | None = None
  custom_prompt: str | None = None
  user_request: str
  use_rag: bool = True
  use_web: bool = False
  deep_research: bool = False
  web_provider: str | None = None
  make_podcast: bool = False
  model: str | None = None
  provider: str | None = None
  uploaded_rag_documents: list[dict] | None = None


@router.get("/principal/document-presets")
def list_principal_document_presets_api():
  from app.services.principal_document_presets import list_principal_document_presets
  return {"ok": True, "presets": list_principal_document_presets()}


@router.get("/principal/decisions")
def list_principal_decisions(
  limit: int | None = None,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  lim = int(limit or 50)
  if lim < 1:
    lim = 1
  if lim > 200:
    lim = 200

  sql = """
    SELECT
      d.id AS decision_id,
      d.decision_status,
      d.created_at,
      d.decided_at,
      r.id AS request_id,
      r.prompt,
      r.rag_query,
      d.ai_suggestion
    FROM ai_decisions d
    JOIN ai_requests r ON r.id=d.ai_request_id
    WHERE
      r.user_id=%s
      AND r.domain='MANAGEMENT'
      AND (
        COALESCE(LOWER(r.role_effective), '') IN ('principal', 'assistant')
        OR JSON_UNQUOTE(JSON_EXTRACT(r.rag_query, '$.type'))='principal_decision'
        OR JSON_UNQUOTE(JSON_EXTRACT(r.rag_query, '$.source'))='assistant'
      )
    ORDER BY d.id DESC
    LIMIT %s
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (uid, lim))
      rows = list(cur.fetchall() or [])

  items = []
  for r in rows:
    meta = _parse_json(r.get("rag_query"))
    title = ""
    updated_at = r.get("created_at")
    workflow_status = "DRAFT"
    if isinstance(meta, dict):
      title = str(meta.get("title") or "").strip()
      updated_at = meta.get("updated_at") or updated_at
      workflow_status = str(meta.get("workflow_status") or "").strip().upper() or workflow_status
    if not title:
      title = _truncate(str(r.get("prompt") or "").strip(), 120) or _truncate(str(r.get("ai_suggestion") or "").strip(), 120)
    items.append(
      {
        "id": int(r.get("decision_id") or 0),
        "status": str(r.get("decision_status") or "DRAFT"),
        "created_at": r.get("created_at"),
        "updated_at": updated_at,
        "decided_at": r.get("decided_at"),
        "title": title,
        "workflow_status": workflow_status,
      }
    )
  return {"ok": True, "items": items}


@router.get("/principal/export-docx/{decision_id}")
@router.get("/principal/decisions/{decision_id}/export-docx")
def export_principal_decision_docx_api(
  decision_id: int,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection
  from app.services.principal_docx_export import CONTENT_TYPE_DOCX, export_principal_decision_docx

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT
          d.id AS decision_id,
          d.ai_suggestion,
          r.user_id,
          r.prompt,
          r.rag_query
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None

  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  if int(row.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")

  meta = _parse_json(row.get("rag_query"))
  if not isinstance(meta, dict):
    meta = {}
  title = str(meta.get("title") or row.get("prompt") or f"Văn bản {did}").strip()
  generated_text = str(row.get("ai_suggestion") or "").strip()
  if not generated_text:
    raise HTTPException(status_code=400, detail="empty_generated_text")
  try:
    content, filename = export_principal_decision_docx(title=title, generated_text=generated_text, meta=meta, decision_id=did)
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
  return Response(
    content=content,
    media_type=CONTENT_TYPE_DOCX,
    headers={"Content-Disposition": _content_disposition(filename), "Cache-Control": "no-store"},
  )


@router.get("/principal/decisions/{decision_id}")
def get_principal_decision(
  decision_id: int,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  sql = """
    SELECT
      d.id AS decision_id,
      d.decision_status,
      d.ai_suggestion,
      d.human_decision,
      d.decided_by,
      d.decided_at,
      d.created_at,
      r.id AS request_id,
      r.user_id,
      r.role_effective,
      r.domain,
      r.prompt,
      r.rag_query,
      r.model
    FROM ai_decisions d
    JOIN ai_requests r ON r.id=d.ai_request_id
    WHERE d.id=%s
    LIMIT 1
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (did,))
      row = cur.fetchone() or None

  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  if int(row.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")

  meta = _parse_json(row.get("rag_query"))
  return {
    "ok": True,
    "item": {
      "id": int(row.get("decision_id") or 0),
      "status": str(row.get("decision_status") or "DRAFT"),
      "created_at": row.get("created_at"),
      "decided_at": row.get("decided_at"),
      "decided_by": row.get("decided_by"),
      "prompt": str(row.get("prompt") or ""),
      "model": str(row.get("model") or ""),
      "meta": meta if isinstance(meta, dict) else {},
      "ai_suggestion": str(row.get("ai_suggestion") or ""),
      "human_decision": str(row.get("human_decision") or ""),
    },
  }


from app.services.ioffice_audio import _tts_audio, _prepare_tts_text

@router.get("/principal/decisions/{decision_id}/podcast_audio")
def get_principal_decision_podcast_audio(
  decision_id: int,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT d.id AS decision_id, r.user_id, r.rag_query
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None

  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  if int(row.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")

  meta = _parse_json(row.get("rag_query"))
  if not isinstance(meta, dict):
    meta = {}
  
  script = str(meta.get("podcast_script") or "").strip()
  if not script:
    raise HTTPException(status_code=404, detail="no_podcast_script")

  try:
    # Sử dụng chung logic TTS của iOffice Summary (cùng giọng, cùng tốc độ, cùng xử lý text)
    clean_text = _prepare_tts_text(script)
    audio_bytes, fmt = _tts_audio(clean_text)
    
    media_type = "audio/mpeg"
    if fmt == "wav":
      media_type = "audio/wav"

    return Response(
      content=audio_bytes,
      media_type=media_type,
      headers={
        "Content-Disposition": f'inline; filename="podcast_{did}.{fmt}"',
        "Cache-Control": "public, max-age=3600"
      }
    )
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))



@router.post("/principal/decisions")
def create_principal_decision(
  payload: PrincipalDecisionCreateBody,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  user_request = (payload.user_request or "").strip()
  if not user_request:
    raise HTTPException(status_code=400, detail="missing_user_request")
  generated = (payload.generated_text or "").strip()
  if not generated:
    raise HTTPException(status_code=400, detail="missing_generated_text")

  doc_ids = [str(x or "").strip() for x in (payload.doc_ids or []) if str(x or "").strip()]
  work_ids = [int(x) for x in (payload.work_ids or []) if int(x or 0) > 0]
  mode = (payload.mode or "").strip() or ("custom" if (payload.custom_prompt or "").strip() else "preset")
  title = (payload.title or "").strip()
  if not title:
    title = _truncate(user_request, 120)

  docs_snapshot = payload.docs_snapshot if isinstance(payload.docs_snapshot, list) else None
  if docs_snapshot is None and doc_ids:
    docs_snapshot = _fetch_ioffice_docs_snapshot(doc_ids)

  meta = {
    "type": "principal_decision",
    "source": (payload.source or "").strip() or "ioffice",
    "title": title,
    "semantic_query": (payload.semantic_query or "").strip(),
    "doc_ids": doc_ids,
    "work_ids": work_ids,
    "docs_snapshot": docs_snapshot or [],
    "preset_id": (payload.preset_id or "").strip() or None,
    "mode": mode,
    "custom_prompt": (payload.custom_prompt or "").strip() or None,
    "user_request": user_request,
    "use_rag": bool(payload.use_rag),
    "provider": (payload.provider or "").strip() or None,
    "citations": payload.citations if isinstance(payload.citations, dict) else {},
    "created_from": "ioffice_documents",
  }

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        INSERT INTO ai_requests (user_id, role_effective, domain, prompt, rag_query, model)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
          uid,
          "principal",
          "MANAGEMENT",
          user_request,
          _safe_json(meta),
          (payload.model or None),
        ),
      )
      req_id = int(cur.lastrowid or 0)
      cur.execute(
        """
        INSERT INTO ai_decisions (ai_request_id, ai_suggestion, human_decision, decision_status)
        VALUES (%s, %s, NULL, 'DRAFT')
        """,
        (req_id, generated),
      )
      dec_id = int(cur.lastrowid or 0)
    conn.commit()

  return {"ok": True, "id": dec_id}


@router.post("/principal/decisions/draft")
def create_principal_decision_draft(
  payload: PrincipalDecisionDraftBody,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  user_request = (payload.user_request or "").strip()
  if not user_request:
    raise HTTPException(status_code=400, detail="missing_user_request")

  doc_ids = [str(x or "").strip() for x in (payload.doc_ids or []) if str(x or "").strip()]
  work_ids = [int(x) for x in (payload.work_ids or []) if int(x or 0) > 0]
  mode = (payload.mode or "").strip() or ("custom" if (payload.custom_prompt or "").strip() else "preset")
  title = (payload.title or "").strip() or _truncate(user_request, 120)

  uploaded_docs = payload.uploaded_rag_documents if isinstance(payload.uploaded_rag_documents, list) else []
  docs_snapshot = _fetch_ioffice_docs_snapshot(doc_ids) if doc_ids else []

  meta = {
    "type": "principal_decision",
    "source": (payload.source or "").strip() or "assistant",
    "title": title,
    "semantic_query": (payload.semantic_query or "").strip(),
    "doc_ids": doc_ids,
    "work_ids": work_ids,
    "docs_snapshot": docs_snapshot,
    "preset_id": (payload.preset_id or "").strip() or None,
    "mode": mode,
    "custom_prompt": (payload.custom_prompt or "").strip() or None,
    "user_request": user_request,
    "use_rag": bool(payload.use_rag),
    "use_web": bool(payload.use_web),
    "deep_research": bool(payload.deep_research),
    "web_provider": (payload.web_provider or "").strip() or None,
    "make_podcast": bool(payload.make_podcast),
    "model": (payload.model or "").strip() or None,
    "provider": (payload.provider or "").strip() or None,
    "uploaded_rag_documents": uploaded_docs,
    "created_from": "assistant_draft",
  }

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        INSERT INTO ai_requests (user_id, role_effective, domain, prompt, rag_query, model)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
          uid,
          "principal",
          "MANAGEMENT",
          user_request,
          _safe_json(meta),
          None,
        ),
      )
      req_id = int(cur.lastrowid or 0)
      cur.execute(
        """
        INSERT INTO ai_decisions (ai_request_id, ai_suggestion, human_decision, decision_status)
        VALUES (%s, %s, NULL, 'DRAFT')
        """,
        (req_id, ""),
      )
      dec_id = int(cur.lastrowid or 0)
    conn.commit()

  return {"ok": True, "id": dec_id}


@router.put("/principal/decisions/{decision_id}")
def update_principal_decision(
  decision_id: int,
  payload: PrincipalDecisionUpdateBody,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT d.id AS decision_id, d.ai_request_id AS request_id, r.user_id, r.rag_query, r.prompt
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None
      if not row:
        raise HTTPException(status_code=404, detail="not_found")
      if int(row.get("user_id") or 0) != uid:
        raise HTTPException(status_code=403, detail="forbidden")

      meta = _parse_json(row.get("rag_query"))
      if not isinstance(meta, dict):
        meta = {}

      if payload.title is not None:
        meta["title"] = str(payload.title or "").strip()
      if payload.semantic_query is not None:
        meta["semantic_query"] = str(payload.semantic_query or "").strip()
      if payload.doc_ids is not None:
        meta["doc_ids"] = [str(x or "").strip() for x in (payload.doc_ids or []) if str(x or "").strip()]
        meta["docs_snapshot"] = _fetch_ioffice_docs_snapshot(meta["doc_ids"])
      if payload.work_ids is not None:
        meta["work_ids"] = [int(x) for x in (payload.work_ids or []) if int(x or 0) > 0]
      if payload.preset_id is not None:
        meta["preset_id"] = str(payload.preset_id or "").strip() or None
      if payload.mode is not None:
        meta["mode"] = str(payload.mode or "").strip() or None
      if payload.custom_prompt is not None:
        meta["custom_prompt"] = str(payload.custom_prompt or "").strip() or None
      if payload.user_request is not None:
        meta["user_request"] = str(payload.user_request or "").strip()
      if payload.use_rag is not None:
        meta["use_rag"] = bool(payload.use_rag)
      if payload.use_web is not None:
        meta["use_web"] = bool(payload.use_web)
      if payload.deep_research is not None:
        meta["deep_research"] = bool(payload.deep_research)
      if payload.web_provider is not None:
        meta["web_provider"] = str(payload.web_provider or "").strip() or None
      if payload.make_podcast is not None:
        meta["make_podcast"] = bool(payload.make_podcast)
      if payload.model is not None:
        meta["model"] = str(payload.model or "").strip() or None
      if payload.provider is not None:
        meta["provider"] = str(payload.provider or "").strip() or None
      if payload.uploaded_rag_documents is not None:
        meta["uploaded_rag_documents"] = payload.uploaded_rag_documents if isinstance(payload.uploaded_rag_documents, list) else []
      if payload.thinking is not None:
        meta["thinking"] = str(payload.thinking or "").strip()
      if payload.thinking_log is not None:
        meta["thinking_log"] = str(payload.thinking_log or "").strip()
      if payload.citations is not None:
        meta["citations"] = payload.citations if isinstance(payload.citations, dict) else {}
      if payload.podcast_script is not None:
        meta["podcast_script"] = str(payload.podcast_script or "").strip()
      if payload.pending_questions is not None:
        meta["pending_questions"] = [str(x or "").strip() for x in (payload.pending_questions or []) if str(x or "").strip()]
      if payload.reasoning_turns is not None:
        turns = payload.reasoning_turns if isinstance(payload.reasoning_turns, list) else []
        meta["reasoning_turns"] = turns[:50]
      if payload.ui_layout is not None:
        meta["ui_layout"] = str(payload.ui_layout or "").strip() or None
      if payload.request_collapsed is not None:
        meta["request_collapsed"] = bool(payload.request_collapsed)
      if payload.workspace_id is not None:
        meta["workspace_id"] = str(payload.workspace_id or "").strip() or None
      if payload.workflow_status is not None:
        ws = str(payload.workflow_status or "").strip().upper()
        if ws not in ("DRAFT", "PENDING", "COMPLETED"):
          raise HTTPException(status_code=400, detail="invalid_workflow_status")
        meta["workflow_status"] = ws
      meta["updated_at"] = _now_utc().isoformat()

      new_prompt = str(payload.user_request or "").strip() if payload.user_request is not None else str(row.get("prompt") or "")
      cur.execute("UPDATE ai_requests SET prompt=%s, rag_query=%s WHERE id=%s", (new_prompt, _safe_json(meta), int(row.get("request_id") or 0)))
      if payload.ai_suggestion is not None:
        cur.execute("UPDATE ai_decisions SET ai_suggestion=%s WHERE id=%s", (str(payload.ai_suggestion or ""), did))
    conn.commit()

  return {"ok": True}


@router.delete("/principal/decisions/{decision_id}")
def delete_principal_decision(
  decision_id: int,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT d.id AS decision_id, r.user_id
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None
      if not row:
        raise HTTPException(status_code=404, detail="not_found")
      if int(row.get("user_id") or 0) != uid:
        raise HTTPException(status_code=403, detail="forbidden")
      cur.execute("DELETE FROM ai_decisions WHERE id=%s", (did,))
    conn.commit()

  return {"ok": True}


@router.post("/principal/decisions/{decision_id}/regenerate")
async def regenerate_principal_decision(
  decision_id: int,
  payload: PrincipalDecisionRegenerateBody,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection
  from app.services.principal_deeptutor_agent import generate_principal_content_deeptutor

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT d.id AS decision_id, d.ai_request_id AS request_id, r.user_id, r.rag_query, r.prompt
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None

  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  if int(row.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")

  meta = _parse_json(row.get("rag_query"))
  if not isinstance(meta, dict):
    meta = {}

  stored_doc_ids = [str(x or "").strip() for x in (meta.get("doc_ids") or []) if str(x or "").strip()]
  stored_work_ids = [int(x) for x in (meta.get("work_ids") or []) if int(x or 0) > 0]

  doc_ids = [str(x or "").strip() for x in (payload.doc_ids or stored_doc_ids) if str(x or "").strip()]
  work_ids = [int(x) for x in (payload.work_ids or stored_work_ids) if int(x or 0) > 0]

  user_request = (payload.user_request if payload.user_request is not None else meta.get("user_request") or row.get("prompt") or "").strip()
  if not user_request:
    raise HTTPException(status_code=400, detail="missing_user_request")

  preset_id = (payload.preset_id if payload.preset_id is not None else meta.get("preset_id") or None)
  mode = (payload.mode if payload.mode is not None else meta.get("mode") or None)
  custom_prompt = (payload.custom_prompt if payload.custom_prompt is not None else meta.get("custom_prompt") or None)
  use_rag = bool(payload.use_rag) if payload.use_rag is not None else bool(meta.get("use_rag", True))

  if mode and str(mode).strip().lower() == "preset":
    custom_prompt = None
  if mode and str(mode).strip().lower() == "custom":
    preset_id = None

  use_web = bool(payload.use_web) if payload.use_web is not None else bool(meta.get("use_web", False))
  deep_research = bool(payload.deep_research) if payload.deep_research is not None else bool(meta.get("deep_research", False))
  web_provider = (payload.web_provider if payload.web_provider is not None else meta.get("web_provider") or None)
  make_podcast = bool(payload.make_podcast) if payload.make_podcast is not None else bool(meta.get("make_podcast", False))
  model = (payload.model if payload.model is not None else meta.get("model") or None)
  provider = (payload.provider if payload.provider is not None else meta.get("provider") or None)
  uploaded_docs = payload.uploaded_rag_documents if payload.uploaded_rag_documents is not None else (meta.get("uploaded_rag_documents") or [])
  if not isinstance(uploaded_docs, list):
    uploaded_docs = []
  uploaded_docs = payload.uploaded_rag_documents if payload.uploaded_rag_documents is not None else (meta.get("uploaded_rag_documents") or [])
  if not isinstance(uploaded_docs, list):
    uploaded_docs = []

  res = await generate_principal_content_deeptutor(
    doc_ids=doc_ids,
    work_ids=work_ids,
    user_request=user_request,
    preset_id=(str(preset_id).strip() if preset_id else None),
    custom_prompt=(str(custom_prompt).strip() if custom_prompt else None),
    use_rag=use_rag,
    use_web=use_web,
    deep_research=deep_research,
    web_provider=(str(web_provider).strip() if web_provider else None),
    make_podcast=make_podcast,
    uploaded_rag_documents=uploaded_docs,
    model=((payload.model if payload.model is not None else meta.get("model")) or None),
    provider=((payload.provider if payload.provider is not None else meta.get("provider")) or None),
  )

  out_text = str(res.get("text") or "").strip()
  if bool(res.get("need_user_input")):
    questions = res.get("questions") if isinstance(res.get("questions"), list) else []
    raise HTTPException(status_code=409, detail={"need_user_input": True, "questions": questions, "ideagen": res.get("ideagen") or ""})
  citations = res.get("citations") if isinstance(res.get("citations"), dict) else {}
  podcast_script = str(res.get("podcast_script") or "").strip()
  thinking = str(res.get("thinking") or "").strip()

  meta["doc_ids"] = doc_ids
  meta["work_ids"] = work_ids
  meta["docs_snapshot"] = _fetch_ioffice_docs_snapshot(doc_ids) if doc_ids else (meta.get("docs_snapshot") or [])
  meta["preset_id"] = (str(preset_id).strip() if preset_id else None)
  meta["mode"] = (str(mode).strip() if mode else ("custom" if (custom_prompt or "").strip() else "preset"))
  meta["custom_prompt"] = (str(custom_prompt).strip() if custom_prompt else None)
  meta["user_request"] = user_request
  meta["use_rag"] = use_rag
  meta["use_web"] = use_web
  meta["deep_research"] = deep_research
  meta["web_provider"] = (str(web_provider).strip() if web_provider else None)
  meta["make_podcast"] = make_podcast
  meta["model"] = (str(model).strip() if model else None)
  meta["provider"] = (str(provider).strip() if provider else None)
  meta["uploaded_rag_documents"] = uploaded_docs
  meta["citations"] = citations
  meta["podcast_script"] = podcast_script
  meta["thinking"] = thinking
  meta["updated_at"] = _now_utc().isoformat()

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("UPDATE ai_requests SET prompt=%s, rag_query=%s WHERE id=%s", (user_request, _safe_json(meta), int(row.get("request_id") or 0)))
      cur.execute("UPDATE ai_decisions SET ai_suggestion=%s, decision_status='DRAFT' WHERE id=%s", (out_text, did))
    conn.commit()

  return {"ok": True, "text": out_text, "citations": citations, "podcast_script": podcast_script, "thinking": thinking, "meta": meta}


@router.post("/principal/decisions/{decision_id}/regenerate_stream")
async def regenerate_principal_decision_stream(
  decision_id: int,
  payload: PrincipalDecisionRegenerateBody,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection
  from app.services.principal_deeptutor_agent import generate_principal_content_deeptutor_stream

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT d.id AS decision_id, d.ai_request_id AS request_id, r.user_id, r.rag_query, r.prompt
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None

  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  if int(row.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")

  meta = _parse_json(row.get("rag_query"))
  if not isinstance(meta, dict):
    meta = {}

  stored_doc_ids = [str(x or "").strip() for x in (meta.get("doc_ids") or []) if str(x or "").strip()]
  stored_work_ids = [int(x) for x in (meta.get("work_ids") or []) if int(x or 0) > 0]

  doc_ids = [str(x or "").strip() for x in (payload.doc_ids or stored_doc_ids) if str(x or "").strip()]
  work_ids = [int(x) for x in (payload.work_ids or stored_work_ids) if int(x or 0) > 0]

  user_request = (payload.user_request if payload.user_request is not None else meta.get("user_request") or row.get("prompt") or "").strip()
  if not user_request:
    raise HTTPException(status_code=400, detail="missing_user_request")

  preset_id = (payload.preset_id if payload.preset_id is not None else meta.get("preset_id") or None)
  mode = (payload.mode if payload.mode is not None else meta.get("mode") or None)
  custom_prompt = (payload.custom_prompt if payload.custom_prompt is not None else meta.get("custom_prompt") or None)
  use_rag = bool(payload.use_rag) if payload.use_rag is not None else bool(meta.get("use_rag", True))

  if mode and str(mode).strip().lower() == "preset":
    custom_prompt = None
  if mode and str(mode).strip().lower() == "custom":
    preset_id = None

  use_web = bool(payload.use_web) if payload.use_web is not None else bool(meta.get("use_web", False))
  deep_research = bool(payload.deep_research) if payload.deep_research is not None else bool(meta.get("deep_research", False))
  web_provider = (payload.web_provider if payload.web_provider is not None else meta.get("web_provider") or None)
  make_podcast = bool(payload.make_podcast) if payload.make_podcast is not None else bool(meta.get("make_podcast", False))
  uploaded_docs = payload.uploaded_rag_documents if payload.uploaded_rag_documents is not None else (meta.get("uploaded_rag_documents") or [])
  if not isinstance(uploaded_docs, list):
    uploaded_docs = []

  async def event_stream():
    import json as _json

    def _sse(event: str, data_obj) -> bytes:
      data_str = _json.dumps(data_obj, ensure_ascii=False)
      return f"event: {event}\ndata: {data_str}\n\n".encode("utf-8")

    def _append_run_event(event: str, *, stage: str | None = None, message: str | None = None, data: dict | None = None):
      evs = meta.get("run_events")
      if not isinstance(evs, list):
        evs = []
      seq = int(meta.get("run_seq") or 0) + 1
      meta["run_seq"] = seq
      payload = {"seq": seq, "ts": _now_utc().isoformat(), "event": str(event or "")}
      if stage is not None:
        payload["stage"] = str(stage or "")
      if message is not None:
        payload["message"] = str(message or "")
      if data and isinstance(data, dict):
        safe = {}
        for k, v in data.items():
          if k in ("type", "stage", "message"):
            continue
          if isinstance(v, (str, int, float, bool)) or v is None:
            safe[k] = v
        if safe:
          payload["data"] = safe
      evs.append(payload)
      if len(evs) > 5000:
        evs = evs[-5000:]
      meta["run_events"] = evs

    def _update_run_state(status: str, *, stage: str | None = None):
      meta["run_status"] = str(status or "").strip() or None
      meta["run_stage"] = str(stage or "").strip() or None
      meta["run_last_heartbeat_at"] = _now_utc().isoformat()
      meta["updated_at"] = meta["run_last_heartbeat_at"]

    def _flush_meta():
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute("UPDATE ai_requests SET rag_query=%s WHERE id=%s", (_safe_json(meta), int(row.get("request_id") or 0)))
        conn.commit()

    try:
      _update_run_state("running", stage="Bắt đầu")
      _append_run_event("start", stage="Bắt đầu", message="Bắt đầu chạy phiên.")
      _flush_meta()
      async for item in generate_principal_content_deeptutor_stream(
        doc_ids=doc_ids,
        work_ids=work_ids,
        user_request=user_request,
        preset_id=(str(preset_id).strip() if preset_id else None),
        custom_prompt=(str(custom_prompt).strip() if custom_prompt else None),
        use_rag=use_rag,
        use_web=use_web,
        deep_research=deep_research,
        web_provider=(str(web_provider).strip() if web_provider else None),
        make_podcast=make_podcast,
        uploaded_rag_documents=uploaded_docs,
        model=((payload.model if payload.model is not None else meta.get("model")) or None),
        provider=((payload.provider if payload.provider is not None else meta.get("provider")) or None),
      ):
        t = str(item.get("type") or "")
        if t == "progress":
          _update_run_state("running", stage=str(item.get("stage") or "").strip() or None)
          _append_run_event("progress", stage=str(item.get("stage") or ""), message=str(item.get("message") or ""), data=item)
          _flush_meta()
          yield _sse("progress", item)
          continue
        if t == "heartbeat":
          _update_run_state(str(meta.get("run_status") or "running"), stage=str(meta.get("run_stage") or "") or None)
          _flush_meta()
          yield _sse("heartbeat", {"ok": True, "ts": meta.get("run_last_heartbeat_at")})
          continue
        if t == "final":
          res = item.get("result") if isinstance(item.get("result"), dict) else {}
          if bool(res.get("need_user_input")):
            questions = res.get("questions") if isinstance(res.get("questions"), list) else []
            meta["pending_questions"] = questions
            meta["ideagen"] = res.get("ideagen") or ""
            meta["thinking"] = str(res.get("thinking") or "").strip()
            _update_run_state("waiting_input", stage="Cần xác nhận")
            _append_run_event("need_input", stage="Cần xác nhận", message="Cần bạn trả lời để tiếp tục.", data={"questions": questions})
            with get_db_connection() as conn:
              with conn.cursor() as cur:
                cur.execute("UPDATE ai_requests SET prompt=%s, rag_query=%s WHERE id=%s", (user_request, _safe_json(meta), int(row.get("request_id") or 0)))
              conn.commit()
            yield _sse("need_input", {"questions": questions, "ideagen": res.get("ideagen") or "", "thinking": res.get("thinking") or ""})
            return
          out_text = str(res.get("text") or "").strip()
          citations = res.get("citations") if isinstance(res.get("citations"), dict) else {}
          podcast_script = str(res.get("podcast_script") or "").strip()
          thinking = str(res.get("thinking") or "").strip()

          meta["doc_ids"] = doc_ids
          meta["work_ids"] = work_ids
          meta["docs_snapshot"] = _fetch_ioffice_docs_snapshot(doc_ids) if doc_ids else (meta.get("docs_snapshot") or [])
          meta["preset_id"] = (str(preset_id).strip() if preset_id else None)
          meta["mode"] = (str(mode).strip() if mode else ("custom" if (custom_prompt or "").strip() else "preset"))
          meta["custom_prompt"] = (str(custom_prompt).strip() if custom_prompt else None)
          meta["user_request"] = user_request
          meta["use_rag"] = use_rag
          meta["use_web"] = use_web
          meta["deep_research"] = deep_research
          meta["web_provider"] = (str(web_provider).strip() if web_provider else None)
          meta["make_podcast"] = make_podcast
          meta["uploaded_rag_documents"] = uploaded_docs
          meta["citations"] = citations
          meta["podcast_script"] = podcast_script
          meta["thinking"] = thinking
          _update_run_state("done", stage="Hoàn tất")
          _append_run_event("final", stage="Hoàn tất", message="Đã tạo nội dung.", data={"citations": len(citations), "podcast_len": len(podcast_script)})

          with get_db_connection() as conn:
            with conn.cursor() as cur:
              cur.execute("UPDATE ai_requests SET prompt=%s, rag_query=%s WHERE id=%s", (user_request, _safe_json(meta), int(row.get("request_id") or 0)))
              cur.execute("UPDATE ai_decisions SET ai_suggestion=%s, decision_status='DRAFT' WHERE id=%s", (out_text, did))
            conn.commit()

          yield _sse("final", {"ok": True, "text": out_text, "citations": citations, "podcast_script": podcast_script, "thinking": thinking, "meta": meta})
    except Exception as e:
      _update_run_state("error", stage=str(meta.get("run_stage") or "") or None)
      _append_run_event("error", stage=str(meta.get("run_stage") or ""), message=str(e))
      try:
        _flush_meta()
      except Exception:
        pass
      yield _sse("error", {"ok": False, "message": str(e)})

  return StreamingResponse(
    event_stream(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
  )


@router.post("/principal/decisions/{decision_id}/run")
async def start_principal_decision_run(
  decision_id: int,
  payload: PrincipalDecisionRegenerateBody,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  did = int(decision_id or 0)
  if did < 1:
    raise HTTPException(status_code=400, detail="invalid_decision_id")

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        SELECT d.id AS decision_id, d.ai_request_id AS request_id, r.user_id, r.rag_query, r.prompt
        FROM ai_decisions d
        JOIN ai_requests r ON r.id=d.ai_request_id
        WHERE d.id=%s
        LIMIT 1
        """,
        (did,),
      )
      row = cur.fetchone() or None

  if not row:
    raise HTTPException(status_code=404, detail="not_found")
  if int(row.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")

  meta = _parse_json(row.get("rag_query"))
  if not isinstance(meta, dict):
    meta = {}

  existing_run_id = str(meta.get("run_id") or "").strip()
  if existing_run_id and str(meta.get("run_status") or "").strip() == "running" and existing_run_id in _RUNS:
    return {"ok": True, "run_id": existing_run_id}

  stored_doc_ids = [str(x or "").strip() for x in (meta.get("doc_ids") or []) if str(x or "").strip()]
  stored_work_ids = [int(x) for x in (meta.get("work_ids") or []) if int(x or 0) > 0]

  doc_ids = [str(x or "").strip() for x in (payload.doc_ids or stored_doc_ids) if str(x or "").strip()]
  work_ids = [int(x) for x in (payload.work_ids or stored_work_ids) if int(x or 0) > 0]

  user_request = (payload.user_request if payload.user_request is not None else meta.get("user_request") or row.get("prompt") or "").strip()
  if not user_request:
    raise HTTPException(status_code=400, detail="missing_user_request")

  preset_id = (payload.preset_id if payload.preset_id is not None else meta.get("preset_id") or None)
  mode = (payload.mode if payload.mode is not None else meta.get("mode") or None)
  custom_prompt = (payload.custom_prompt if payload.custom_prompt is not None else meta.get("custom_prompt") or None)
  use_rag = bool(payload.use_rag) if payload.use_rag is not None else bool(meta.get("use_rag", True))

  if mode and str(mode).strip().lower() == "preset":
    custom_prompt = None
  if mode and str(mode).strip().lower() == "custom":
    preset_id = None

  use_web = bool(payload.use_web) if payload.use_web is not None else bool(meta.get("use_web", False))
  deep_research = bool(payload.deep_research) if payload.deep_research is not None else bool(meta.get("deep_research", False))
  web_provider = (payload.web_provider if payload.web_provider is not None else meta.get("web_provider") or None)
  make_podcast = bool(payload.make_podcast) if payload.make_podcast is not None else bool(meta.get("make_podcast", False))
  uploaded_docs = payload.uploaded_rag_documents if payload.uploaded_rag_documents is not None else (meta.get("uploaded_rag_documents") or [])
  if not isinstance(uploaded_docs, list):
    uploaded_docs = []
  model = payload.model if getattr(payload, "model", None) is not None else (meta.get("model") or None)
  provider = payload.provider if getattr(payload, "provider", None) is not None else (meta.get("provider") or None)

  run_id = uuid.uuid4().hex
  ts = _now_utc().isoformat()
  meta["doc_ids"] = doc_ids
  meta["work_ids"] = work_ids
  meta["preset_id"] = (str(preset_id).strip() if preset_id else None)
  meta["mode"] = (str(mode).strip() if mode else ("custom" if (custom_prompt or "").strip() else "preset"))
  meta["custom_prompt"] = (str(custom_prompt).strip() if custom_prompt else None)
  meta["user_request"] = user_request
  meta["use_rag"] = use_rag
  meta["use_web"] = use_web
  meta["deep_research"] = deep_research
  meta["web_provider"] = (str(web_provider).strip() if web_provider else None)
  meta["make_podcast"] = make_podcast
  meta["uploaded_rag_documents"] = uploaded_docs
  meta["model"] = (str(model).strip() if model else None)
  meta["provider"] = (str(provider).strip() if provider else None)
  meta["run_id"] = run_id
  meta["run_seq"] = 0
  meta["run_events"] = [{"seq": 1, "ts": ts, "event": "start", "stage": "Bắt đầu", "message": "Bắt đầu chạy phiên."}]
  meta["run_seq"] = 1
  meta["run_status"] = "running"
  meta["run_stage"] = "Bắt đầu"
  meta["run_last_heartbeat_at"] = ts
  meta["run_started_at"] = ts
  meta["run_params"] = {
    "doc_ids": doc_ids,
    "work_ids": work_ids,
    "user_request": user_request,
    "preset_id": (str(preset_id).strip() if preset_id else None),
    "mode": (str(mode).strip() if mode else None),
    "custom_prompt": (str(custom_prompt).strip() if custom_prompt else None),
    "use_rag": use_rag,
    "use_web": use_web,
    "deep_research": deep_research,
    "web_provider": (str(web_provider).strip() if web_provider else None),
    "make_podcast": make_podcast,
    "uploaded_rag_documents": uploaded_docs,
    "model": (str(model).strip() if model else None),
    "provider": (str(provider).strip() if provider else None),
  }
  meta["updated_at"] = ts

  req_id = int(row.get("request_id") or 0)
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("UPDATE ai_requests SET prompt=%s, rag_query=%s WHERE id=%s", (user_request, _safe_json(meta), req_id))
    conn.commit()

  async def _push(event: str, payload_obj: dict):
    st = _RUNS.get(run_id)
    if not st:
      return
    dead: list[asyncio.Queue] = []
    for q in list(st.get("queues") or []):
      try:
        q.put_nowait({"event": event, "data": payload_obj})
      except Exception:
        dead.append(q)
    for q in dead:
      try:
        st.get("queues").discard(q)
      except Exception:
        pass

  def _db_update(new_meta: dict, *, prompt_val: str | None = None, suggestion: str | None = None):
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        if prompt_val is not None:
          cur.execute("UPDATE ai_requests SET prompt=%s, rag_query=%s WHERE id=%s", (prompt_val, _safe_json(new_meta), req_id))
        else:
          cur.execute("UPDATE ai_requests SET rag_query=%s WHERE id=%s", (_safe_json(new_meta), req_id))
        if suggestion is not None:
          cur.execute("UPDATE ai_decisions SET ai_suggestion=%s, decision_status='DRAFT' WHERE id=%s", (suggestion, did))
      conn.commit()

  async def _runner():
    from app.services.principal_deeptutor_agent import generate_principal_content_deeptutor_stream

    def _append_event(event: str, *, stage: str | None = None, message: str | None = None, data: dict | None = None):
      seq = int(meta.get("run_seq") or 0) + 1
      meta["run_seq"] = seq
      evs = meta.get("run_events")
      if not isinstance(evs, list):
        evs = []
      out = {"seq": seq, "ts": _now_utc().isoformat(), "event": str(event or "")}
      if stage is not None:
        out["stage"] = str(stage or "")
      if message is not None:
        out["message"] = str(message or "")
      if data and isinstance(data, dict):
        safe = {}
        for k, v in data.items():
          if isinstance(v, (str, int, float, bool)) or v is None:
            safe[k] = v
            continue
          if isinstance(v, list):
            xs = [str(x or "").strip() for x in v if str(x or "").strip()]
            if xs:
              safe[k] = xs[:12]
            continue
          if isinstance(v, dict):
            safe2 = {}
            for k2, v2 in v.items():
              if isinstance(v2, (str, int, float, bool)) or v2 is None:
                safe2[str(k2)] = v2
            if safe2:
              safe[k] = safe2
        if safe:
          out["data"] = safe
      evs.append(out)
      if len(evs) > 5000:
        evs = evs[-5000:]
      meta["run_events"] = evs
      meta["run_last_heartbeat_at"] = out["ts"]
      meta["updated_at"] = out["ts"]
      return out

    async def _flush(*, prompt_val: str | None = None, suggestion: str | None = None):
      await asyncio.to_thread(_db_update, dict(meta), prompt_val=prompt_val, suggestion=suggestion)

    try:
      await _push("start", {"run_id": run_id, "ts": ts})
      async for item in generate_principal_content_deeptutor_stream(
        doc_ids=doc_ids,
        work_ids=work_ids,
        user_request=user_request,
        preset_id=(str(preset_id).strip() if preset_id else None),
        custom_prompt=(str(custom_prompt).strip() if custom_prompt else None),
        use_rag=use_rag,
        use_web=use_web,
        deep_research=deep_research,
        web_provider=(str(web_provider).strip() if web_provider else None),
        make_podcast=make_podcast,
        uploaded_rag_documents=uploaded_docs,
        model=((payload.model if payload.model is not None else meta.get("model")) or None),
        provider=((payload.provider if payload.provider is not None else meta.get("provider")) or None),
      ):
        t2 = str(item.get("type") or "")
        if t2 == "heartbeat":
          meta["run_status"] = "running"
          meta["run_stage"] = str(meta.get("run_stage") or "") or "Đang chạy"
          hb = _append_event("heartbeat", stage=str(meta.get("run_stage") or ""), message="")
          await _flush()
          await _push("heartbeat", hb)
          continue
        if t2 == "progress":
          stage = str(item.get("stage") or "").strip()
          message = str(item.get("message") or "").strip()
          meta["run_status"] = "running"
          meta["run_stage"] = stage or None
          ev = _append_event("progress", stage=stage, message=message)
          await _flush()
          await _push("progress", ev)
          continue
        if t2 == "final":
          res = item.get("result") if isinstance(item.get("result"), dict) else {}
          if bool(res.get("need_user_input")):
            questions = res.get("questions") if isinstance(res.get("questions"), list) else []
            meta["pending_questions"] = questions
            meta["ideagen"] = res.get("ideagen") or ""
            meta["thinking"] = str(res.get("thinking") or "").strip()
            meta["run_status"] = "waiting_input"
            meta["run_stage"] = "Cần xác nhận"
            ev = _append_event(
              "need_input",
              stage="Cần xác nhận",
              message="Cần bạn trả lời để tiếp tục.",
              data={"questions": questions, "ideagen_len": len(str(meta.get("ideagen") or "")), "thinking_len": len(str(meta.get("thinking") or ""))},
            )
            await _flush(prompt_val=user_request)
            await _push("need_input", {"ok": True, "event": ev, "questions": questions, "ideagen": meta.get("ideagen") or "", "thinking": meta.get("thinking") or ""})
            return
          out_text = str(res.get("text") or "").strip()
          citations = res.get("citations") if isinstance(res.get("citations"), dict) else {}
          podcast_script = str(res.get("podcast_script") or "").strip()
          thinking = str(res.get("thinking") or "").strip()
          meta["citations"] = citations
          meta["podcast_script"] = podcast_script
          meta["thinking"] = thinking
          meta["run_status"] = "done"
          meta["run_stage"] = "Hoàn tất"
          ev = _append_event("final", stage="Hoàn tất", message="Đã tạo nội dung.", data={"citations": len(citations), "podcast_len": len(podcast_script)})
          await _flush(prompt_val=user_request, suggestion=out_text)
          await _push("final", {"ok": True, "event": ev, "text": out_text, "citations": citations, "podcast_script": podcast_script, "thinking": thinking})
          return
    except Exception as e:
      meta["run_status"] = "error"
      meta["run_stage"] = str(meta.get("run_stage") or "") or "Lỗi"
      ev = _append_event("error", stage=str(meta.get("run_stage") or ""), message=str(e))
      try:
        await _flush()
      except Exception:
        pass
      await _push("error", {"ok": False, "event": ev, "message": str(e)})
    finally:
      _RUNS.pop(run_id, None)

  _RUNS[run_id] = {"decision_id": did, "request_id": req_id, "user_id": uid, "queues": set(), "task": asyncio.create_task(_runner())}
  return {"ok": True, "run_id": run_id}


@router.get("/principal/decisions/runs/{run_id}/stream")
async def stream_principal_decision_run(
  run_id: str,
  after: int | None = None,
  x_user_id: str | None = Header(default=None),
):
  from app.db import get_db_connection

  uid = _user_id(x_user_id)
  rid = str(run_id or "").strip()
  if not rid:
    raise HTTPException(status_code=400, detail="invalid_run_id")
  after_seq = int(after or 0)
  if after_seq < 0:
    after_seq = 0

  sql = """
    SELECT
      d.id AS decision_id,
      d.ai_request_id AS request_id,
      r.user_id,
      r.rag_query
    FROM ai_decisions d
    JOIN ai_requests r ON r.id=d.ai_request_id
    WHERE r.user_id=%s AND JSON_UNQUOTE(JSON_EXTRACT(r.rag_query, '$.run_id'))=%s
    LIMIT 1
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (uid, rid))
      row = cur.fetchone() or None
  if not row:
    raise HTTPException(status_code=404, detail="not_found")

  meta = _parse_json(row.get("rag_query"))
  if not isinstance(meta, dict):
    meta = {}
  st = _RUNS.get(rid)
  if st:
    q: asyncio.Queue = asyncio.Queue()
    st.get("queues").add(q)
    async def _live_stream():
      import json as _json
      def _sse(event: str, data_obj) -> bytes:
        data_str = _json.dumps(data_obj, ensure_ascii=False)
        return f"event: {event}\ndata: {data_str}\n\n".encode("utf-8")
      try:
        while True:
          msg = await q.get()
          event = str((msg or {}).get("event") or "message")
          data = (msg or {}).get("data")
          yield _sse(event, data)
          if event in ("final", "need_input", "error"):
            return
      finally:
        try:
          st.get("queues").discard(q)
        except Exception:
          pass
    return StreamingResponse(_live_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

  evs = meta.get("run_events")
  if not isinstance(evs, list):
    evs = []

  async def event_stream():
    import json as _json

    def _sse(event: str, data_obj) -> bytes:
      data_str = _json.dumps(data_obj, ensure_ascii=False)
      return f"event: {event}\ndata: {data_str}\n\n".encode("utf-8")

    for ev in evs:
      try:
        seq = int((ev or {}).get("seq") or 0)
      except Exception:
        seq = 0
      if seq <= after_seq:
        continue
      yield _sse(str((ev or {}).get("event") or "progress"), ev)

    st = _RUNS.get(rid)
    if not st:
      return
    q: asyncio.Queue = asyncio.Queue()
    st.get("queues").add(q)
    try:
      while True:
        msg = await q.get()
        event = str((msg or {}).get("event") or "message")
        data = (msg or {}).get("data")
        yield _sse(event, data)
        if event in ("final", "need_input", "error"):
          return
    finally:
      try:
        st.get("queues").discard(q)
      except Exception:
        pass

  return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/principal/decisions/runs/{run_id}/cancel")
async def cancel_principal_decision_run(
  run_id: str,
  x_user_id: str | None = Header(default=None),
):
  uid = _user_id(x_user_id)
  rid = str(run_id or "").strip()
  st = _RUNS.get(rid)
  if not st:
    return {"ok": True}
  if int(st.get("user_id") or 0) != uid:
    raise HTTPException(status_code=403, detail="forbidden")
  task = st.get("task")
  if task:
    try:
      task.cancel()
    except Exception:
      pass
  _RUNS.pop(rid, None)
  return {"ok": True}


@router.post("/suggest")
def suggest():
  return {"suggestion": None}
