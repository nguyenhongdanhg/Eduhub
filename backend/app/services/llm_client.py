
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

from app.services.local_config import load_local_config
from app.db import get_db_connection
from app.services.db_keyring import get_ring, is_key_exhausted_error

def _get_db_config(key: str) -> Optional[str]:
    """Get configuration from database system_configs table"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT conf_value FROM system_configs WHERE conf_key = %s", (key,))
                row = cur.fetchone()
                return row.get("conf_value") if row else None
    except Exception:
        return None

def _log_token_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int, content_type: Optional[str] = None):
    """Log token usage to database"""
    try:
        from app.services.auth import get_current_user_id
        user_id = None
        # Note: This might be tricky if not in a request context, 
        # but usually LLM calls are triggered by users.
    except ImportError:
        user_id = None

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO token_usage_logs (user_id, provider, model, prompt_tokens, completion_tokens, content_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, provider, model, prompt_tokens, completion_tokens, content_type))
            conn.commit()
    except Exception as e:
        print(f"Error logging token usage: {e}")

def _post_json(url: str, body: dict, headers: dict) -> dict:
  data = json.dumps(body).encode("utf-8")
  req = urllib.request.Request(url=url, data=data, method="POST", headers=headers)
  try:
    with urllib.request.urlopen(req, timeout=60) as resp:
      raw = resp.read().decode("utf-8")
      return json.loads(raw) if raw else {}
  except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"LLM HTTP {e.code}: {raw}") from e


def _normalize_gemini_model_id(model: str) -> str:
  s = str(model or "").strip()
  if not s:
    return ""
  s = s.replace("models/", "").replace("Models/", "").strip()
  s = re.sub(r"\s+", "-", s.lower()).strip("-")
  return s


def get_summary_prompt_presets() -> list[dict]:
  default_p1 = (
    "Bạn là trợ lý tóm tắt văn bản hành chính cho lãnh đạo đọc nhanh. "
    "Chỉ tóm tắt, không đưa ra quyết định hay chỉ đạo thực thi. "
    "Trả lời tiếng Việt, văn bản thuần (KHÔNG dùng Markdown, KHÔNG dùng **, KHÔNG bảng). "
    "Tóm tắt ngắn gọn 5-7 ý, mỗi ý 1 dòng. "
    "Nêu ý chính, đối tượng áp dụng, số liệu/mốc thời gian/hạn xử lý nếu có."
  )
  default_p3 = (
    "Bạn là trợ lý tóm tắt văn bản hành chính theo chuẩn điều hành. "
    "Chỉ tóm tắt, không đưa ra quyết định hay chỉ đạo thực thi. "
    "Trả lời tiếng Việt, văn bản thuần (KHÔNG dùng Markdown, KHÔNG dùng **, KHÔNG bảng).\n"
    "Cấu trúc (mỗi mục 1 dòng, không bullet Markdown):\n"
    "Mục tiêu/vấn đề: ...\nNội dung chính: ...\nYêu cầu/đầu việc: ...\nMốc thời gian/hạn xử lý: ...\nĐối tượng/đơn vị liên quan: ...\n"
    "Giữ ngắn gọn, ưu tiên thông tin có thể hành động."
  )
  default_general = (
    "Bạn là trợ lý tóm tắt văn bản hành chính. "
    "Chỉ tóm tắt, không đưa ra quyết định hay chỉ đạo thực thi. "
    "Trả lời tiếng Việt, văn bản thuần (KHÔNG dùng Markdown, KHÔNG dùng **, KHÔNG bảng). "
    "Tóm tắt 6-10 ý, mỗi ý 1 dòng, nêu nội dung chính, đối tượng áp dụng, mốc thời gian/hạn xử lý nếu có."
  )
  p1 = (os.getenv("EDUAI_SUMMARY_PROMPT_P1") or "").strip() or default_p1
  p3 = (os.getenv("EDUAI_SUMMARY_PROMPT_P3") or "").strip() or default_p3
  general = (os.getenv("EDUAI_SUMMARY_PROMPT_DEFAULT") or "").strip() or default_general

  base = [
    {"id": "p1", "label": "Lãnh đạo đọc nhanh", "prompt": p1},
    {"id": "p3", "label": "Tổng hợp chuẩn điều hành", "prompt": p3},
    {"id": "default", "label": "Mặc định", "prompt": general},
  ]

  cfg = load_local_config() or {}
  raw = cfg.get("SUMMARY_PROMPT_PRESETS")
  if not isinstance(raw, list):
    raw = []

  merged: dict[str, dict] = {p["id"]: dict(p) for p in base if isinstance(p, dict) and p.get("id")}
  extra_order: list[str] = []
  for it in raw:
    if not isinstance(it, dict):
      continue
    pid = str(it.get("id") or "").strip()
    prompt = str(it.get("prompt") or "").strip()
    if not pid or not prompt:
      continue
    label = str(it.get("label") or pid).strip() or pid
    if pid in merged:
      merged[pid]["label"] = label
      merged[pid]["prompt"] = prompt
    else:
      merged[pid] = {"id": pid, "label": label, "prompt": prompt}
      extra_order.append(pid)

  def _apply_db():
    try:
      from app.services.ioffice_prompt_store import list_prompt_presets

      rows = list_prompt_presets()
    except Exception:
      rows = []
    if not rows:
      return
    for r in rows:
      try:
        pid = str(r.get("id") or "").strip()
        if not pid:
          continue
        if not bool(r.get("enabled")):
          if pid in merged:
            merged.pop(pid, None)
          continue
        label = str(r.get("label") or pid).strip() or pid
        prompt = str(r.get("prompt") or "").strip()
        if not prompt:
          continue
        if pid in merged:
          merged[pid]["label"] = label
          merged[pid]["prompt"] = prompt
        else:
          merged[pid] = {"id": pid, "label": label, "prompt": prompt}
          extra_order.append(pid)
      except Exception:
        continue

  _apply_db()

  out = [merged.get("p1") or base[0], merged.get("p3") or base[1], merged.get("default") or {"id": "default", "label": "Mặc định", "prompt": general}]
  for pid in extra_order:
    if pid in ("p1", "p3", "default"):
      continue
    out.append(merged[pid])
  return out


def get_summary_prompts() -> dict:
  presets = get_summary_prompt_presets()
  out: dict[str, str] = {}
  for p in presets:
    try:
      pid = str(p.get("id") or "").strip()
      pr = str(p.get("prompt") or "").strip()
      if pid and pr:
        out[pid] = pr
    except Exception:
      continue
  if "default" not in out and presets:
    out["default"] = str(presets[0].get("prompt") or "")
  return out


def _pick_prompt(prompt_mode: str | None) -> str:
  pm = (prompt_mode or "").strip().lower()
  prompts = get_summary_prompts()
  if pm and pm in prompts:
    return prompts[pm]
  if "default" in prompts:
    return prompts["default"]
  return next(iter(prompts.values()), "")


def _read_int_env(name: str, default: int) -> int:
  try:
    v = int(str(os.getenv(name) or "").strip() or str(default))
  except Exception:
    v = default
  if v < 1:
    v = default
  if v > 8192:
    v = 8192
  return v


def _read_optional_int_env(name: str, default: int | None = None) -> int | None:
  raw = str(os.getenv(name) or "").strip()
  if raw == "":
    return default
  try:
    v = int(raw)
  except Exception:
    return default
  if v < 1:
    return None
  if v > 8192:
    v = 8192
  return v


def _trim_by_chars(text: str, max_chars: int | None) -> str:
  t = (text or "").strip()
  if not t:
    return t
  if max_chars is None:
    return t
  try:
    n = int(max_chars)
  except Exception:
    return t
  if n < 1:
    return t
  return t[:n]


def _parse_model_list(raw: str | None, default: str) -> List[str]:
    s = (raw or "").strip() or default
    parts = [m.strip() for m in s.split(",") if m.strip()]
    return parts if parts else [default]


@dataclass(frozen=True)
class SummaryModelPlan:
  provider: str
  model: str
  api_key: str
  base_url: str
  prompt: str
  max_tokens: int | None


def _friendly_provider_name(provider: str) -> str:
  p = (provider or "").strip().lower()
  if p in ("openai", "openai_compatible"):
    return "OpenAI-compatible"
  if p == "deepseek":
    return "DeepSeek"
  if p == "gemini":
    return "Gemini"
  return p or "AI"


def _build_summary_plan(*, model: str | None = None, prompt_mode: str | None = None, provider: str | None = None, api_key: str | None = None, content_type: str = "summary") -> SummaryModelPlan:
  resolved_provider = _resolve_provider_for_call(resolve_summary_provider(provider))
  prompt = _pick_prompt(prompt_mode)
  max_tokens = _read_int_env("EDUAI_IOFFICE_SUMMARY_MAX_TOKENS", 1600) if str(content_type or "").strip().lower() == "ioffice_summary" else _read_int_env("EDUAI_SUMMARY_MAX_TOKENS", 1024)
  if resolved_provider == "fallback":
    raise RuntimeError("Chưa cấu hình AI để tóm tắt. Vào Cấu hình AI, thêm API key OpenAI/Gemini/DeepSeek và chọn provider/model tóm tắt.")
  if resolved_provider in ("openai", "openai_compatible"):
    base_url = (_get_db_config("AI_OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    selected_model = (model or _get_db_config("AI_OPENAI_MODEL") or "gpt-4o-mini").strip()
    key = str(api_key or get_ring("AI_OPENAI_API_KEY").pick() or "").strip()
    if not key:
      raise RuntimeError("Thiếu API key OpenAI-compatible trong Cấu hình AI.")
    return SummaryModelPlan(provider="openai_compatible", model=selected_model, api_key=key, base_url=base_url, prompt=prompt, max_tokens=max_tokens)
  if resolved_provider == "deepseek":
    base_url = (_get_db_config("AI_DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").strip()
    selected_model = (model or _get_db_config("AI_DEEPSEEK_MODEL") or "deepseek-chat").strip()
    key = str(api_key or get_ring("AI_DEEPSEEK_API_KEY").pick() or "").strip()
    if not key:
      raise RuntimeError("Thiếu API key DeepSeek trong Cấu hình AI.")
    return SummaryModelPlan(provider="deepseek", model=selected_model, api_key=key, base_url=base_url, prompt=prompt, max_tokens=max_tokens)
  if resolved_provider == "gemini":
    base_url = (_get_db_config("AI_GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta").strip()
    selected_model = (model or _get_db_config("AI_GEMINI_MODEL") or "gemini-1.5-flash").strip()
    key = str(api_key or get_ring("AI_GEMINI_API_KEY").pick() or "").strip()
    if not key:
      raise RuntimeError("Thiếu API key Gemini trong Cấu hình AI.")
    return SummaryModelPlan(provider="gemini", model=selected_model, api_key=key, base_url=base_url, prompt=prompt, max_tokens=max_tokens)
  raise RuntimeError(f"Provider tóm tắt không được hỗ trợ: {resolved_provider}")


def validate_summary_model(*, model: str | None = None, prompt_mode: str | None = None, provider: str | None = None, api_key: str | None = None, content_type: str = "summary") -> dict:
  plan = _build_summary_plan(model=model, prompt_mode=prompt_mode, provider=provider, api_key=api_key, content_type=content_type)
  return {"provider": plan.provider, "provider_label": _friendly_provider_name(plan.provider), "model": plan.model, "base_url": plan.base_url}


def _summarize_openai_compatible(
  text: str,
  *,
  api_key: str,
  base_url: str,
  model: str,
  prompt: str,
  max_tokens: int | None,
  max_input_chars: int | None = 20000,
  provider_name: str = "openai_compatible",
  content_type: Optional[str] = None
) -> tuple[str, str]:
  body: dict = {
    "model": model,
    "temperature": 0.2,
    "messages": [
      {"role": "system", "content": prompt},
      {"role": "user", "content": _trim_by_chars(text, max_input_chars)},
    ],
  }
  if max_tokens is not None:
    body["max_tokens"] = int(max_tokens)
  headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
  res = _post_json(f"{base_url.rstrip('/')}/chat/completions", body, headers)
  
  # Extract content
  content = res.get("choices", [{}])[0].get("message", {}).get("content")
  
  # Log token usage
  usage = res.get("usage", {})
  prompt_tokens = usage.get("prompt_tokens", 0)
  completion_tokens = usage.get("completion_tokens", 0)
  if prompt_tokens or completion_tokens:
      _log_token_usage(provider_name, model, prompt_tokens, completion_tokens, content_type)
      
  if not content:
    raise RuntimeError("empty_response")
  return str(content).strip(), model


def _summarize_gemini(
  text: str,
  *,
  api_key: str,
  base_url: str,
  model: str,
  prompt: str,
  max_tokens: int | None,
  max_input_chars: int | None = 20000,
  content_type: Optional[str] = None,
) -> tuple[str, str]:
  model_id = _normalize_gemini_model_id(model)
  url = f"{base_url.rstrip('/')}/models/{urllib.parse.quote(model_id)}:generateContent?key={urllib.parse.quote(api_key)}"
  gen_cfg: dict = {"temperature": 0.2}
  if max_tokens is not None:
    gen_cfg["maxOutputTokens"] = int(max_tokens)
  body: dict = {
    "systemInstruction": {"parts": [{"text": prompt}]},
    "contents": [{"role": "user", "parts": [{"text": _trim_by_chars(text, max_input_chars)}]}],
    "generationConfig": gen_cfg,
  }
  headers = {"Content-Type": "application/json"}
  res = _post_json(url, body, headers)
  
  candidates = res.get("candidates") or []
  if not candidates:
    raise RuntimeError("empty_response")
  
  # Extract content
  content = candidates[0].get("content") or {}
  parts = content.get("parts") or []
  texts = [p.get("text") for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
  out = "\n".join([t for t in texts if t and t.strip()]).strip()
  
  # Gemini token usage is in usageMetadata
  usage = res.get("usageMetadata", {})
  prompt_tokens = usage.get("promptTokenCount", 0)
  completion_tokens = usage.get("candidatesTokenCount", 0)
  if prompt_tokens or completion_tokens:
      _log_token_usage("gemini", model, prompt_tokens, completion_tokens, content_type)
      
  if not out:
    raise RuntimeError("empty_response")
  return out, model


def _get_openai_compatible_key() -> str:
  ring = get_ring("AI_OPENAI_API_KEY")
  k = ring.pick()
  return (k or "").strip()


def _get_deepseek_key() -> str:
  ring = get_ring("AI_DEEPSEEK_API_KEY")
  k = ring.pick()
  return (k or "").strip()


def _get_gemini_key() -> str:
  ring = get_ring("AI_GEMINI_API_KEY")
  k = ring.pick()
  return (k or "").strip()


def _auto_pick_provider() -> str:
  if get_ring("AI_OPENAI_API_KEY").list_keys():
    return "openai_compatible"
  if get_ring("AI_DEEPSEEK_API_KEY").list_keys():
    return "deepseek"
  if get_ring("AI_GEMINI_API_KEY").list_keys():
    return "gemini"
  return "fallback"


_provider_rr_lock = threading.Lock()
_provider_rr_cursor = 0


def _available_providers_for_auto() -> list[str]:
  out: list[str] = []
  if get_ring("AI_OPENAI_API_KEY").list_keys():
    out.append("openai_compatible")
  if get_ring("AI_DEEPSEEK_API_KEY").list_keys():
    out.append("deepseek")
  if get_ring("AI_GEMINI_API_KEY").list_keys():
    out.append("gemini")
  return out


def _pick_provider_round_robin(available: list[str]) -> str:
  global _provider_rr_cursor
  if not available:
    return "fallback"
  with _provider_rr_lock:
    i = int(_provider_rr_cursor) % max(1, len(available))
    _provider_rr_cursor += 1
  return available[i]


def _resolve_provider_for_call(configured_provider: str) -> str:
  p = (configured_provider or "").strip().lower()
  if not p or p == "auto":
    available = _available_providers_for_auto()
    if not available:
      return "fallback"
    if len(available) == 1:
      return available[0]
    return _pick_provider_round_robin(available)
  return p


def resolve_summary_provider(requested: str | None = None) -> str:
  provider = (requested or _get_db_config("AI_SUMMARY_PROVIDER") or "").strip().lower()
  return provider or "auto"


def resolve_generate_provider(requested: str | None = None) -> str:
  provider = (requested or _get_db_config("AI_GENERATE_PROVIDER") or "").strip().lower()
  return provider or "auto"


def summarize_text(
  text: str,
  *,
  model: str | None = None,
  prompt_mode: str | None = None,
  provider: str | None = None,
  api_key: str | None = None,
  content_type: str = "summary"
) -> tuple[str, str]:
  plan = _build_summary_plan(model=model, prompt_mode=prompt_mode, provider=provider, api_key=api_key, content_type=content_type)
  if plan.provider in ("openai", "openai_compatible"):
    try:
      return _summarize_openai_compatible(text, api_key=plan.api_key, base_url=plan.base_url, model=plan.model, prompt=plan.prompt, max_tokens=plan.max_tokens, provider_name="openai", content_type=content_type)
    except Exception as e:
      if is_key_exhausted_error(e):
        get_ring("AI_OPENAI_API_KEY").mark_bad(plan.api_key, cooldown_seconds=120)
      raise RuntimeError(f"Model tóm tắt OpenAI-compatible không chạy được ({plan.model}). Kiểm tra lại model trước khi tóm tắt. Chi tiết: {e}") from e
  if plan.provider == "deepseek":
    try:
      return _summarize_openai_compatible(text, api_key=plan.api_key, base_url=plan.base_url, model=plan.model, prompt=plan.prompt, max_tokens=plan.max_tokens, provider_name="deepseek", content_type=content_type)
    except Exception as e:
      if is_key_exhausted_error(e):
        get_ring("AI_DEEPSEEK_API_KEY").mark_bad(plan.api_key, cooldown_seconds=120)
      raise RuntimeError(f"Model tóm tắt DeepSeek không chạy được ({plan.model}). Kiểm tra lại model trước khi tóm tắt. Chi tiết: {e}") from e
  if plan.provider == "gemini":
    try:
      chosen_model = _normalize_gemini_model_id(plan.model)
      return _summarize_gemini(text, api_key=plan.api_key, base_url=plan.base_url, model=chosen_model, prompt=plan.prompt, max_tokens=plan.max_tokens, content_type=content_type)
    except Exception as e:
      if is_key_exhausted_error(e):
        get_ring("AI_GEMINI_API_KEY").mark_bad(plan.api_key, cooldown_seconds=120)
      raise RuntimeError(f"Model tóm tắt Gemini không chạy được ({plan.model}). Kiểm tra lại model trước khi tóm tắt. Chi tiết: {e}") from e
  raise RuntimeError(f"unsupported_provider:{plan.provider}")


def generate_text(
  user_text: str,
  *,
  system_prompt: str,
  model: str | None = None,
  provider: str | None = None,
  api_key: str | None = None,
  content_type: str = "generate"
) -> tuple[str, str]:
  configured_provider = resolve_generate_provider(provider)
  provider = _resolve_provider_for_call(configured_provider)
  user_text2 = (user_text or "").strip()
  if not user_text2:
    raise ValueError("empty_text")
  sys2 = (system_prompt or "").strip()
  if not sys2:
    raise ValueError("empty_prompt")
  if str(content_type or "").strip().lower() == "ioffice_generate":
    max_tokens = _read_optional_int_env("EDUAI_IOFFICE_GENERATE_MAX_TOKENS", None)
    max_input_chars = _read_optional_int_env("EDUAI_IOFFICE_GENERATE_MAX_INPUT_CHARS", None)
  else:
    max_tokens = _read_optional_int_env("EDUAI_GENERATE_MAX_TOKENS", 2000)
    max_input_chars = _read_optional_int_env("EDUAI_LLM_MAX_INPUT_CHARS", 20000)
  user_text2 = _trim_by_chars(user_text2, max_input_chars)

  if provider == "fallback":
    raise RuntimeError("Chưa cấu hình AI để sinh văn bản. Vào Cấu hình AI, thêm API key/provider/model hoặc chọn provider tạo nội dung hợp lệ.")

  if provider in ("openai", "openai_compatible"):
    base_url = (_get_db_config("AI_OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    default_model = (_get_db_config("AI_GENERATE_MODEL") or _get_db_config("AI_OPENAI_MODEL") or "gpt-4o-mini").strip()
    model_list = _parse_model_list(model, default_model)
    
    ring = get_ring("AI_OPENAI_API_KEY")
    keys = ring.list_keys()
    if api_key:
      keys = [str(api_key).strip()]
    if not keys:
      raise RuntimeError("missing_openai_api_key")
    last_err: Exception | None = None
    for _ in range(max(1, len(keys))):
      k = keys[0] if api_key else (ring.pick() or "")
      if not k:
        break
      for m in model_list:
        try:
            return _summarize_openai_compatible(
              user_text2,
              api_key=k,
              base_url=base_url,
              model=m,
              prompt=sys2,
              max_tokens=max_tokens,
              max_input_chars=None,
              provider_name="openai",
              content_type=content_type,
            )
        except Exception as e:
            last_err = e
            if is_key_exhausted_error(e):
                ring.mark_bad(k, cooldown_seconds=120)
                break
            continue
    raise last_err or RuntimeError("missing_openai_api_key")

  if provider == "deepseek":
    base_url = (_get_db_config("AI_DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").strip()
    default_model = (_get_db_config("AI_GENERATE_MODEL") or _get_db_config("AI_DEEPSEEK_MODEL") or "deepseek-chat").strip()
    model_list = _parse_model_list(model, default_model)

    ring = get_ring("AI_DEEPSEEK_API_KEY")
    keys = ring.list_keys()
    if api_key:
      keys = [str(api_key).strip()]
    if not keys:
      raise RuntimeError("missing_deepseek_api_key")
    last_err: Exception | None = None
    for _ in range(max(1, len(keys))):
      k = keys[0] if api_key else (ring.pick() or "")
      if not k:
        break
      for m in model_list:
        try:
            return _summarize_openai_compatible(
              user_text2,
              api_key=k,
              base_url=base_url,
              model=m,
              prompt=sys2,
              max_tokens=max_tokens,
              max_input_chars=None,
              provider_name="deepseek",
              content_type=content_type,
            )
        except Exception as e:
            last_err = e
            if is_key_exhausted_error(e):
                ring.mark_bad(k, cooldown_seconds=120)
                break
            continue
            
    raise last_err or RuntimeError("missing_deepseek_api_key")

  if provider == "gemini":
    base_url = (_get_db_config("AI_GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta").strip()
    default_model = (_get_db_config("AI_GENERATE_MODEL") or _get_db_config("AI_GEMINI_MODEL") or "gemini-1.5-flash").strip()
    model_list = _parse_model_list(model, default_model)
    
    ring = get_ring("AI_GEMINI_API_KEY")
    keys = ring.list_keys()
    if api_key:
      keys = [str(api_key).strip()]
    if not keys:
      raise RuntimeError("missing_gemini_api_key")
    last_err: Exception | None = None
    for _ in range(max(1, len(keys))):
      k = keys[0] if api_key else (ring.pick() or "")
      if not k:
        break
      for m in model_list:
        try:
            chosen_model = _normalize_gemini_model_id(m)
            return _summarize_gemini(
              user_text2,
              api_key=k,
              base_url=base_url,
              model=chosen_model,
              prompt=sys2,
              max_tokens=max_tokens,
              max_input_chars=None,
              content_type=content_type,
            )
        except Exception as e:
            last_err = e
            if is_key_exhausted_error(e):
                ring.mark_bad(k, cooldown_seconds=120)
                break
            continue
    raise last_err or RuntimeError("missing_gemini_api_key")

  raise RuntimeError(f"unsupported_provider:{provider}")


def _fallback(text: str) -> str:
  t = (text or "").strip()
  if not t:
    return "Không có nội dung để tóm tắt."
  snippet = t[:1200]
  return f"Tóm tắt (tạm thời):\n{snippet}"
