import asyncio
import os
from typing import Any, Dict

from .base import BaseEmbeddingAdapter, EmbeddingRequest, EmbeddingResponse


class SentenceTransformersEmbeddingAdapter(BaseEmbeddingAdapter):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._model = None
        self._lock = asyncio.Lock()

    def _pick_device(self) -> str:
        raw = (os.getenv("EMBEDDING_DEVICE") or "auto").strip().lower()
        if raw and raw != "auto":
            return raw
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _load_model(self):
        from sentence_transformers import SentenceTransformer

        model_name = self.model
        if not model_name:
            raise ValueError("EMBEDDING_MODEL not set for sentence_transformers")
        device = self._pick_device()
        self._model = SentenceTransformer(model_name, device=device)
        try:
            dim = int(getattr(self._model, "get_sentence_embedding_dimension")())
            self.dimensions = dim
        except Exception:
            pass

    async def _ensure_model(self):
        if self._model is not None:
            return
        async with self._lock:
            if self._model is None:
                await asyncio.to_thread(self._load_model)

    def _encode(self, texts, input_type: str | None):
        batch_size = int((os.getenv("EMBEDDING_BATCH_SIZE") or "32").strip() or "32")
        if batch_size < 1:
            batch_size = 1
        if batch_size > 256:
            batch_size = 256

        normalize = (os.getenv("EMBEDDING_NORMALIZED") or "true").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        model_name = (self.model or "").lower()
        if "e5" in model_name:
            prefix = None
            if input_type:
                t = input_type.lower()
                if "query" in t:
                    prefix = "query: "
                elif "passage" in t or "document" in t:
                    prefix = "passage: "
            if prefix:
                texts = [prefix + (t or "") for t in texts]

        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=normalize,
        )
        try:
            vecs = vecs.tolist()
        except Exception:
            vecs = [list(v) for v in vecs]
        return vecs

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        await self._ensure_model()
        texts = [(t or "").strip() for t in (request.texts or [])]
        texts = [t for t in texts if t]
        if not texts:
            raise ValueError("Empty texts")

        vecs = await asyncio.to_thread(self._encode, texts, request.input_type)
        dims = int(self.dimensions or (len(vecs[0]) if vecs and vecs[0] else 0) or 0)

        return EmbeddingResponse(
            embeddings=vecs,
            model=self.model,
            dimensions=dims,
            usage={"input_texts": len(texts)},
        )

    def get_model_info(self) -> Dict[str, Any]:
        return {"provider": "sentence_transformers", "model": self.model, "dimensions": self.dimensions, "device": self._pick_device()}

