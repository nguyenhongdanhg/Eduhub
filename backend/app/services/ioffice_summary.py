import hashlib
import re

from app.services.llm_client import summarize_text
from utils import FILES_ROOT, make_safe_relative_from_any
from ai_summary_compat import extract_text_from_zip_selected


def sha256_hex(text: str) -> str:
  return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def build_summary_input(doc: dict, extracted_text: str) -> str:
  meta = (
    f"Số ký hiệu: {doc.get('so_ky_hieu') or ''}\n"
    f"Trích yếu: {doc.get('trich_yeu') or ''}\n"
    f"Đơn vị ban hành: {doc.get('don_vi_ban_hanh') or ''}\n"
    f"Vai trò: {doc.get('vai_tro') or ''}\n"
    f"Ngày đến: {doc.get('ngay_den') or ''}\n"
    f"Hạn xử lý: {doc.get('han_xu_ly') or ''}\n"
  ).strip()
  if extracted_text.strip():
    return f"{meta}\n\nNỘI DUNG VĂN BẢN:\n{extracted_text}"
  return meta


def sanitize_summary_output(text: str) -> str:
  t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
  t = t.replace("`", "")
  t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
  t = re.sub(r"__(.+?)__", r"\1", t)
  t = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", t)
  t = re.sub(r"(?m)^\s{0,3}>\s?", "", t)
  t = re.sub(r"(?m)^\s{0,3}[-*•]\s+", "", t)
  t = re.sub(r"(?m)^\s{0,3}\d+[\.\)]\s+", "", t)
  t = re.sub(r"[ \t]+\n", "\n", t)
  t = re.sub(r"\n{3,}", "\n\n", t)
  return t.strip()


def prepare_summary_input(
  doc: dict,
  *,
  selected_members: list[str] | None = None,
  model: str | None = None,
  prompt_mode: str | None = None,
) -> tuple[str, str]:
  file_path = (doc.get("file_path") or doc.get("duong_dan_file") or "").strip()
  extracted = ""
  if file_path:
    safe = make_safe_relative_from_any(file_path)
    p = FILES_ROOT / safe
    if p.exists() and p.suffix.lower() == ".zip":
      extracted = extract_text_from_zip_selected(p, selected_members)
  inp = build_summary_input(doc, extracted)
  members = selected_members or []
  members_norm = ",".join(sorted([str(x or "").strip() for x in members if str(x or "").strip()]))
  cfg = f"prompt_mode={(prompt_mode or '').strip()}|model={(model or '').strip()}|members={members_norm}"
  h = sha256_hex(f"{inp}\n\n__SUMMARY_CFG__:{cfg}")
  return inp, h


def summarize_document(
  doc: dict,
  *,
  selected_members: list[str] | None = None,
  model: str | None = None,
  prompt_mode: str | None = None,
) -> tuple[str, str, str]:
  inp, h = prepare_summary_input(doc, selected_members=selected_members, model=model, prompt_mode=prompt_mode)
  
  # Smart Model Selection similar to Principal Agent
  # If model is a list (e.g. "o1,gpt-4o"), use reasoning model for summary task
  from app.services.principal_deeptutor_agent import _resolve_smart_model
  
  # iOffice Summary task can benefit from reasoning models if available
  # We assume user might configure a list of models in DB config
  smart_model = _resolve_smart_model(None, model, task_type="reasoning")
  
  summary, model_used = summarize_text(inp, model=smart_model, prompt_mode=prompt_mode, content_type="ioffice_summary")
  
  # Clean output if it came from a reasoning model
  from app.services.principal_deeptutor_agent import _clean_reasoning_output
  summary = _clean_reasoning_output(summary)
  
  return sanitize_summary_output(summary), model_used, h
