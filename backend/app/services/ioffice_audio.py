import base64
import json
import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from app.db import get_db_connection
from app.services.db_keyring import get_ring
from app.services.ioffice_audio_schema import ensure_ioffice_audio_columns
from app.services.tts_client import tts_available, tts_speak
from app.services.edge_tts_client import edge_tts_mp3
from app.services.sapi_tts_client import sapi_tts_wav
from app.services.gtts_client import gtts_mp3
from utils import FILES_ROOT, ensure_dir, make_safe_relative_from_any


def _sha256_hex(text: str) -> str:
  import hashlib

  return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _audio_profile() -> str:
  provider = (os.getenv("EDUAI_IOFFICE_AUDIO_PROVIDER") or "auto").strip().lower()
  speed = (os.getenv("EDUAI_IOFFICE_TTS_SPEED") or "1.5").strip()
  if provider == "google":
    voice = (os.getenv("EDUAI_IOFFICE_TTS_GOOGLE_VOICE") or "vi-VN-Standard-A").strip()
    return f"google|voice={voice}|speed={speed}|v2"
  if provider == "edge":
    voice = (os.getenv("EDUAI_IOFFICE_TTS_EDGE_VOICE") or "vi-VN-HoaiMyNeural").strip()
    return f"edge|voice={voice}|speed={speed}|v2"
  if provider == "gtts":
    lang = (os.getenv("EDUAI_IOFFICE_TTS_GTTS_LANG") or "vi").strip()
    tld = (os.getenv("EDUAI_IOFFICE_TTS_GTTS_TLD") or "com.vn").strip()
    return f"gtts|lang={lang}|tld={tld}|speed={speed}|v2"
  if provider == "sapi":
    hint = (os.getenv("EDUAI_IOFFICE_TTS_SAPI_VOICE_HINT") or "hoaimy").strip()
    return f"sapi|hint={hint}|speed={speed}|v2"
  if provider == "openai":
    voice = (os.getenv("EDUAI_IOFFICE_TTS_OPENAI_VOICE") or os.getenv("EDUAI_TTS_VOICE") or "nova").strip()
    model = (os.getenv("EDUAI_IOFFICE_TTS_OPENAI_MODEL") or os.getenv("EDUAI_TTS_MODEL") or "gpt-4o-mini-tts").strip()
    return f"openai|model={model}|voice={voice}|speed={speed}|v2"
  return f"auto|speed={speed}|order=google,edge,gtts,sapi,openai|v2"


def _prepare_tts_text(text: str) -> str:
  t = (text or "").strip()
  if not t:
    return ""
  import re

  t = t.replace("\r\n", "\n").replace("\r", "\n")
  t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
  t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", t)
  t = re.sub(r"`([^`\n]+)`", r"\1", t)
  out_lines: list[str] = []
  for ln in t.split("\n"):
    s = ln.strip()
    if not s:
      continue
    if re.match(r"^\|?[\s\-:|]+\|?$", s) and "|" in s:
      continue
    if s.startswith("#"):
      s = s.lstrip("#").strip()
    s = re.sub(r"^[\-\*\u2022]\s+", "", s)
    s = s.replace("|", " ; ")
    s = re.sub(r"\s+", " ", s).strip()
    if s:
      out_lines.append(s)
  return "\n".join(out_lines).strip()


def _get_google_tts_key() -> str:
  k = (get_ring("AI_GOOGLE_TTS_API_KEY").pick() or "").strip()
  if k:
    return k
  k2 = (get_ring("AI_GOOGLE_API_KEY").pick() or "").strip()
  if k2:
    return k2
  return (get_ring("AI_GEMINI_API_KEY").pick() or "").strip()


def _tts_google_mp3(text: str) -> bytes:
  api_key = _get_google_tts_key()
  if not api_key:
    raise RuntimeError("missing_google_tts_api_key")

  voice = (os.getenv("EDUAI_IOFFICE_TTS_GOOGLE_VOICE") or "vi-VN-Standard-A").strip()
  speed = float((os.getenv("EDUAI_IOFFICE_TTS_SPEED") or "1.5").strip())
  if speed < 0.25:
    speed = 0.25
  if speed > 4.0:
    speed = 4.0

  t = (text or "").strip()
  if not t:
    raise RuntimeError("empty_text")

  max_chars = int(os.getenv("EDUAI_IOFFICE_TTS_MAX_CHARS") or "4500")
  if max_chars < 200:
    max_chars = 200
  if len(t) > max_chars:
    t = t[:max_chars]

  url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={urllib.parse.quote(api_key)}"
  body = {
    "input": {"text": t},
    "voice": {"languageCode": "vi-VN", "name": voice},
    "audioConfig": {"audioEncoding": "MP3", "speakingRate": speed},
  }
  data = json.dumps(body).encode("utf-8")
  req = urllib.request.Request(url=url, data=data, method="POST", headers={"Content-Type": "application/json"})
  try:
    with urllib.request.urlopen(req, timeout=120) as resp:
      raw = resp.read().decode("utf-8", errors="replace")
  except Exception as e:
    raise RuntimeError(f"google_tts_error:{e}") from e
  j = json.loads(raw) if raw else {}
  b64 = j.get("audioContent") or ""
  if not b64:
    raise RuntimeError("google_tts_empty_audio")
  return base64.b64decode(b64)


def _tts_openai_mp3(text: str) -> bytes:
  if not tts_available():
    raise RuntimeError(
      "TTS không khả dụng (tts_unavailable). "
      "Hãy cấu hình EDUAI_TTS_PROVIDER=openai và thêm AI_OPENAI_API_KEY trong Cấu hình hệ thống."
    )
  voice = (os.getenv("EDUAI_IOFFICE_TTS_OPENAI_VOICE") or os.getenv("EDUAI_TTS_VOICE") or "nova").strip()
  model = (os.getenv("EDUAI_IOFFICE_TTS_OPENAI_MODEL") or os.getenv("EDUAI_TTS_MODEL") or "gpt-4o-mini-tts").strip()
  speed = float((os.getenv("EDUAI_IOFFICE_TTS_SPEED") or "1.5").strip())
  audio, _mime, _fmt = tts_speak(text, voice=voice, model=model, fmt="mp3", speed=speed)
  if not audio:
    raise RuntimeError("tts_empty_audio")
  return audio


def _tts_audio(text: str) -> tuple[bytes, str]:
  provider = (os.getenv("EDUAI_IOFFICE_AUDIO_PROVIDER") or "auto").strip().lower()
  if provider == "openai":
    return _tts_openai_mp3(text), "mp3"
  if provider == "edge":
    return edge_tts_mp3(text), "mp3"
  if provider == "gtts":
    return gtts_mp3(text), "mp3"
  if provider == "google":
    return _tts_google_mp3(text), "mp3"
  if provider == "sapi":
    return sapi_tts_wav(text), "wav"
  if provider == "auto":
    tried: list[str] = []
    errors: dict[str, str] = {}

    if _get_google_tts_key():
      tried.append("google")
      try:
        return _tts_google_mp3(text), "mp3"
      except Exception as e:
        errors["google"] = str(e)
        pass
    else:
      tried.append("google(no_key)")

    tried.append("edge")
    try:
      return edge_tts_mp3(text), "mp3"
    except Exception as e:
      errors["edge"] = str(e)
      pass

    tried.append("gtts")
    try:
      return gtts_mp3(text), "mp3"
    except Exception as e:
      errors["gtts"] = str(e)
      pass

    tried.append("sapi")
    try:
      return sapi_tts_wav(text), "wav"
    except Exception as e:
      errors["sapi"] = str(e)
      pass

    if tts_available():
      tried.append("openai")
      try:
        return _tts_openai_mp3(text), "mp3"
      except Exception as e:
        errors["openai"] = str(e)
        pass
    else:
      tried.append("openai(not_configured)")

    detail = "; ".join([f"{k}={v}" for k, v in errors.items() if v]) if errors else ""
    raise RuntimeError(
      "TTS không khả dụng (tts_unavailable). "
      "Hãy cấu hình EDUAI_TTS_PROVIDER=openai và thêm AI_OPENAI_API_KEY trong Cấu hình hệ thống, "
      "hoặc cài/thiết lập 1 trong các lựa chọn local (edge-tts, gTTS, SAPI). "
      f"Đã thử: {', '.join(tried)}"
      + (f". Chi tiết: {detail}" if detail else "")
    )
  raise RuntimeError(f"unsupported_audio_provider:{provider}")



def _audio_rel_path(doc_id: str, audio_hash: str, ext: str) -> str:
  safe_id = "".join([c for c in str(doc_id or "") if c.isalnum() or c in ("-", "_")])[:64] or "doc"
  e = (ext or "mp3").lstrip(".").lower()
  if e not in ("mp3", "wav"):
    e = "mp3"
  return f"audio/summary_{safe_id}_{audio_hash[:16]}.{e}"


def _normalize_existing_path(p: str) -> str:
  s = make_safe_relative_from_any(p or "")
  s = s.replace("\\", "/").lstrip("/")
  return s


def _get_doc_by_ioffice_id(doc_id: str) -> dict | None:
  did = (doc_id or "").strip()
  if not did:
    return None
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM ioffice_documents WHERE ioffice_doc_id=%s", (did,))
      return cur.fetchone()


def request_summary_audio(doc_id: str) -> dict:
  ensure_ioffice_audio_columns()
  doc = _get_doc_by_ioffice_id(doc_id)
  if not doc:
    raise RuntimeError("not_found")
  summary_raw = (doc.get("summary_text") or doc.get("ai_summary") or "").strip()
  summary = _prepare_tts_text(summary_raw)
  if not summary:
    raise RuntimeError("missing_summary_text")

  audio_hash = _sha256_hex(summary + "\n" + _audio_profile())
  audio_status = (doc.get("audio_status") or "").strip().upper()
  audio_path = _normalize_existing_path(doc.get("audio_path") or "")
  prev_hash = (doc.get("audio_hash") or "").strip()

  if audio_status == "READY" and prev_hash == audio_hash and audio_path:
    full = (FILES_ROOT / audio_path).resolve()
    root = FILES_ROOT.resolve()
    if str(full).startswith(str(root)) and full.exists():
      return {"ok": True, "status": "READY", "audio_path": audio_path}

  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
        """
        UPDATE ioffice_documents
        SET audio_status='PROCESSING',
            audio_error=NULL,
            audio_updated_at=UTC_TIMESTAMP(),
            audio_hash=%s
        WHERE ioffice_doc_id=%s
        """,
        (audio_hash, str(doc_id)),
      )

  def _task():
    try:
      out_dir = (FILES_ROOT / "audio").resolve()
      ensure_dir(out_dir)
      root = FILES_ROOT.resolve()
      audio, ext = _tts_audio(summary)
      rel = _audio_rel_path(str(doc_id), audio_hash, ext)
      full = (FILES_ROOT / rel).resolve()
      if not str(full).startswith(str(root)):
        raise RuntimeError("bad_audio_path")
      full.parent.mkdir(parents=True, exist_ok=True)
      full.write_bytes(audio or b"")
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(
            """
            UPDATE ioffice_documents
            SET audio_status='READY',
                audio_path=%s,
                audio_error=NULL,
                audio_updated_at=UTC_TIMESTAMP()
            WHERE ioffice_doc_id=%s
            """,
            (rel, str(doc_id)),
          )
    except Exception as e:
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute(
            """
            UPDATE ioffice_documents
            SET audio_status='FAILED',
                audio_error=%s,
                audio_updated_at=UTC_TIMESTAMP()
            WHERE ioffice_doc_id=%s
            """,
            (str(e), str(doc_id)),
          )

  threading.Thread(target=_task, daemon=True).start()
  return {"ok": True, "status": "PROCESSING"}


def get_audio_status(doc_id: str) -> dict:
  ensure_ioffice_audio_columns()
  doc = _get_doc_by_ioffice_id(doc_id)
  if not doc:
    raise RuntimeError("not_found")
  return {
    "ok": True,
    "audio_status": (doc.get("audio_status") or "").strip() or "PENDING",
    "audio_path": _normalize_existing_path(doc.get("audio_path") or ""),
    "audio_error": (doc.get("audio_error") or "").strip(),
    "audio_updated_at": (doc.get("audio_updated_at") or ""),
  }
