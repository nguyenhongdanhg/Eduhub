import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Awaitable

from app.services.llm_client import generate_text


async def _emit(
  cb: Callable[[str, dict[str, Any]], None | Awaitable[None]] | None,
  stage: str,
  message: str,
  data: dict[str, Any] | None = None,
):
  if not cb:
    return
  payload = {"stage": stage, "message": message}
  if data and isinstance(data, dict):
    payload.update(data)
  try:
    res = cb(stage, payload)
    if res is not None and hasattr(res, "__await__"):
      await res
  except Exception:
    return


def _project_root() -> Path:
  return Path(__file__).resolve().parents[2]


def _ensure_deeptutor_on_path():
  root = _project_root()
  deeptutor_root = root / "apps" / "DeepTutor"
  if deeptutor_root.exists():
    p = str(deeptutor_root)
    if p not in sys.path:
      sys.path.insert(0, p)


def _truncate(s: str, max_len: int) -> str:
  t = str(s or "")
  if len(t) <= max_len:
    return t
  return t[: max_len - 1] + "…"


def _clean_reasoning_output(text: str) -> str:
  """Remove <think>...</think> blocks from DeepSeek Reasoner output"""
  import re
  s = str(text or "")
  # Remove content between <think> and </think> (dotall)
  s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL)
  # Also remove standalone tags just in case
  s = s.replace("<think>", "").replace("</think>", "")
  return s.strip()


def _resolve_smart_model(provider: str | None, model: str | None, task_type: str = "reasoning") -> str | None:
    """
    Smartly resolve model for specific tasks (reasoning vs chat).
    If model is a comma-separated list, it picks the best one for the task.
    """
    if not model:
        return None
        
    # Split model list
    candidates = [m.strip() for m in str(model).split(",") if m.strip()]
    if not candidates:
        return None
        
    if len(candidates) == 1:
        return candidates[0]
        
    # Keywords for reasoning models
    reasoning_keywords = ["reasoner", "o1", "o3", "thinking", "r1"]
    
    # If task requires reasoning (IdeaGen, Research Planning)
    if task_type == "reasoning":
        # Find first model that matches reasoning keywords
        for m in candidates:
            if any(k in m.lower() for k in reasoning_keywords):
                # Put reasoning model first, but keep others as fallback
                others = [x for x in candidates if x != m]
                return ",".join([m] + others)
        # If no explicit reasoning model found, return original order
        return ",".join(candidates)
        
    # If task is chat/writing (Generation, Podcast)
    else:
        # Prefer models that are NOT reasoning models (usually cheaper/faster)
        for m in candidates:
            if not any(k in m.lower() for k in reasoning_keywords):
                others = [x for x in candidates if x != m]
                return ",".join([m] + others)
                
    return ",".join(candidates)


def _build_ideagen_prompt(user_request: str, context: str) -> tuple[str, str]:
  system_prompt = (
    "Bạn là Cộng tác viên viết bài (IdeaGen) hỗ trợ Hiệu trưởng.\n"
    "Nhiệm vụ: phân rã yêu cầu thành mục tiêu, dàn ý, và gợi ý các điểm cần kiểm chứng.\n"
    "CHỈ THỊ QUAN TRỌNG: Hãy chủ động đưa ra các giả định hợp lý dựa trên ngữ cảnh công việc và văn bản đã có. "
    "TUYỆT ĐỐI KHÔNG HỎI lại thông tin đã có trong văn bản đính kèm (hãy tự đọc kỹ toàn bộ ngữ cảnh). "
    "Nếu không đọc được toàn văn, hãy sử dụng tối đa thông tin từ phần TÓM TẮT VĂN BẢN (nếu có) để suy luận. "
    "Chỉ đặt câu hỏi làm rõ nếu thông tin THIẾU và CỰC KỲ QUAN TRỌNG không thể suy luận được.\n"
    "Nếu thông tin có trong văn bản đính kèm hoặc tài liệu tải lên, hãy coi như đã biết và KHÔNG hỏi lại.\n"
    "Nếu thiếu chi tiết nhỏ, hãy tự điền giá trị mặc định và ghi chú lại.\n"
    "Trả lời bằng tiếng Việt, ngắn gọn, có cấu trúc."
  )
  user_prompt = (
    "Hãy tạo dàn ý và checklist thông tin cần căn cứ.\n\n"
    f"YÊU CẦU:\n{user_request}\n\n"
    f"NGỮ CẢNH (Bao gồm văn bản đính kèm, tài liệu tải lên):\n{context}\n\n"
    "Đầu ra gồm 3 phần:\n"
    "1) Dàn ý (5-10 gạch đầu dòng)\n"
    "2) Checklist căn cứ cần có (3-8 mục)\n"
    "3) Câu hỏi làm rõ (Chỉ ghi nếu thực sự thiếu thông tin quan trọng. Nếu đủ thông tin, ghi 'Không có').\n"
  )
  return user_prompt, system_prompt


def _build_admin_writing_policy() -> str:
  return (
    "\n\nQUY CHUẨN SINH VĂN BẢN HÀNH CHÍNH:\n"
    "- Vai trò: chuyên viên tham mưu cho Hiệu trưởng, viết để lãnh đạo có thể dùng/chỉnh sửa ngay.\n"
    "- Đầu ra phải là văn bản/ý kiến chỉ đạo hoàn chỉnh theo đúng yêu cầu người dùng, không chỉ là phân tích.\n"
    "- Ưu tiên rõ việc, rõ đơn vị/cá nhân thực hiện, rõ thời hạn, rõ sản phẩm đầu ra.\n"
    "- Không hỏi lại nếu có thể suy luận hợp lý từ văn bản nguồn; thông tin chưa rõ thì ghi [cần bổ sung: ...] trong đúng vị trí cần điền.\n"
    "- Không bịa số văn bản, ngày tháng, tên đơn vị, căn cứ pháp lý nếu ngữ cảnh không có; dùng [số], [ngày], [đơn vị] khi thiếu.\n"
    "- Diễn đạt chuẩn mực, ngắn gọn, đúng văn phong hành chính tiếng Việt; tránh lời giải thích ngoài văn bản.\n"
    "- Nếu người dùng yêu cầu công văn/thông báo/kế hoạch/tờ trình, hãy trình bày đúng cấu trúc phù hợp thể loại đó.\n"
    "- Nếu đã chọn Mẫu, tuyệt đối tuân thủ loại văn bản của Mẫu; không tự đổi sang loại văn bản khác.\n"
    "- Sinh đầu ra như một bản dự thảo có thể đưa thẳng vào Word: có tên loại văn bản/trích yếu, kính gửi hoặc đối tượng nhận nếu phù hợp, nội dung, tổ chức thực hiện/nơi nhận/ký.\n"
    "- Nếu thiếu số/ký hiệu/ngày/người ký/cơ quan nhận, dùng placeholder như [số], [ngày], [người ký], [cơ quan nhận], không hỏi lại.\n"
    "- Không trả lời kiểu hội thoại, không viết lời giải thích ngoài văn bản dự thảo.\n"
    "- Nếu chỉ yêu cầu ý kiến tham mưu/chỉ đạo, trình bày thành các mục: Nội dung xử lý; Giao nhiệm vụ; Thời hạn; Lưu ý.\n"
    "- Khi dùng căn cứ từ trích dẫn, đặt mã [[CIT-XX]] ngay sau câu liên quan.\n"
    "- Không thêm mục rà soát, ghi chú, lời dặn hoặc phần giải thích sau văn bản trừ khi người dùng yêu cầu."
  )


def _build_podcast_prompt(final_text: str) -> tuple[str, str]:
  system_prompt = (
    "Bạn là biên tập viên podcast tiếng Việt.\n"
    "Tạo kịch bản ngắn 2 nhân vật: MC và Hiệu trưởng.\n"
    "Giọng tự nhiên, dễ nghe, tập trung vào quyết định và hành động.\n"
    "Không thêm thông tin ngoài nội dung đầu vào."
  )
  user_prompt = (
    "Tạo kịch bản podcast 2-4 phút dựa trên nội dung sau.\n"
    "Định dạng:\n"
    "MC: ...\n"
    "Hiệu trưởng: ...\n\n"
    f"NỘI DUNG:\n{final_text}\n"
  )
  return user_prompt, system_prompt


def _format_web_context(citations: list[dict[str, Any]], start_index: int) -> tuple[str, dict[str, Any]]:
  if not citations:
    return "", {}
  parts = ["NGUỒN WEB (trích):"]
  out_map: dict[str, Any] = {}
  idx = start_index
  for c in citations[:8]:
    idx += 1
    cit_id = f"CIT-{idx:02d}"
    title = str(c.get("title") or "").strip()
    url = str(c.get("url") or "").strip()
    snippet = str(c.get("snippet") or "").strip()
    content = str(c.get("content") or "").strip()
    excerpt = _truncate(content or snippet, 520)
    parts.append(f"[[{cit_id}]] {title}".strip())
    if url:
      parts.append(url)
    if excerpt:
      parts.append(excerpt)
    parts.append("")
    out_map[cit_id] = {
      "citation_id": cit_id,
      "source_type": "web",
      "title": title,
      "url": url,
      "snippet": snippet,
      "excerpt": excerpt,
      "tool_type": "web_search",
    }
  return "\n".join(parts).strip(), out_map


def _extract_questions(ideagen_out: str) -> list[str]:
  t = str(ideagen_out or "").strip()
  if not t:
    return []
  lines = [ln.strip() for ln in t.splitlines()]
  idx = -1
  for i, ln in enumerate(lines):
    low = ln.lower()
    if "câu hỏi" in low and ("làm rõ" in low or "làm ro" in low):
      idx = i
      break
  if idx < 0:
    return []
  out: list[str] = []
  import re
  marker_pattern = re.compile(r"^(\d+[\.\)]|\-|\*|•|[a-z][\.\)])\s*", re.IGNORECASE)
  md_pattern = re.compile(r"[\*_`>#\[\]\(\)]")
  none_phrases = {
    "không có", "khong co", "không", "khong", "none", "không có câu hỏi", "khong co cau hoi", "không cần",
    "khong can", "không có thông tin thiếu", "khong co thong tin thieu", "đủ thông tin", "du thong tin",
    "đã đủ thông tin", "da du thong tin", "không có câu hỏi làm rõ", "khong co cau hoi lam ro",
  }

  for ln in lines[idx + 1 :]:
    if not ln:
      continue
    ln_clean = marker_pattern.sub("", ln).strip()
    ln_plain = md_pattern.sub("", ln_clean).strip().lower().rstrip(".,;:! ")
    ln_plain = re.sub(r"\s+", " ", ln_plain)
    if not ln_plain:
      continue
    if ln_plain in none_phrases:
      return []
    if ln_plain.startswith("không có") or ln_plain.startswith("khong co"):
      return []
    if ln_plain.startswith("không cần") or ln_plain.startswith("khong can"):
      return []
    if "không có" in ln_plain and len(ln_plain) <= 80:
      return []
    if "khong co" in ln_plain and len(ln_plain) <= 80:
      return []
    if not ln_clean.endswith("?") and len(ln_plain.split()) <= 4:
      continue
    out.append(ln_clean)
    if len(out) >= 5:
      break
  return out


def _safe_json_loads(s: str) -> dict:
  try:
    import json

    obj = json.loads(s)
    return obj if isinstance(obj, dict) else {}
  except Exception:
    return {}


def _fetch_uploaded_rag_chunks(rag_document_id: int, *, max_chunks: int = 4) -> list[dict[str, Any]]:
  from app.db import get_db_connection

  rid = int(rag_document_id or 0)
  if rid <= 0:
    return []
  lim = int(max_chunks or 4)
  if lim < 1:
    lim = 1
  if lim > 10:
    lim = 10
  sql = """
    SELECT d.id AS rag_document_id, d.title, i.chunk_index, i.metadata
    FROM rag_documents d
    JOIN rag_items i ON i.rag_document_id=d.id
    WHERE d.id=%s AND (i.deleted_at IS NULL)
    ORDER BY i.chunk_index ASC
    LIMIT %s
  """
  with get_db_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(sql, (rid, lim))
      rows = list(cur.fetchall() or [])
  out: list[dict[str, Any]] = []
  for r in rows:
    meta = _safe_json_loads(str(r.get("metadata") or ""))
    out.append(
      {
        "rag_document_id": int(r.get("rag_document_id") or rid),
        "title": str(r.get("title") or "").strip(),
        "chunk_index": int(r.get("chunk_index") or 0),
        "text": str(meta.get("text") or "").strip(),
        "file_rel_path": str(meta.get("file_rel_path") or "").strip(),
        "file_name": str(meta.get("file_name") or "").strip(),
      }
    )
  return out


def _format_uploaded_rag_context(uploaded_docs: list[dict[str, Any]], start_index: int) -> tuple[str, dict[str, Any]]:
  ids: list[int] = []
  for d in uploaded_docs or []:
    try:
      rid = int((d or {}).get("rag_document_id") or 0)
    except Exception:
      rid = 0
    if rid > 0 and rid not in ids:
      ids.append(rid)
  if not ids:
    return "", {}

  out_map: dict[str, Any] = {}
  parts = ["TÀI LIỆU TẢI LÊN (trích):"]
  idx = start_index
  total = 0
  for rid in ids[:5]:
    chunks = _fetch_uploaded_rag_chunks(rid, max_chunks=4)
    for c in chunks:
      if total >= 10:
        break
      text = str(c.get("text") or "").strip()
      if not text:
        continue
      idx += 1
      total += 1
      cit_id = f"CIT-{idx:02d}"
      title = str(c.get("title") or c.get("file_name") or f"Tài liệu {rid}").strip()
      excerpt = _truncate(text, 520)
      parts.append(f"[[{cit_id}]] {title}".strip())
      parts.append(excerpt)
      parts.append("")
      out_map[cit_id] = {
        "citation_id": cit_id,
        "source_type": "rag_upload",
        "rag_document_id": int(c.get("rag_document_id") or rid),
        "title": title,
        "chunk_index": int(c.get("chunk_index") or 0),
        "excerpt": excerpt,
        "file_rel_path": str(c.get("file_rel_path") or "").strip(),
        "file_name": str(c.get("file_name") or "").strip(),
        "tool_type": "rag_upload",
      }
    if total >= 10:
      break
  return "\n".join(parts).strip(), out_map


def _deeptutor_web_search(query: str, provider: str | None) -> dict[str, Any]:
  q = (query or "").strip()
  if not q:
    return {"ok": False, "answer": "", "provider": "", "citations": [], "error": "empty_query"}
  _ensure_deeptutor_on_path()
  try:
    from src.tools.web_search import web_search
  except Exception as e:
    return {"ok": False, "answer": "", "provider": "", "citations": [], "error": f"deeptutor_import_failed: {e}"}
  try:
    res = web_search(q, provider=provider) if provider else web_search(q)
    data = asdict(res) if hasattr(res, "__dataclass_fields__") else (res.to_dict() if hasattr(res, "to_dict") else res)
    cits = data.get("citations") or []
    return {
      "ok": True,
      "provider": str(data.get("provider") or ""),
      "answer": str(data.get("answer") or ""),
      "citations": cits if isinstance(cits, list) else [],
    }
  except Exception as e:
    return {"ok": False, "answer": "", "provider": "", "citations": [], "error": str(e)}


def _infer_provider_from_model(model: str | None, current_provider: str | None) -> str | None:
    """If provider is auto but model is specific, try to infer provider to avoid mismatch"""
    if current_provider and current_provider.lower() != "auto":
        return current_provider
        
    m = (model or "").lower()
    if not m:
        return current_provider
        
    if "gpt" in m or "o1" in m or "o3" in m:
        return "openai"
    if "deepseek" in m:
        return "deepseek"
    if "gemini" in m:
        return "gemini"
        
    return current_provider


async def generate_principal_content_deeptutor(
  *,
  doc_ids: list[str],
  work_ids: list[int],
  user_request: str,
  preset_id: str | None,
  custom_prompt: str | None,
  use_rag: bool,
  use_web: bool,
  deep_research: bool,
  web_provider: str | None,
  make_podcast: bool,
  uploaded_rag_documents: list[dict[str, Any]] | None = None,
  model: str | None,
  provider: str | None,
  progress_callback: Callable[[str, dict[str, Any]], None | Awaitable[None]] | None = None,
) -> dict[str, Any]:
  import asyncio
  from app.services.core_ai_service import CoreAIService
  
  # Smart Model Selection
  reasoning_model = _resolve_smart_model(provider, model, task_type="reasoning")
  chat_model = _resolve_smart_model(provider, model, task_type="chat")
  
  # Infer provider to avoid sending specific model to wrong provider
  reasoning_provider = _infer_provider_from_model(reasoning_model, provider)
  chat_provider = _infer_provider_from_model(chat_model, provider)

  thinking: list[str] = []
  core_ai = CoreAIService(domain="MANAGEMENT")

  docs_data = core_ai._fetch_documents(doc_ids)
  works_data = core_ai._fetch_work_categories(work_ids)

  # Pre-fetch uploaded docs for IdeaGen context
  full_doc_texts = {}
  if docs_data:
      for d in docs_data:
          fp = str(d.get("file_path") or "").strip()
          if fp and os.path.exists(fp):
              try:
                  from app.services.ioffice_rag_ingest import _extract_text_from_file
                  txt = _extract_text_from_file(fp, selected_members=None)
                  if txt:
                      full_doc_texts[d['doc_id']] = txt
              except Exception:
                  pass

  # Phase 1: Create citations for FULL TEXT content if available
  # Instead of just "Doc ID", we chunk the full text so citations map to excerpts
  citations: dict[str, Any] = {}
  
  # List to hold all sources (both full-text chunks and RAG chunks)
  all_doc_sources: list[dict[str, Any]] = []
  
  for d in docs_data:
      did = str(d.get("doc_id") or "").strip()
      
      # If we have full text, split it into chunks and assign CIT IDs
      if full_doc_texts and did in full_doc_texts:
          txt = full_doc_texts[did]
          # Simple chunking: 1500 chars, overlapping 200
          chunk_size = 1500
          overlap = 200
          
          start = 0
          c_idx = 0
          while start < len(txt):
              end = min(start + chunk_size, len(txt))
              chunk_text = txt[start:end]
              
              # Adjust to nearest newline/space to avoid cutting words
              if end < len(txt):
                  last_space = chunk_text.rfind('\n')
                  if last_space == -1:
                      last_space = chunk_text.rfind(' ')
                  if last_space > chunk_size // 2: # Only cut if reasonable
                      end = start + last_space + 1
                      chunk_text = txt[start:end]
              
              cit_id = f"CIT-{len(all_doc_sources) + 1:02d}"
              
              source_item = {
                  "citation_id": cit_id,
                  "source_type": "ioffice_doc_chunk",
                  "doc_id": did,
                  "so_ky_hieu": d.get("so_ky_hieu"),
                  "trich_yeu": d.get("trich_yeu"),
                  "chunk_index": c_idx,
                  "excerpt": chunk_text, # This is the "trích đoạn" user wants
                  "score": 1.0, # Full text is definitely relevant
                  "tool_type": "document_full"
              }
              
              all_doc_sources.append(source_item)
              citations[cit_id] = source_item
              
              start = end - overlap
              c_idx += 1
              if start < 0: start = 0 # Safety
              
      else:
          # Doc too large for full text, rely on RAG/Search later
          # We'll handle this in the "selected_sources" step if not covered here
          pass

  # Pre-fetch uploaded docs for IdeaGen context
  ideagen_uploaded_context = ""
  if uploaded_rag_documents:
      ideagen_uploaded_context, _ = _format_uploaded_rag_context(list(uploaded_rag_documents or []), start_index=0)

  # Pre-fetch RAG context if enabled (moved up from Generation phase)
  thinking.append("RAG tương tác: truy hồi tri thức nội bộ (nếu bật).")
  await _emit(progress_callback, "RAG tương tác", "Đang truy hồi tri thức nội bộ…")
  rag_context = ""
  rag_sources = []
  if use_rag:
    try:
      rag_results = await core_ai._search_rag(user_request)
      rag_context = str(rag_results.get("content") or "")
      rag_sources = rag_results.get("sources") or []
    except Exception:
      rag_context = ""
      rag_sources = []
  await _emit(progress_callback, "RAG tương tác", "Hoàn tất RAG.", {"rag_has_content": bool(rag_context)})

  thinking.append("IdeaGen: phân rã yêu cầu và lập dàn ý.")
  await _emit(progress_callback, "IdeaGen", "Đang lập dàn ý và checklist…")

  base_context = core_ai._build_context_string(docs_data, works_data, rag_content=rag_context, selected_sources=all_doc_sources, full_doc_texts=full_doc_texts)
  if ideagen_uploaded_context:
      base_context += f"\n\n{ideagen_uploaded_context}"
  ideagen_user, ideagen_sys = _build_ideagen_prompt(user_request, base_context)
  ideagen_out, _ = await asyncio.to_thread(
    generate_text,
    ideagen_user,
    system_prompt=ideagen_sys,
    model=reasoning_model,
    provider=reasoning_provider,
    content_type="principal_ideagen",
  )
  ideagen_out = _clean_reasoning_output(str(ideagen_out or "").strip())
  await _emit(progress_callback, "IdeaGen", "Hoàn tất IdeaGen.", {"ideagen": ideagen_out})

  questions = _extract_questions(ideagen_out)
  if questions:
    # Auto-research logic: try to answer questions using Deep Research instead of asking user immediately
    if deep_research and use_web:
        thinking.append("Tự động nghiên cứu: tìm câu trả lời cho các điểm chưa rõ.")
        await _emit(progress_callback, "Nghiên cứu chuyên sâu", "Đang tự tìm câu trả lời cho các câu hỏi thiếu...", {"auto_research": True})
        
        research_context_parts = []
        all_research_cits = []
        
        # Limit to first 3 questions to save time
        for q_idx, q_text in enumerate(questions[:3]):
            await _emit(progress_callback, "Nghiên cứu chuyên sâu", f"Đang tìm hiểu: {q_text}")
            # Web search usually uses simple queries, keep using default logic
            r = await asyncio.to_thread(_deeptutor_web_search, q_text, web_provider)
            ans = str(r.get("answer") or "").strip()
            if ans:
                research_context_parts.append(f"Q: {q_text}\nA: {ans}")
            c = r.get("citations") if isinstance(r.get("citations"), list) else []
            all_research_cits.extend(c)
            
        if research_context_parts:
            # Re-run IdeaGen with research results
            thinking.append("Cập nhật IdeaGen với thông tin mới tìm được.")
            research_context = "\n\n".join(research_context_parts)
            
            # QUAN TRỌNG: Cập nhật prompt IdeaGen lần 2 với kết quả nghiên cứu
            # Phải nói rõ cho AI biết là "Đã tìm thấy thông tin bổ sung, hãy cập nhật dàn ý và bỏ qua các câu hỏi đã được trả lời"
            updated_sys = (
                ideagen_sys + 
                "\n\nTHÔNG TIN BỔ SUNG TỪ NGHIÊN CỨU:\n"
                "Hệ thống đã tự động tìm kiếm câu trả lời cho các câu hỏi làm rõ.\n"
                "Nhiệm vụ của bạn: Dựa trên kết quả nghiên cứu dưới đây, hãy CẬP NHẬT lại dàn ý và checklist.\n"
                "QUAN TRỌNG: Nếu câu hỏi đã có câu trả lời trong kết quả nghiên cứu, HÃY XÓA NÓ khỏi danh sách 'Câu hỏi làm rõ'.\n"
                "Chỉ giữ lại những câu hỏi thực sự chưa có thông tin."
            )
            
            updated_user = (
                f"{ideagen_user}\n\n"
                f"KẾT QUẢ NGHIÊN CỨU TỰ ĐỘNG:\n{research_context}"
            )

            ideagen_out_2, _ = await asyncio.to_thread(
                generate_text,
                updated_user,
                system_prompt=updated_sys,
                model=reasoning_model,
                provider=reasoning_provider,
                content_type="principal_ideagen_retry",
            )
            ideagen_out = _clean_reasoning_output(str(ideagen_out_2 or "").strip())
            
            # Re-extract questions (AI should have removed answered questions)
            questions = _extract_questions(ideagen_out)
            
            # Merge citations
            _, web_cits = _format_web_context(all_research_cits, start_index=len(citations))
            citations.update(web_cits)

  if questions:
    thinking.append("Cần xác nhận: yêu cầu người dùng làm rõ trước khi tiếp tục.")
    await _emit(progress_callback, "Cần xác nhận", "Cần bạn trả lời để tiếp tục.", {"need_user_input": True, "questions": questions})
    return {
      "ok": True,
      "need_user_input": True,
      "questions": questions,
      "ideagen": ideagen_out,
      "text": "",
      "citations": {},
      "web": {"ok": False, "answer": "", "provider": "", "citations": [], "error": ""},
      "podcast_script": "",
      "thinking": "\n".join(thinking),
    }
  
  # RAG is already done before IdeaGen, so we just skip it here
  # but keep the thinking log for consistency or remove it if redundant.
  # Let's keep a small log saying we use the pre-fetched RAG.
  if use_rag and rag_context:
      thinking.append("RAG tương tác: Sử dụng kết quả đã truy vấn từ bước trước.")
      await _emit(progress_callback, "RAG tương tác", "Sử dụng tri thức đã truy hồi.", {"rag_cached": True})

  thinking.append("Trích dẫn: chọn đoạn liên quan từ văn bản đã chọn.")
  await _emit(progress_callback, "Trích dẫn", "Đang chọn trích đoạn từ văn bản đã chọn…")
  
  # Only generate chunks if we don't have full text (or to supplement it)
  # But we must continue citation numbering
  current_cit_idx = len(citations)
  
  # If we already have full text chunks in all_doc_sources, we might not need selected_sources unless docs were skipped
  docs_needing_search = []
  for d in docs_data:
      did = str(d.get("doc_id") or "").strip()
      # If this doc was NOT in full_doc_texts (i.e. too big), we need to search it
      if not (full_doc_texts and did in full_doc_texts):
          docs_needing_search.append(d)
          
  selected_sources = []
  if docs_needing_search:
      selected_sources = core_ai._build_selected_doc_sources(docs_needing_search, user_request)
  
  # Re-assign CIT IDs for selected chunks to follow document IDs
  for s in selected_sources:
      current_cit_idx += 1
      cit_id = f"CIT-{current_cit_idx:02d}"
      s["citation_id"] = cit_id
      
      citations[cit_id] = {
        "citation_id": cit_id,
        "source_type": "ioffice_selected_doc",
        "doc_id": s.get("doc_id"),
        "so_ky_hieu": s.get("so_ky_hieu") or "",
        "trich_yeu": s.get("trich_yeu") or "",
        "chunk_index": s.get("chunk_index"),
        "excerpt": s.get("excerpt") or "",
        "context_before": s.get("context_before") or "",
        "context_after": s.get("context_after") or "",
        "link_goc": s.get("link_goc") or "",
        "score": s.get("score"),
      }
      
  # IMPORTANT: We must merge all_doc_sources and selected_sources for final context
  final_sources_for_generation = all_doc_sources + selected_sources
  
  await _emit(progress_callback, "Trích dẫn", f"Đã tạo {len(citations)} trích dẫn từ văn bản đã chọn.", {"citations_count": len(citations)})

  uploaded_context = ""
  if uploaded_rag_documents:
    thinking.append("Tài liệu tải lên: trích đoạn và đưa vào ngữ cảnh.")
    await _emit(progress_callback, "RAG tương tác", "Đang nạp tài liệu tải lên…")
    uploaded_context, upload_cits = _format_uploaded_rag_context(list(uploaded_rag_documents or []), start_index=len(citations))
    citations.update(upload_cits)
    await _emit(progress_callback, "RAG tương tác", "Hoàn tất nạp tài liệu tải lên.", {"upload_citations": len(upload_cits)})

  thinking.append("Web-search: mở rộng căn cứ (nếu bật và có API key).")
  await _emit(progress_callback, "Web-search", "Đang tìm web…")
  web = {"ok": False, "answer": "", "provider": "", "citations": [], "error": ""}
  web_context = ""
  if use_web:
    if deep_research:
      thinking.append("Nghiên cứu chuyên sâu: tách câu hỏi và tổng hợp nhiều nguồn.")
      await _emit(progress_callback, "Nghiên cứu chuyên sâu", "Đang tạo câu hỏi nghiên cứu…")
      rq_sys = (
        "Bạn là trợ lý nghiên cứu. Hãy tạo 3-6 truy vấn web ngắn, cụ thể.\n"
        "Yêu cầu: tiếng Việt, ưu tiên văn bản quy định/nguồn chính thống.\n"
        "Chỉ trả về danh sách gạch đầu dòng, mỗi dòng 1 truy vấn."
      )
      rq_user = f"YÊU CẦU:\n{user_request}\n\nIDEAGEN:\n{ideagen_out or '—'}\n"
      q_text, _ = await asyncio.to_thread(generate_text, rq_user, system_prompt=rq_sys, model=reasoning_model, provider=reasoning_provider, content_type="principal_research_queries")
      q_text = _clean_reasoning_output(str(q_text or "").strip())
      lines = [ln.strip().lstrip("-•* ").strip() for ln in q_text.splitlines()]
      queries = [ln for ln in lines if ln]
      if len(queries) > 6:
        queries = queries[:6]
      if not queries:
        queries = [user_request]
      await _emit(progress_callback, "Nghiên cứu chuyên sâu", f"Đang tìm {len(queries)} truy vấn…", {"research_queries": len(queries)})
      all_cits: list[dict[str, Any]] = []
      provider_used = ""
      answer_parts: list[str] = []
      for qi, q in enumerate(queries, start=1):
        await _emit(progress_callback, "Nghiên cứu chuyên sâu", f"Tìm web {qi}/{len(queries)}…")
        r = await asyncio.to_thread(_deeptutor_web_search, q, web_provider)
        if r.get("provider"):
          provider_used = str(r.get("provider") or "")
        c = r.get("citations") if isinstance(r.get("citations"), list) else []
        all_cits.extend(c)
        a = str(r.get("answer") or "").strip()
        if a:
          answer_parts.append(a)
      web = {"ok": True, "answer": "\n\n".join(answer_parts).strip(), "provider": provider_used, "citations": all_cits, "error": ""}
      web_context, web_cits = _format_web_context(all_cits, start_index=len(citations))
      citations.update(web_cits)
      await _emit(progress_callback, "Nghiên cứu chuyên sâu", "Hoàn tất nghiên cứu chuyên sâu.", {"web_citations": len(all_cits)})
    else:
      web = await asyncio.to_thread(_deeptutor_web_search, user_request, web_provider)
      web_context, web_cits = _format_web_context(web.get("citations") or [], start_index=len(citations))
      citations.update(web_cits)
  await _emit(
    progress_callback,
    "Web-search",
    "Hoàn tất web search." if use_web else "Bỏ qua web search.",
    {"web_ok": bool(web.get("ok")), "web_provider": web.get("provider") or "", "web_citations": len(web.get("citations") or [])},
  )

  thinking.append("Tổng hợp: soạn thảo nội dung có trích dẫn.")
  await _emit(progress_callback, "Tổng hợp", "Đang soạn thảo nội dung…")
  system_prompt = core_ai._get_system_prompt(preset_id, custom_prompt)
  system_prompt += _build_admin_writing_policy()
  system_prompt += (
    "\n\nQUY ĐỊNH TRÍCH DẪN:\n"
    "- Khi sử dụng thông tin từ phần TRÍCH DẪN hoặc NGUỒN WEB, bắt buộc chèn đúng mã [[CIT-XX]] tương ứng ngay sau câu.\n"
    "- Chỉ dùng mã trích dẫn đã xuất hiện.\n"
    "- Nếu không có căn cứ trong trích dẫn/nguồn web, hãy ghi [cần kiểm chứng] thay vì khẳng định."
  )

  full_context = core_ai._build_context_string(docs_data, works_data, rag_content=rag_context, selected_sources=final_sources_for_generation, full_doc_texts=full_doc_texts)
  if uploaded_context:
    full_context = (full_context + "\n\n" + uploaded_context).strip()
  if web_context:
    full_context = (full_context + "\n\n" + web_context).strip()

  user_text = (
    f"YÊU CẦU:\n{user_request}\n\n"
    f"DÀN Ý & CHECKLIST (IdeaGen):\n{ideagen_out or '—'}\n\n"
    f"NGỮ CẢNH:\n{full_context}"
  ).strip()

  out, model_used = await asyncio.to_thread(
    generate_text,
    user_text,
    system_prompt=system_prompt,
    model=chat_model,
    provider=chat_provider,
    content_type="principal_generate",
  )
  out = str(out or "").strip()
  await _emit(progress_callback, "Tổng hợp", "Hoàn tất nội dung.", {"model": model_used})

  podcast = ""
  if make_podcast:
    thinking.append("Podcast: tạo kịch bản tóm tắt dễ nghe.")
    await _emit(progress_callback, "Podcast", "Đang tạo kịch bản podcast…")
    p_user, p_sys = _build_podcast_prompt(out)
    p_out, _ = await asyncio.to_thread(
      generate_text,
      p_user,
      system_prompt=p_sys,
      model=chat_model,
      provider=chat_provider,
      content_type="principal_podcast",
    )
    podcast = str(p_out or "").strip()
    await _emit(progress_callback, "Podcast", "Hoàn tất kịch bản podcast.", {"podcast_len": len(podcast)})
  else:
    await _emit(progress_callback, "Podcast", "Bỏ qua podcast.")

  return {
    "ok": True,
    "text": out,
    "model": model_used,
    "citations": citations,
    "ideagen": ideagen_out,
    "rag": {"content": rag_context, "sources": rag_sources},
    "web": web,
    "podcast_script": podcast,
    "thinking": "\n".join(thinking),
  }


async def generate_principal_content_deeptutor_stream(
  *,
  doc_ids: list[str],
  work_ids: list[int],
  user_request: str,
  preset_id: str | None,
  custom_prompt: str | None,
  use_rag: bool,
  use_web: bool,
  deep_research: bool,
  web_provider: str | None,
  make_podcast: bool,
  uploaded_rag_documents: list[dict[str, Any]] | None = None,
  model: str | None,
  provider: str | None,
) -> AsyncGenerator[dict[str, Any], None]:
  import asyncio
  import time

  q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

  async def on_progress(stage: str, payload: dict[str, Any]):
    await q.put({"type": "progress", **payload})

  await q.put({"type": "progress", "stage": "Bắt đầu", "message": "Chuẩn bị chạy đa tác nhân…"})

  task = asyncio.create_task(
    generate_principal_content_deeptutor(
      doc_ids=doc_ids,
      work_ids=work_ids,
      user_request=user_request,
      preset_id=preset_id,
      custom_prompt=custom_prompt,
      use_rag=use_rag,
      use_web=use_web,
      deep_research=deep_research,
      web_provider=web_provider,
      make_podcast=make_podcast,
      uploaded_rag_documents=uploaded_rag_documents,
      model=model,
      provider=provider,
      progress_callback=on_progress,
    )
  )

  last_heartbeat = time.monotonic()
  while True:
    if task.done() and q.empty():
      break
    try:
      item = await asyncio.wait_for(q.get(), timeout=0.25)
      last_heartbeat = time.monotonic()
      yield item
    except asyncio.TimeoutError:
      now = time.monotonic()
      if now - last_heartbeat >= 2.0:
        last_heartbeat = now
        yield {"type": "heartbeat"}
      continue

  res = await task
  yield {"type": "final", "result": res}
