"""Adaptador offline do detector de idioma (langid, 11 locales).

O modelo (pequeno, ~2 MB) e carregado UMA vez por processo e restrito aos 11
idiomas da interface. Medicoes locais: ~31 MB de RSS, ~1,2 s no primeiro load
e ~0,2 ms por mensagem depois de aquecido. A deteccao por script cobre
ar/ru/ja/ko/zh-CN antes do modelo estatistico; o modelo so decide os idiomas
latinos (e confirma os demais quando o script e ambiguo).

A biblioteca e opcional em runtime: se o import falhar, o adaptador continua
funcionando apenas com os sinais de script (degradacao segura, sem derrubar o
chat).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger
from app.modules.ai.domain.language import (
    LanguageDetection,
    detect_script,
    has_request_marker,
    is_substantial,
    preprocess_for_detection,
    split_mixed_segments,
)
from app.modules.ai.domain.types import Locale

_logger = get_logger(__name__)

_LANGID_CODES: dict[str, Locale] = {
    "pt": Locale.PT_BR,
    "en": Locale.EN,
    "es": Locale.ES,
    "de": Locale.DE,
    "fr": Locale.FR,
    "it": Locale.IT,
    "ru": Locale.RU,
    "ar": Locale.AR,
    "ja": Locale.JA,
    "ko": Locale.KO,
    "zh": Locale.ZH_CN,
}


class LangidLanguageDetector:
    """Detector restrito aos 11 locales; script Unicode vem primeiro."""

    def __init__(self) -> None:
        self._langid = _build_langid_model()

    def detect(self, text: str) -> LanguageDetection:
        cleaned = preprocess_for_detection(text)
        if not cleaned:
            return LanguageDetection(language=None)
        script = detect_script(cleaned)
        if script is not None:
            return script
        if self._langid is None:
            return LanguageDetection(language=None)
        detections = self._segment_detections(cleaned)
        if not detections:
            return LanguageDetection(language=None)
        if len(detections) == 1:
            return detections[0][1]
        requested = next(
            (detection for segment, detection in detections if has_request_marker(segment)),
            None,
        )
        if requested is not None:
            return requested
        _segment, best = max(detections, key=lambda item: (item[1].confidence, len(item[0])))
        return best

    def _segment_detections(self, cleaned: str) -> list[tuple[str, LanguageDetection]]:
        results: list[tuple[str, LanguageDetection]] = []
        for segment in split_mixed_segments(cleaned):
            detection = detect_script(segment) or self._detect_latin(segment)
            if detection.language is not None:
                results.append((segment, detection))
        return results

    def _detect_latin(self, segment: str) -> LanguageDetection:
        if not is_substantial(segment):
            return LanguageDetection(language=None)
        if self._langid is None:  # pragma: no cover - defendido em detect()
            return LanguageDetection(language=None)
        ranks = self._langid.rank(segment)
        if not ranks:
            return LanguageDetection(language=None)
        code, confidence = _top_language(ranks)
        locale = _LANGID_CODES.get(code)
        if locale is None:
            return LanguageDetection(language=None)
        return LanguageDetection(language=locale, confidence=confidence, source="detector")


def _top_language(ranks: list[tuple[str, float]]) -> tuple[str, float]:
    """Topo do rank + confianca softmax sobre os idiomas restritos."""
    code, best = ranks[0]
    exps = [math.exp(score - best) for _code, score in ranks]
    total = sum(exps)
    return code, (exps[0] / total) if total > 0 else 0.0


@lru_cache(maxsize=1)
def _build_langid_model() -> Any | None:
    """Carrega o modelo uma vez por processo; None se a lib nao existir."""
    try:
        import langid

        langid.set_languages(list(_LANGID_CODES))
    except Exception as exc:  # noqa: BLE001 - dependencia opcional em runtime
        _logger.warning("language_detector_unavailable", error=str(exc))
        return None
    return langid
