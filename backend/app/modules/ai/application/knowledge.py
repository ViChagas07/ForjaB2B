"""RAG estatico e deterministico sobre a base de conhecimento do Forja.

A base e Markdown versionado no pacote e entra no prompt como DADO NAO
CONFIAVEL (bloco delimitado), com sanitizacao e limite de tamanho. Nao ha
embedding nem LLM na recuperacao: termos da atividade/consulta sao pontuados
no titulo, nas atividades e no texto. Assim o Qwen so redige a recomendacao
com a orientacao recuperada + os produtos reais do catalogo.
"""

from __future__ import annotations

import importlib.resources
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.modules.ai.domain.security.catalog_sanitizer import sanitize_tool_text

_KB_FILE = "knowledge_base.chat.v1.md"
_MAX_SECTION_CHARS = 1200
_TOKEN = re.compile(r"[a-z0-9]{2,}")
_STOPWORDS = frozenset(
    {
        "que",
        "para",
        "com",
        "uma",
        "dos",
        "das",
        "por",
        "como",
        "mais",
        "meu",
        "minha",
        "preciso",
        "quero",
        "sobre",
        "the",
        "and",
        "for",
        "with",
        "what",
        "need",
        "de",
        "do",
        "da",
        "em",
        "no",
        "na",
        "os",
        "as",
        "um",
        "ao",
        "se",
        "ou",
        "e",
    }
)


@dataclass(frozen=True, kw_only=True)
class KnowledgeSection:
    title: str
    text: str
    categories: tuple[str, ...]
    activities: tuple[str, ...]
    search_terms: tuple[str, ...] = ()


class KnowledgeBase:
    """Indice em memoria de secoes Markdown (carregado uma vez)."""

    def __init__(self, sections: tuple[KnowledgeSection, ...]) -> None:
        self._sections = sections

    @classmethod
    def from_markdown(cls, text: str) -> KnowledgeBase:
        sections: list[KnowledgeSection] = []
        title = ""
        body: list[str] = []
        categories: tuple[str, ...] = ()
        activities: tuple[str, ...] = ()
        search_terms: tuple[str, ...] = ()
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if line.startswith("## "):
                _append_section(sections, title, body, categories, activities, search_terms)
                title = _clean_title(line[3:])
                body = []
                categories = ()
                activities = ()
                search_terms = ()
                continue
            if line.lower().startswith("categorias:"):
                categories = _split_csv(line.split(":", 1)[1])
                continue
            if line.lower().startswith("atividades:"):
                activities = _split_csv(line.split(":", 1)[1])
                continue
            if line.lower().startswith("busca:"):
                search_terms = _split_csv(line.split(":", 1)[1])
                continue
            if title and line and not line.startswith("#"):
                body.append(line)
        _append_section(sections, title, body, categories, activities, search_terms)
        return cls(tuple(sections))

    @classmethod
    def load_default(cls) -> KnowledgeBase:
        resource = importlib.resources.files("app.modules.ai.application.security").joinpath(
            f"data/{_KB_FILE}"
        )
        return cls.from_markdown(resource.read_text(encoding="utf-8"))

    def search(self, query: str, *, limit: int = 2) -> tuple[KnowledgeSection, ...]:
        tokens = _tokens(query)
        if not tokens:
            return ()
        scored: list[tuple[int, KnowledgeSection]] = []
        for section in self._sections:
            haystack_title = _fold(section.title)
            haystack_activities = _fold(" ".join(section.activities))
            haystack_text = _fold(section.text)
            score = 0
            for token in tokens:
                if token in haystack_title:
                    score += 4
                if token in haystack_activities:
                    score += 5
                score += min(haystack_text.count(token), 3)
            if score <= 0:
                continue
            safe = sanitize_tool_text(
                f"{section.title}\n{section.text}",
                label="base_de_conhecimento",
                max_chars=_MAX_SECTION_CHARS,
            )
            if safe.quarantined or not safe.context_text:
                continue
            scored.append(
                (
                    score,
                    KnowledgeSection(
                        title=section.title,
                        text=safe.context_text,
                        categories=section.categories,
                        activities=section.activities,
                        search_terms=section.search_terms,
                    ),
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return tuple(section for _, section in scored[:limit])


def _append_section(
    sections: list[KnowledgeSection],
    title: str,
    body: list[str],
    categories: tuple[str, ...],
    activities: tuple[str, ...],
    search_terms: tuple[str, ...],
) -> None:
    if not title:
        return
    text = "\n".join(body).strip()
    if text:
        sections.append(
            KnowledgeSection(
                title=title,
                text=text,
                categories=categories,
                activities=activities,
                search_terms=search_terms,
            )
        )


def _clean_title(value: str) -> str:
    return re.sub(r"^[#\s]+", "", value).strip()


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _tokens(query: str) -> tuple[str, ...]:
    return tuple(token for token in _TOKEN.findall(_fold(query)) if token not in _STOPWORDS)


@lru_cache(maxsize=1)
def default_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase.load_default()
