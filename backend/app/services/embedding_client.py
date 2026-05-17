import json
import os
import urllib.error
import urllib.parse
import urllib.request
import threading

from app.db import get_db_connection
from app.services.db_keyring import get_ring, is_key_exhausted_error


def _get_db_config(key: str) -> str:
  try:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT conf_value FROM system_configs WHERE conf_key=%s", (str(key),))
        row = cur.fetchone()
        return str((row or {}).get("conf_value") or "").strip()
  except Exception:
    return ""


def _can_import_sentence_transformers() -> bool:
  try:
    import sentence_transformers  # noqa: F401

    return True
  except Exception:
    return False


def _get_ollama_base_url() -> str:
  return (os.getenv("EDUAI_OLLAMA_BASE_URL") or "http://127.0.0.1:11434").strip().rstrip("/")


def _ollama_available(timeout_sec: float = 0.25) -> bool:
  base = _get_ollama_base_url()
  try:
    req = urllib.request.Request(url=f"{base}/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
      raw = resp.read().decode("utf-8", errors="replace")
    if not raw:
      return False
    j = json.loads(raw)
    return isinstance(j, dict)
  except Exception:
    return False


def _embed_ollama(text: str, *, model: str | None = None) -> tuple[list[float], str]:
  base = _get_ollama_base_url()
  model_name = (model or os.getenv("EDUAI_OLLAMA_EMBED_MODEL") or "nomic-embed-text").strip()
  body = {"model": model_name, "prompt": text}
  data = json.dumps(body).encode("utf-8")
  req = urllib.request.Request(url=f"{base}/api/embeddings", data=data, method="POST", headers={"Content-Type": "application/json"})
  try:
    with urllib.request.urlopen(req, timeout=120) as resp:
      raw = resp.read().decode("utf-8", errors="replace")
      res = json.loads(raw) if raw else {}
  except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"Ollama Embedding HTTP {e.code}: {raw}") from e
  vec = res.get("embedding")
  if not isinstance(vec, list) or not vec:
    raise RuntimeError("empty_embedding")
  return [float(x) for x in vec], model_name


def _embed_gemini(text: str, *, model: str | None = None) -> tuple[list[float], str]:
  ring = get_ring("AI_GEMINI_API_KEY")
  keys = ring.list_keys()
  if not keys:
    raise RuntimeError("missing_gemini_api_key")
  base_url = (_get_db_config("AI_GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/")
  model_name = (model or _get_db_config("AI_GEMINI_EMBED_MODEL") or "text-embedding-004").strip()
  body = {"content": {"parts": [{"text": text}]}}
  data = json.dumps(body).encode("utf-8")
  last_err: Exception | None = None
  for _ in range(max(1, len(keys))):
    api_key = ring.pick() or ""
    if not api_key:
      break
    url = f"{base_url}/models/{urllib.parse.quote(model_name)}:embedContent?key={urllib.parse.quote(api_key)}"
    req = urllib.request.Request(url=url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
      with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        res = json.loads(raw) if raw else {}
      emb = (res.get("embedding") or {}).get("values")
      if not isinstance(emb, list) or not emb:
        raise RuntimeError("empty_embedding")
      return [float(x) for x in emb], model_name
    except urllib.error.HTTPError as e:
      raw = e.read().decode("utf-8", errors="replace")
      err = RuntimeError(f"Gemini Embedding HTTP {e.code}: {raw}")
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
  raise last_err or RuntimeError("missing_gemini_api_key")


def _select_provider(raw: str) -> str:
  p = str(raw or "").strip().lower()
  if not p:
    p = "auto"
  if p not in ("auto", "sentence_transformers", "openai", "ollama", "gemini"):
    p = "auto"
  if p == "sentence_transformers":
    return "sentence_transformers" if _can_import_sentence_transformers() else "auto"
  if p == "ollama":
    return "ollama" if _ollama_available() else "auto"
  if p == "gemini":
    return "gemini" if get_ring("AI_GEMINI_API_KEY").list_keys() else "auto"
  if p == "openai":
    return "openai" if get_ring("AI_OPENAI_API_KEY").list_keys() else "auto"
  if _can_import_sentence_transformers():
    return "sentence_transformers"
  if _ollama_available():
    return "ollama"
  if get_ring("AI_OPENAI_API_KEY").list_keys():
    return "openai"
  if get_ring("AI_GEMINI_API_KEY").list_keys():
    return "gemini"
  return "none"


def embedding_available() -> bool:
  provider = _select_provider(os.getenv("EDUAI_EMBED_PROVIDER") or "")
  if provider == "sentence_transformers":
    return True
  if provider == "ollama":
    return True
  if provider == "openai":
    return bool(get_ring("AI_OPENAI_API_KEY").list_keys())
  if provider == "gemini":
    return bool(get_ring("AI_GEMINI_API_KEY").list_keys())
  return False


def embedding_runtime_info() -> dict:
  provider = _select_provider(os.getenv("EDUAI_EMBED_PROVIDER") or "")
  if provider == "sentence_transformers":
    model_name = (os.getenv("EDUAI_LOCAL_EMBED_MODEL") or os.getenv("EDUAI_OPENAI_EMBED_MODEL") or "intfloat/multilingual-e5-base").strip()
    device = _pick_local_device()
    diag: dict = {}
    try:
      import torch

      cuda_ok = bool(torch.cuda.is_available())
      diag = {
        "torch": getattr(torch, "__version__", ""),
        "torch_cuda": getattr(getattr(torch, "version", None), "cuda", None),
        "cuda_available": cuda_ok,
        "cuda_device_count": int(torch.cuda.device_count() or 0) if hasattr(torch, "cuda") else 0,
      }
      if cuda_ok and int(diag.get("cuda_device_count") or 0) > 0:
        try:
          diag["cuda_device_0"] = str(torch.cuda.get_device_name(0) or "")
        except Exception:
          diag["cuda_device_0"] = ""
    except Exception as e:
      diag = {"torch_error": str(e)}
    return {"provider": "sentence_transformers", "model": model_name, "device": device, "has_gpu": device == "cuda", "diag": diag}
  if provider == "ollama":
    model_name = (os.getenv("EDUAI_OLLAMA_EMBED_MODEL") or "nomic-embed-text").strip()
    return {"provider": "ollama", "model": model_name, "device": "server", "has_gpu": None}
  if provider == "openai":
    model_name = (os.getenv("EDUAI_OPENAI_EMBED_MODEL") or "text-embedding-3-small").strip()
    return {"provider": "openai", "model": model_name, "device": "api", "has_gpu": None}
  if provider == "gemini":
    model_name = (_get_db_config("AI_GEMINI_EMBED_MODEL") or "text-embedding-004").strip()
    return {"provider": "gemini", "model": model_name, "device": "api", "has_gpu": None}
  return {"provider": provider, "model": "", "device": "none", "has_gpu": None}


_local_model = None
_local_lock = threading.Lock()


def _pick_local_device() -> str:
  raw = (os.getenv("EDUAI_EMBED_DEVICE") or "auto").strip().lower()
  if raw and raw != "auto":
    return raw
  try:
    import torch

    if torch.cuda.is_available():
      return "cuda"
  except Exception:
    pass
  return "cpu"


def _get_local_model(model_name: str):
  global _local_model
  if _local_model is not None:
    return _local_model
  with _local_lock:
    if _local_model is None:
      from sentence_transformers import SentenceTransformer

      _local_model = SentenceTransformer(model_name, device=_pick_local_device())
  return _local_model


def _normalize_embed_input_type(input_type: str | None) -> str | None:
  if input_type is None:
    return None
  t = str(input_type).strip().lower()
  if not t:
    return None
  if "query" in t:
    return "query"
  if "document" in t or "passage" in t:
    return "document"
  return t


def _apply_sentence_transformers_conventions(text: str, *, model_name: str, input_type: str | None) -> str:
  t = (text or "").strip()
  if not t:
    return t
  it = _normalize_embed_input_type(input_type)
  is_e5 = "e5" in model_name.lower()
  if not is_e5:
    return t
  q_prefix = os.getenv("EDUAI_E5_QUERY_PREFIX")
  p_prefix = os.getenv("EDUAI_E5_PASSAGE_PREFIX")
  legacy_prefix = os.getenv("EDUAI_E5_PREFIX")
  if q_prefix is None:
    q_prefix = "query: "
  if p_prefix is None:
    p_prefix = (legacy_prefix if legacy_prefix is not None else "passage: ")
  if it == "query":
    return f"{q_prefix}{t}"
  if it == "document":
    return f"{p_prefix}{t}"
  return t


def embed_text_typed(text: str, *, model: str | None = None, input_type: str | None = None) -> tuple[list[float], str]:
  provider = _select_provider(os.getenv("EDUAI_EMBED_PROVIDER") or "")
  if provider == "none":
    raise RuntimeError("embed_provider_not_configured")
  if provider == "sentence_transformers":
    model_name = (model or os.getenv("EDUAI_LOCAL_EMBED_MODEL") or os.getenv("EDUAI_OPENAI_EMBED_MODEL") or "intfloat/multilingual-e5-base").strip()
    t = _apply_sentence_transformers_conventions(text, model_name=model_name, input_type=input_type)
    if not t:
      raise RuntimeError("empty_text")
    max_chars = int(os.getenv("EDUAI_EMBED_MAX_CHARS") or "8000")
    if max_chars < 1000:
      max_chars = 1000
    if len(t) > max_chars:
      t = t[:max_chars]
    m = _get_local_model(model_name)
    normalize = (os.getenv("EDUAI_EMBED_NORMALIZED") or "true").strip().lower() in ("1", "true", "yes", "on")
    vec = m.encode([t], normalize_embeddings=normalize, show_progress_bar=False)[0]
    try:
      vec = vec.tolist()
    except Exception:
      vec = [float(x) for x in vec]
    return [float(x) for x in vec], model_name
  if provider == "ollama":
    t = _apply_sentence_transformers_conventions((text or "").strip(), model_name=(model or os.getenv("EDUAI_OLLAMA_EMBED_MODEL") or "nomic-embed-text").strip(), input_type=input_type)
    if not t:
      raise RuntimeError("empty_text")
    max_chars = int(os.getenv("EDUAI_EMBED_MAX_CHARS") or "8000")
    if max_chars < 1000:
      max_chars = 1000
    if len(t) > max_chars:
      t = t[:max_chars]
    return _embed_ollama(t, model=model)
  if provider == "gemini":
    t = (text or "").strip()
    if not t:
      raise RuntimeError("empty_text")
    max_chars = int(os.getenv("EDUAI_EMBED_MAX_CHARS") or "8000")
    if max_chars < 1000:
      max_chars = 1000
    if len(t) > max_chars:
      t = t[:max_chars]
    return _embed_gemini(t, model=model)
  if provider != "openai":
    raise RuntimeError("embed_provider_not_configured")

  ring = get_ring("AI_OPENAI_API_KEY")
  keys = ring.list_keys()
  if not keys:
    raise RuntimeError("missing_openai_api_key")

  base_url = (_get_db_config("AI_OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
  model = (model or os.getenv("EDUAI_OPENAI_EMBED_MODEL") or "text-embedding-3-small").strip()
  dimensions_raw = (os.getenv("EDUAI_OPENAI_EMBED_DIMENSIONS") or "").strip()

  t = (text or "").strip()
  if not t:
    raise RuntimeError("empty_text")

  max_chars = int(os.getenv("EDUAI_EMBED_MAX_CHARS") or "8000")
  if max_chars < 1000:
    max_chars = 1000
  if len(t) > max_chars:
    t = t[:max_chars]

  body: dict = {"model": model, "input": t}
  if dimensions_raw:
    try:
      body["dimensions"] = int(dimensions_raw)
    except Exception:
      pass

  last_err: Exception | None = None
  for _ in range(max(1, len(keys))):
    api_key = ring.pick() or ""
    if not api_key:
      break
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
      url=f"{base_url}/embeddings",
      data=data,
      method="POST",
      headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
      with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        res = json.loads(raw) if raw else {}
      vec = (res.get("data") or [{}])[0].get("embedding")
      if not isinstance(vec, list) or not vec:
        raise RuntimeError("empty_embedding")
      return [float(x) for x in vec], model
    except urllib.error.HTTPError as e:
      raw = e.read().decode("utf-8", errors="replace")
      err = RuntimeError(f"Embedding HTTP {e.code}: {raw}")
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


def embed_texts_typed(texts: list[str], *, model: str | None = None, input_type: str | None = None) -> tuple[list[list[float]], str]:
  provider = _select_provider(os.getenv("EDUAI_EMBED_PROVIDER") or "")
  if provider == "none":
    raise RuntimeError("embed_provider_not_configured")
  cleaned = [str(x or "").strip() for x in (texts or [])]
  if not cleaned or not any(cleaned):
    raise RuntimeError("empty_texts")

  if provider == "sentence_transformers":
    model_name = (model or os.getenv("EDUAI_LOCAL_EMBED_MODEL") or os.getenv("EDUAI_OPENAI_EMBED_MODEL") or "intfloat/multilingual-e5-base").strip()
    max_chars = int(os.getenv("EDUAI_EMBED_MAX_CHARS") or "8000")
    if max_chars < 1000:
      max_chars = 1000
    prepared: list[str] = []
    for t in cleaned:
      t2 = _apply_sentence_transformers_conventions(t, model_name=model_name, input_type=input_type)
      if not t2:
        prepared.append("")
        continue
      if len(t2) > max_chars:
        t2 = t2[:max_chars]
      prepared.append(t2)
    if not any(prepared):
      raise RuntimeError("empty_texts")

    m = _get_local_model(model_name)
    normalize = (os.getenv("EDUAI_EMBED_NORMALIZED") or "true").strip().lower() in ("1", "true", "yes", "on")
    try:
      batch_size = int((os.getenv("EDUAI_EMBED_BATCH_SIZE") or "").strip() or "32")
    except Exception:
      batch_size = 32
    if batch_size < 1:
      batch_size = 1
    vecs = m.encode(prepared, normalize_embeddings=normalize, show_progress_bar=False, batch_size=batch_size)
    out: list[list[float]] = []
    for v in vecs:
      try:
        out.append([float(x) for x in v.tolist()])
      except Exception:
        out.append([float(x) for x in v])
    return out, model_name

  if provider in ("ollama", "gemini"):
    out: list[list[float]] = []
    used_model = ""
    for t in cleaned:
      if not t:
        out.append([])
        continue
      vec, used_model = embed_text_typed(t, model=model, input_type=input_type)
      out.append(vec)
    if not any(out):
      raise RuntimeError("empty_embedding")
    return out, used_model

  if provider != "openai":
    raise RuntimeError("embed_provider_not_configured")

  ring = get_ring("AI_OPENAI_API_KEY")
  keys = ring.list_keys()
  if not keys:
    raise RuntimeError("missing_openai_api_key")

  base_url = (_get_db_config("AI_OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
  model = (model or os.getenv("EDUAI_OPENAI_EMBED_MODEL") or "text-embedding-3-small").strip()
  dimensions_raw = (os.getenv("EDUAI_OPENAI_EMBED_DIMENSIONS") or "").strip()

  max_chars = int(os.getenv("EDUAI_EMBED_MAX_CHARS") or "8000")
  if max_chars < 1000:
    max_chars = 1000
  prepared = []
  for t in cleaned:
    t2 = t.strip()
    if not t2:
      prepared.append("")
      continue
    if len(t2) > max_chars:
      t2 = t2[:max_chars]
    prepared.append(t2)
  if not any(prepared):
    raise RuntimeError("empty_texts")

  body: dict = {"model": model, "input": prepared}
  if dimensions_raw:
    try:
      body["dimensions"] = int(dimensions_raw)
    except Exception:
      pass
  last_err: Exception | None = None
  for _ in range(max(1, len(keys))):
    api_key = ring.pick() or ""
    if not api_key:
      break
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
      url=f"{base_url}/embeddings",
      data=data,
      method="POST",
      headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
      with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        res = json.loads(raw) if raw else {}

      data_list = res.get("data") or []
      if not isinstance(data_list, list) or not data_list:
        raise RuntimeError("empty_embedding")
      out: list[list[float]] = []
      for row in data_list:
        vec = (row or {}).get("embedding") if isinstance(row, dict) else None
        if not isinstance(vec, list) or not vec:
          out.append([])
        else:
          out.append([float(x) for x in vec])
      if not any(out):
        raise RuntimeError("empty_embedding")
      return out, model
    except urllib.error.HTTPError as e:
      raw = e.read().decode("utf-8", errors="replace")
      err = RuntimeError(f"Embedding HTTP {e.code}: {raw}")
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


def embed_text(text: str, *, model: str | None = None) -> tuple[list[float], str]:
  return embed_text_typed(text, model=model, input_type="document")


def embed_text_query(text: str, *, model: str | None = None) -> tuple[list[float], str]:
  return embed_text_typed(text, model=model, input_type="query")


def embed_text_document(text: str, *, model: str | None = None) -> tuple[list[float], str]:
  return embed_text_typed(text, model=model, input_type="document")


def embed_texts_query(texts: list[str], *, model: str | None = None) -> tuple[list[list[float]], str]:
  return embed_texts_typed(texts, model=model, input_type="query")


def embed_texts_document(texts: list[str], *, model: str | None = None) -> tuple[list[list[float]], str]:
  return embed_texts_typed(texts, model=model, input_type="document")
