import os
import tempfile


def sapi_tts_wav(text: str, *, voice_hint: str | None = None, speed: float | None = None) -> bytes:
  try:
    import pyttsx3
  except Exception as e:
    raise RuntimeError(f"missing_pyttsx3:{e}") from e

  t = (text or "").strip()
  if not t:
    raise RuntimeError("empty_text")

  max_chars = int(os.getenv("EDUAI_IOFFICE_TTS_MAX_CHARS") or "4500")
  if max_chars < 200:
    max_chars = 200
  if len(t) > max_chars:
    t = t[:max_chars]

  vhint = (voice_hint or os.getenv("EDUAI_IOFFICE_TTS_SAPI_VOICE_HINT") or "hoaimy").strip().lower()
  sp = speed
  if sp is None:
    try:
      sp = float((os.getenv("EDUAI_IOFFICE_TTS_SPEED") or "1.5").strip())
    except Exception:
      sp = 1.5
  if sp < 0.25:
    sp = 0.25
  if sp > 3.0:
    sp = 3.0

  engine = pyttsx3.init()
  try:
    voices = engine.getProperty("voices") or []
    def _voice_meta(v) -> tuple[str, str, str]:
      try:
        name = str(getattr(v, "name", "") or "")
      except Exception:
        name = ""
      try:
        vid = str(getattr(v, "id", "") or "")
      except Exception:
        vid = ""
      langs = ""
      try:
        raw_langs = getattr(v, "languages", None) or []
        parts = []
        for it in raw_langs:
          try:
            if isinstance(it, (bytes, bytearray)):
              parts.append(it.decode("utf-8", errors="ignore"))
            else:
              parts.append(str(it))
          except Exception:
            continue
        langs = " ".join(parts)
      except Exception:
        langs = ""
      return name, vid, langs

    def _score_voice(v) -> int:
      name, vid, langs = _voice_meta(v)
      s = " ".join([name, vid, langs]).lower()
      score = 0
      if "vi" in s or "vi-vn" in s or "vietnam" in s:
        score += 50
      if "hoaimy" in s or "hoài my" in s:
        score += 80
      if "female" in s or "woman" in s or "nu" in s or "nữ" in s:
        score += 10
      if vhint and vhint in s:
        score += 40
      if score == 0 and voices:
        score = 1
      return score

    chosen_id = None
    best = None
    best_score = -1
    for v in voices:
      try:
        sc = _score_voice(v)
        if sc > best_score:
          best_score = sc
          best = v
      except Exception:
        continue
    if best is not None:
      try:
        _name, _vid, _langs = _voice_meta(best)
        chosen_id = _vid or None
      except Exception:
        chosen_id = None
    if chosen_id:
      try:
        engine.setProperty("voice", chosen_id)
      except Exception:
        pass

    try:
      base_rate = int(engine.getProperty("rate") or 200)
    except Exception:
      base_rate = 200
    try:
      engine.setProperty("rate", int(round(base_rate * float(sp))))
    except Exception:
      pass

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
      out_path = f.name
    try:
      engine.save_to_file(t, out_path)
      engine.runAndWait()
      with open(out_path, "rb") as rf:
        return rf.read()
    finally:
      try:
        __import__("os").unlink(out_path)
      except Exception:
        pass
  finally:
    try:
      engine.stop()
    except Exception:
      pass
