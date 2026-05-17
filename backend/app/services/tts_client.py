import os
import urllib.error
import urllib.request

from app.services.db_keyring import get_ring, is_key_exhausted_error


def tts_available() -> bool:
  provider = (os.getenv("EDUAI_TTS_PROVIDER") or "").strip().lower()
  if provider != "openai":
    return False
  return True


def tts_speak(
  text: str,
  *,
  voice: str | None = None,
  model: str | None = None,
  fmt: str | None = None,
  speed: float | None = None,
) -> tuple[bytes, str, str]:
  provider = (os.getenv("EDUAI_TTS_PROVIDER") or "").strip().lower()
  if provider != "openai":
    raise RuntimeError("tts_provider_not_configured")

  ring = get_ring("AI_OPENAI_API_KEY")
  keys = ring.list_keys()
  if not keys:
    raise RuntimeError("OpenAI API key is required for TTS. Please add AI_OPENAI_API_KEY in system configuration.")

  base_url = "https://api.openai.com/v1"
  try:
    from app.services.llm_client import _get_db_config as _db

    base_url = (_db("AI_OPENAI_BASE_URL") or base_url).strip()
  except Exception:
    base_url = base_url
  base_url = base_url.rstrip("/")

  model = (model or os.getenv("EDUAI_TTS_MODEL") or "gpt-4o-mini-tts").strip()
  voice = (voice or os.getenv("EDUAI_TTS_VOICE") or "alloy").strip()
  fmt = (fmt or os.getenv("EDUAI_TTS_FORMAT") or "mp3").strip().lower()
  instructions = (os.getenv("EDUAI_TTS_INSTRUCTIONS") or "").strip() or "Đọc nội dung sau bằng tiếng Việt, giọng rõ ràng, tự nhiên."

  t = (text or "").strip()
  if not t:
    raise RuntimeError("empty_text")

  max_chars = int(os.getenv("EDUAI_TTS_MAX_CHARS") or "4000")
  if max_chars < 500:
    max_chars = 500
  if len(t) > max_chars:
    t = t[:max_chars]

  body = {
    "model": model,
    "voice": voice,
    "input": t,
    "format": fmt,
    "instructions": instructions,
  }
  try:
    if speed is not None:
      body["speed"] = float(speed)
    else:
      s = (os.getenv("EDUAI_TTS_SPEED") or "").strip()
      if s:
        body["speed"] = float(s)
  except Exception:
    pass
  data = __import__("json").dumps(body).encode("utf-8")
  last_err: Exception | None = None
  for _ in range(max(1, len(keys))):
    api_key = ring.pick() or ""
    if not api_key:
      break
    req = urllib.request.Request(
      url=f"{base_url}/audio/speech",
      data=data,
      method="POST",
      headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
      with urllib.request.urlopen(req, timeout=60) as resp:
        audio = resp.read()
      mime = "audio/mpeg" if fmt == "mp3" else "application/octet-stream"
      return audio or b"", mime, fmt
    except urllib.error.HTTPError as e:
      raw = e.read().decode("utf-8", errors="replace")
      err = RuntimeError(f"TTS HTTP {e.code}: {raw}")
      last_err = err
      if is_key_exhausted_error(err):
        ring.mark_bad(api_key, cooldown_seconds=120)
        continue
      raise err from e
    except Exception as e:
      last_err = e
      if is_key_exhausted_error(e):
        ring.mark_bad(api_key, cooldown_seconds=120)
        continue
      raise
  raise last_err or RuntimeError("missing_openai_api_key")
