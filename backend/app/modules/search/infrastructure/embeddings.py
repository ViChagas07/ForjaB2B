"""Provedor de embeddings local (ONNX Runtime) - unico ponto que conhece o modelo.

As dependencias de runtime (``onnxruntime``, ``tokenizers``, ``numpy``) sao
importadas de forma preguica: se ausentes, ``build_embedding_provider`` devolve
``None`` e a busca segue lexical (modo real informado na resposta). O modelo e
carregado uma vez no ciclo de vida da aplicacao e a inferencia roda em thread
(``asyncio.to_thread``), sem bloquear o event loop.
"""

from __future__ import annotations

import asyncio
import importlib
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.search.application.ports import EmbeddingProvider

_logger = get_logger(__name__)

_DOCUMENT_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


def mean_pool_normalize(
    token_vectors: Sequence[Sequence[float]], mask: Sequence[int]
) -> list[float]:
    """Media dos tokens ativos + normalizacao L2 (pura, sem dependencias)."""
    if not token_vectors:
        return []
    dim = len(token_vectors[0])
    summed = [0.0] * dim
    count = 0
    for vector, keep in zip(token_vectors, mask, strict=True):
        if not keep:
            continue
        count += 1
        for index, value in enumerate(vector):
            summed[index] += value
    if count:
        summed = [value / count for value in summed]
    norm = math.sqrt(sum(value * value for value in summed)) or 1.0
    return [value / norm for value in summed]


class OnnxEmbeddingProvider:
    """Provedor ONNX local (E5): prefixos ``passage:``/``query:``, vetores normalizados."""

    def __init__(
        self,
        *,
        session: Any,
        tokenizer: Any,
        model: str,
        dimension: int,
        batch_size: int,
    ) -> None:
        self._session = session
        self._tokenizer = tokenizer
        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed, _DOCUMENT_PREFIX, list(texts))

    async def embed_query(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(self._embed, _QUERY_PREFIX, [text])
        return vectors[0] if vectors else []

    def _embed(self, prefix: str, texts: list[str]) -> list[list[float]]:
        numpy: Any = importlib.import_module("numpy")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = [prefix + text for text in texts[start : start + self._batch_size]]
            encodings = self._tokenizer.encode_batch(batch)
            attention = numpy.array([item.attention_mask for item in encodings], dtype=numpy.int64)
            inputs = {
                "input_ids": numpy.array([item.ids for item in encodings], dtype=numpy.int64),
                "attention_mask": attention,
                "token_type_ids": numpy.array(
                    [item.type_ids for item in encodings], dtype=numpy.int64
                ),
            }
            outputs = self._session.run(None, inputs)
            token_vectors = outputs[0]
            for row_index, mask in enumerate(attention.tolist()):
                vectors.append(mean_pool_normalize(token_vectors[row_index].tolist(), mask))
        return vectors


def build_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Constroi o provedor ONNX; ``None`` quando desabilitado ou indisponivel."""
    if not settings.embeddings_enabled:
        return None
    model_dir = Path(settings.embedding_model_path)
    onnx_path = model_dir / settings.embedding_onnx_filename
    tokenizer_path = model_dir / settings.embedding_tokenizer_filename
    if not onnx_path.is_file() or not tokenizer_path.is_file():
        _logger.warning("embedding_model_missing", path=str(model_dir))
        return None
    try:
        onnxruntime: Any = importlib.import_module("onnxruntime")
        tokenizers: Any = importlib.import_module("tokenizers")
    except ImportError:
        _logger.warning("embedding_runtime_dependency_missing")
        return None
    try:
        session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        tokenizer = tokenizers.Tokenizer.from_file(str(tokenizer_path))
    except Exception:  # noqa: BLE001 - modelo invalido nunca derruba a aplicacao
        _logger.warning("embedding_model_load_failed", path=str(onnx_path))
        return None
    _logger.info(
        "embedding_provider_ready",
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )
    return OnnxEmbeddingProvider(
        session=session,
        tokenizer=tokenizer,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
    )
