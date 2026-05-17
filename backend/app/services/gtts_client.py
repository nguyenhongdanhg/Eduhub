import io
import os


def gtts_mp3(text: str) -> bytes:
  try:
    from gtts import gTTS
  except Exception as e:
    raise RuntimeError(f"missing_gtts:{e}") from e

  t = (text or "").strip()
  if not t:
    raise RuntimeError("empty_text")

  max_chars = int(os.getenv("EDUAI_IOFFICE_TTS_MAX_CHARS") or "4500")
  if max_chars < 200:
    max_chars = 200
  if len(t) > max_chars:
    t = t[:max_chars]

  lang = (os.getenv("EDUAI_IOFFICE_TTS_GTTS_LANG") or "vi").strip().lower() or "vi"
  tld = (os.getenv("EDUAI_IOFFICE_TTS_GTTS_TLD") or "com.vn").strip().lower() or "com.vn"

  buf = io.BytesIO()
  try:
    gTTS(text=t, lang=lang, tld=tld, slow=False).write_to_fp(buf)
  except Exception as e:
    raise RuntimeError(f"gtts_error:{e}") from e
  return buf.getvalue() or b""

