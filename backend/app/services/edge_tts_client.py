import asyncio
import os
import tempfile


def _rate_str_from_speed(speed: float) -> str:
  try:
    s = float(speed)
  except Exception:
    s = 1.0
  if s < 0.25:
    s = 0.25
  if s > 3.0:
    s = 3.0
  pct = int(round((s - 1.0) * 100))
  if pct == 0:
    return "+0%"
  if pct > 0:
    return f"+{pct}%"
  return f"{pct}%"


def edge_tts_mp3(text: str, *, voice: str | None = None, speed: float | None = None) -> bytes:
  try:
    import edge_tts
  except Exception as e:
    raise RuntimeError(f"missing_edge_tts:{e}") from e

  t = (text or "").strip()
  if not t:
    raise RuntimeError("empty_text")

  max_chars = int(os.getenv("EDUAI_IOFFICE_TTS_MAX_CHARS") or "4500")
  if max_chars < 200:
    max_chars = 200
  if len(t) > max_chars:
    t = t[:max_chars]

  v = (voice or os.getenv("EDUAI_IOFFICE_TTS_EDGE_VOICE") or "vi-VN-HoaiMyNeural").strip()
  sp = speed
  if sp is None:
    try:
      sp = float((os.getenv("EDUAI_IOFFICE_TTS_SPEED") or "1.5").strip())
    except Exception:
      sp = 1.5
  rate = _rate_str_from_speed(float(sp))

  async def _run() -> bytes:
    comm = edge_tts.Communicate(t, v, rate=rate)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
      out_path = f.name
    try:
      await comm.save(out_path)
      with open(out_path, "rb") as rf:
        return rf.read()
    finally:
      try:
        __import__("os").unlink(out_path)
      except Exception:
        pass

  return asyncio.run(_run())

