
import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.db import get_db_connection
from app.services.document_categories_repo import DocumentCategoriesRepo
from app.services.embedding_client import embed_text_query, embed_texts_typed
from app.services.llm_client import generate_text

# Add DeepTutor to sys.path to allow importing its services
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEEPTUTOR_ROOT = PROJECT_ROOT / "apps" / "DeepTutor"
if str(DEEPTUTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(DEEPTUTOR_ROOT))

try:
    from src.agents.research.utils.citation_manager import CitationManager
    from src.services.rag.service import RAGService
except ImportError as e:
    print(f"Warning: DeepTutor components not fully available: {e}")
    # Fallback if DeepTutor is not fully available
    class CitationManager:
        def __init__(self, id, dir):
            self._citations = {}
        def get_next_citation_id(self, stage="research", block_id=""):
            return f"CIT-{len(self._citations) + 1:02d}"
        def add_citation(self, id, type, trace, answer):
            self._citations[id] = {
                "citation_id": id,
                "tool_type": type,
                "query": getattr(trace, 'query', ''),
                "summary": getattr(trace, 'summary', ''),
                "timestamp": getattr(trace, 'timestamp', datetime.now().isoformat())
            }
        def get_all_citations(self):
            return self._citations.copy()
    RAGService = None

class CoreAIService:
    """
    Core AI Engine for EduAI Hub.
    Integrates iOffice data, Work Categories, and RAG Knowledge.
    Uses Multi-agent patterns and Citation System from DeepTutor.
    """

    def __init__(self, domain: str = "MANAGEMENT"):
        self.domain = domain.upper()
        self.categories_repo = DocumentCategoriesRepo()
        self._rag_service = None
        self.session_id = f"core_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.cache_dir = PROJECT_ROOT / "cache" / self.session_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.citation_manager = CitationManager(self.session_id, self.cache_dir)

    def _get_rag_service(self):
        """Lazy load RAGService from DeepTutor"""
        if self._rag_service is None:
            if RAGService:
                self._rag_service = RAGService()
            else:
                self._rag_service = False
        return self._rag_service

    async def generate_content(
        self,
        doc_ids: List[str],
        work_ids: List[int],
        user_request: str,
        preset_id: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        use_rag: bool = True,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Multi-agent workflow to generate content with precise citations.
        """
        # Phase 1: Context Collection
        docs_data = self._fetch_documents(doc_ids)
        works_data = self._fetch_work_categories(work_ids)
        
        rag_context = ""
        rag_sources = []
        if use_rag:
            rag_results = await self._search_rag(user_request)
            rag_context = rag_results.get("content", "")
            rag_sources = rag_results.get("sources", [])

        # Phase 2: Citation Preparation (trích đúng từ văn bản đã chọn)
        citations: Dict[str, Any] = {}
        # Changed: Ưu tiên đọc full text cho văn bản chọn (nếu <= 100k ký tự) để đưa vào context
        # thay vì chỉ RAG. Chỉ RAG khi văn bản quá dài.
        selected_sources = []
        full_doc_texts = {}
        
        if docs_data:
            # Check total length
            total_len = 0
            temp_texts = {}
            for d in docs_data:
                fp = str(d.get("file_path") or "").strip()
                if fp:
                    try:
                        from app.services.ioffice_rag_ingest import _extract_text_from_file
                        txt = _extract_text_from_file(fp, selected_members=None)
                        if txt:
                            temp_texts[d['doc_id']] = txt
                            total_len += len(txt)
                    except Exception:
                        pass
            
            # Nếu tổng độ dài < 120k ký tự (khoảng 30-40k token), dùng full text
            if total_len < 120000:
                full_doc_texts = temp_texts
            else:
                # Nếu quá dài, fallback về RAG tìm đoạn liên quan
                selected_sources = self._build_selected_doc_sources(docs_data, user_request)

        for s in selected_sources:
            citations[str(s.get("citation_id"))] = {
                "citation_id": s.get("citation_id"),
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

        # Phase 3: Generation
        system_prompt = self._get_system_prompt(preset_id, custom_prompt)
        # Add instruction for citations
        if selected_sources:
            system_prompt += "\n\nQUY ĐỊNH TRÍCH DẪN:\n- Khi sử dụng thông tin từ phần TRÍCH DẪN, bắt buộc chèn đúng mã [[CIT-XX]] tương ứng ngay sau câu.\n- Chỉ dùng mã trích dẫn đã xuất hiện trong phần TRÍCH DẪN.\n- Nếu không thấy căn cứ trong TRÍCH DẪN, hãy nói rõ “không có căn cứ trong tài liệu đã chọn”."
        
        full_context = self._build_context_string(docs_data, works_data, rag_context, selected_sources, full_doc_texts)
        user_text = f"YÊU CẦU:\n{user_request}\n\nNGỮ CẢNH:\n{full_context}".strip()

        out, model_used = generate_text(user_text, system_prompt=system_prompt, model=model, provider=provider, content_type="ioffice_generate")
        
        # Phase 4: Finalize
        return {
            "ok": True,
            "text": out,
            "model": model_used,
            "session_id": self.session_id,
            "docs_used": [d['doc_id'] for d in docs_data],
            "works_used": [w['id'] for w in works_data],
            "citations": citations
        }

    def _build_selected_doc_sources(self, docs: List[Dict[str, Any]], user_request: str) -> List[Dict[str, Any]]:
        try:
            from app.services.ioffice_rag_ingest import _extract_text_from_file, _chunk_text, _chunking_cfg, FulltextChunkingConfig
        except Exception:
            return []

        q = (user_request or "").strip()
        if not q:
            return []

        try:
            query_vec, _ = embed_text_query(q)
        except Exception:
            return []

        def dot(a: list[float], b: list[float]) -> float:
            s = 0.0
            for x, y in zip(a, b):
                s += float(x) * float(y)
            return s

        def norm(a: list[float]) -> float:
            s = 0.0
            for x in a:
                s += float(x) * float(x)
            return s ** 0.5

        qn = norm(query_vec) or 1.0

        candidates: List[Dict[str, Any]] = []
        base_cfg = _chunking_cfg()
        total_docs = len(docs)
        words = len([x for x in q.split() if x.strip()])
        target_total = max(3, min(20, max(total_docs * 3, 3 + int(words / 6))))

        for d in docs:
            did = str(d.get("doc_id") or "").strip()
            if not did:
                continue
            file_path = str(d.get("file_path") or "").strip()
            text = _extract_text_from_file(file_path, selected_members=None) if file_path else ""
            
            # Fallback to summary if text extraction failed or empty
            if not text or len(text) < 50:
                text = str(d.get("ai_summary") or d.get("summary_text") or "").strip()
                
            if not text or len(text) < 20:
                continue

            cfg = base_cfg
            auto_chunking = (os.getenv("EDUAI_IOFFICE_RAG_AUTO_CHUNKING") or "1").strip().lower() not in ("0", "false", "no", "off")
            if auto_chunking and not str(os.getenv("EDUAI_IOFFICE_RAG_CHUNK_CHARS") or "").strip():
                total_chars = len(text)
                target_k = int((total_chars / 20000.0) + 3)
                if target_k < 3:
                    target_k = 3
                if target_k > 20:
                    target_k = 20
                chunk_chars = int(total_chars / max(1, target_k))
                if chunk_chars < 700:
                    chunk_chars = 700
                if chunk_chars > 4000:
                    chunk_chars = 4000
                overlap_chars = int(chunk_chars * 0.18)
                if overlap_chars < 80:
                    overlap_chars = 80
                if overlap_chars > 800:
                    overlap_chars = 800
                cfg = FulltextChunkingConfig(
                    chunk_chars=chunk_chars,
                    overlap_chars=overlap_chars,
                    min_chunk_chars=cfg.min_chunk_chars,
                    max_total_chars=cfg.max_total_chars,
                )

            chunks = _chunk_text(text, cfg)
            if not chunks:
                continue

            per_doc_cap = max(1, min(12, int(target_total / max(1, total_docs)) + 2))
            try:
                vecs, _ = embed_texts_typed(chunks, input_type="document")
            except Exception:
                continue

            scored: List[tuple[int, float]] = []
            for idx, v in enumerate(vecs):
                if not v:
                    continue
                vn = norm(v) or 1.0
                sc = dot(query_vec, v) / (qn * vn)
                scored.append((idx, float(sc)))
            scored.sort(key=lambda x: x[1], reverse=True)
            picked = scored[:per_doc_cap]
            for idx, sc in picked:
                chunk_text = chunks[idx]
                excerpt = chunk_text.strip()
                if len(excerpt) > 1200:
                    excerpt = excerpt[:1200].rstrip() + "…"
                before = chunks[idx - 1].strip() if idx > 0 else ""
                after = chunks[idx + 1].strip() if idx + 1 < len(chunks) else ""
                if len(before) > 800:
                    before = "…" + before[-800:].lstrip()
                if len(after) > 800:
                    after = after[:800].rstrip() + "…"
                candidates.append(
                    {
                        "doc_id": did,
                        "so_ky_hieu": d.get("so_ky_hieu") or "",
                        "trich_yeu": d.get("trich_yeu") or "",
                        "link_goc": d.get("link_goc") or "",
                        "chunk_index": int(idx),
                        "excerpt": excerpt,
                        "context_before": before,
                        "context_after": after,
                        "score": sc,
                    }
                )

        candidates.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        if not candidates:
            return []

        out: List[Dict[str, Any]] = []
        per_doc_first: Dict[str, bool] = {}
        for c in candidates:
            if len(out) >= target_total:
                break
            did = str(c.get("doc_id") or "")
            if did and did not in per_doc_first:
                out.append(c)
                per_doc_first[did] = True
        if len(out) < target_total:
            for c in candidates:
                if len(out) >= target_total:
                    break
                if c in out:
                    continue
                out.append(c)

        for i, c in enumerate(out, start=1):
            c["citation_id"] = f"CIT-{i:02d}"
        return out

    async def _fetch_deep_doc_content(self, doc_ids: List[str]) -> Dict[str, str]:
        """Fetch actual content chunks from RAG for specific documents"""
        rag = self._get_rag_service()
        if not rag or rag is True:
            return {}
        
        results = {}
        for did in doc_ids:
            try:
                # Search specifically for chunks belonging to this document
                search_res = await rag.search(
                    query=f"Nội dung chi tiết của văn bản {did}", 
                    kb_name="RAG_MANAGEMENT",
                    mode="hybrid",
                    limit=5
                )
                if search_res.get("content"):
                    results[did] = search_res["content"]
            except Exception:
                continue
        return results

    def _fetch_documents(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        if not doc_ids:
            return []
        placeholders = ",".join(["%s"] * len(doc_ids))
        summary_col = "summary_text"
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SHOW COLUMNS FROM ioffice_documents")
                    cols = [str((r or {}).get("Field") or "") for r in (cur.fetchall() or []) if isinstance(r, dict)]
            if "summary_text" not in cols and "ai_summary" in cols:
                summary_col = "ai_summary"
        except Exception:
            summary_col = "summary_text"
        sql = f"""
            SELECT ioffice_doc_id AS doc_id, so_ky_hieu, trich_yeu, don_vi_ban_hanh, link_goc, file_path, {summary_col} AS ai_summary
            FROM ioffice_documents
            WHERE ioffice_doc_id IN ({placeholders})
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(doc_ids))
                return list(cur.fetchall() or [])

    def _fetch_work_categories(self, work_ids: List[int]) -> List[Dict[str, Any]]:
        if not work_ids:
            return []
        placeholders = ",".join(["%s"] * len(work_ids))
        sql = f"SELECT id, name, description FROM document_categories WHERE id IN ({placeholders})"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(work_ids))
                return list(cur.fetchall() or [])

    async def _search_rag(self, query: str) -> Dict[str, Any]:
        rag = self._get_rag_service()
        if not rag or rag is True: # False or True (if failed to load)
            return {"content": "", "sources": []}
        
        collection_map = {
            "MANAGEMENT": "RAG_MANAGEMENT",
            "TEACHING": "RAG_TEACHING",
            "LEARNING": "RAG_LEARNING"
        }
        kb_name = collection_map.get(self.domain, "RAG_MANAGEMENT")
        
        try:
            return await rag.search(query, kb_name=kb_name, mode="hybrid")
        except Exception as e:
            print(f"RAG search error: {e}")
            return {"content": "", "sources": []}

    def _get_system_prompt(self, preset_id: Optional[str], custom_prompt: Optional[str]) -> str:
        if custom_prompt:
            return custom_prompt
        from app.services.ioffice_prompt_store import list_prompt_presets
        presets = {str(p.get("id")): str(p.get("prompt") or "") for p in (list_prompt_presets() or []) if isinstance(p, dict) and p.get("id")}
        return presets.get(preset_id) or "Bạn là trợ lý AI thông minh hỗ trợ quản lý văn administrative và giáo dục."

    def _build_context_string(self, docs: List[Dict], works: List[Dict], rag_content: str, selected_sources: List[Dict[str, Any]] | None = None, full_doc_texts: Dict[str, str] | None = None) -> str:
        parts = []
        if docs:
            parts.append("1. VĂN BẢN ĐÃ CHỌN:")
            for d in docs:
                did = str(d.get("doc_id") or "").strip()
                cit_tag = f"[[{d['citation_id']}]] " if d.get("citation_id") else ""
                parts.append(f"- {cit_tag}DOC_ID: {did}")
                parts.append(f"  Số ký hiệu: {d.get('so_ky_hieu')}")
                parts.append(f"  Trích yếu: {d.get('trich_yeu')}")
                
                content_found = False
                # Ưu tiên nội dung đầy đủ
                if full_doc_texts and did in full_doc_texts:
                    txt = full_doc_texts[did]
                    if len(txt) > 200000: # Truncate if too long to avoid context overflow
                        txt = txt[:200000] + "...(đã cắt bớt)"
                    parts.append(f"  NỘI DUNG VĂN BẢN {did}:\n{txt}")
                    content_found = True
                
                # Fallback: Nếu không có full text, dùng tóm tắt AI (nếu có)
                if not content_found:
                    summ = str(d.get("ai_summary") or d.get("summary_text") or "").strip()
                    if summ:
                        parts.append(f"  TÓM TẮT VĂN BẢN (tự động):\n{summ}")
                        content_found = True
                
                if not content_found:
                    parts.append("  (Cảnh báo: Không lấy được nội dung chi tiết file đính kèm. Hãy dựa vào Trích yếu và Tri thức RAG).")
            parts.append("")

        sources = selected_sources or []
        if sources:
            parts.append("2. TRÍCH DẪN (trích từ văn bản đã chọn):")
            for s in sources:
                parts.append(f"[[{s.get('citation_id')}]] DOC_ID={s.get('doc_id')} | {s.get('so_ky_hieu') or ''} | chunk={s.get('chunk_index')}")
                parts.append(str(s.get("excerpt") or "").strip())
                parts.append("")

        if works:
            parts.append("3. CÔNG VIỆC LIÊN QUAN (Nghiệp vụ):")
            for w in works:
                parts.append(f"- [{w['name']}]: {w.get('description') or 'Không có mô tả'}")
            parts.append("")

        if rag_content:
            parts.append("4. TRI THỨC BỔ SUNG TỪ KHO RAG:")
            parts.append(rag_content)
            parts.append("")
            
        return "\n".join(parts).strip()

    def _search_ioffice_qdrant(self, query: str, *, limit: int = 8) -> Dict[str, Any]:
        from app.services.embedding_client import embedding_available, embed_text_query
        from app.services.qdrant_rest import QdrantRestClient
        from app.services.rag_conventions import collection_for_domain

        q = (query or "").strip()
        if not q:
            return {"content": "", "hits": []}
        if not embedding_available():
            return {"content": "", "hits": []}

        vector, _ = embed_text_query(q)
        col = collection_for_domain(self.domain)
        qdrant = QdrantRestClient()
        filter_ = {
            "must": [
                {"key": "domain", "match": {"value": self.domain}},
                {"key": "source", "match": {"value": "IOFFICE"}},
                {"key": "type", "match": {"any": ["official_document_chunk", "official_document_summary"]}},
            ]
        }
        hits = qdrant.search_points(collection=col, vector=vector, limit=int(limit), filter_=filter_, with_payload=True)
        if not hits:
            return {"content": "", "hits": []}

        point_ids: list[str] = []
        meta_by_pid: dict[str, dict] = {}
        for h in hits:
            pid = str(h.get("id") or "").strip()
            if pid:
                point_ids.append(pid)

        if point_ids:
            placeholders = ",".join(["%s"] * len(point_ids))
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT qdrant_point_id, metadata FROM rag_items WHERE deleted_at IS NULL AND qdrant_point_id IN ({placeholders})",
                        tuple(point_ids),
                    )
                    rows = cur.fetchall() or []
            for r in rows:
                pid = str(r.get("qdrant_point_id") or "").strip()
                raw = r.get("metadata") or ""
                try:
                    meta_by_pid[pid] = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
                except Exception:
                    meta_by_pid[pid] = {}

        out_hits = []
        lines = []
        for i, h in enumerate(hits[: int(limit)], start=1):
            payload = h.get("payload") if isinstance(h, dict) else None
            if not isinstance(payload, dict):
                payload = {}
            pid = str(h.get("id") or "").strip()
            oid = str(payload.get("original_id") or "").strip()
            typ = str(payload.get("type") or "").strip()
            try:
                score = float(h.get("score") or 0.0)
            except Exception:
                score = 0.0
            meta = meta_by_pid.get(pid) or {}
            snippet = str(meta.get("text") or "").strip()
            if not snippet and typ == "official_document_summary":
                snippet = str(payload.get("title") or "").strip()
            out_hits.append({"point_id": pid, "original_id": oid, "type": typ, "score": score, "snippet": snippet})
            if snippet:
                lines.append(f"[{i}] score={score:.3f} {oid} ({typ})")
                lines.append(snippet[:700])
                lines.append("")
        return {"content": "\n".join(lines).strip(), "hits": out_hits}
