"""Estado curto da sessao de chat para follow-ups (Fase 5).

O estado e SEMPRE escrito pelo servidor a partir da IntentDecision validada e
dos ids devolvidos pelas ferramentas. O texto do usuario nunca e copiado para
campos de sessao: ele so alimenta os extratores deterministicos desta camada
(preco/tamanho/"mais"/"comparar"). Tudo e limitado em tamanho e TTL.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    PriceSort,
    extract_price_constraints,
    first_product_term,
)

MAX_QUERY_CHARS = 200
MAX_PRODUCT_IDS = 8
MAX_ATTRIBUTES = 4
MAX_ATTRIBUTE_CHARS = 60
MAX_STATE_CHARS = 2000
MAX_OFFSET = 50

_SIZE = re.compile(r"(?i)\b(?:tamanho|size)\s*[:\-]?\s*(xxg|xg|gg|g|m|p|xs|s)\b")
_MORE = re.compile(r"(?i)\b(?:me mostra mais|mais opcoes|mais opções|mais resultados)\b")
_COMPARE = re.compile(
    r"(?i)\b(?:compara (?:essas|esses|estas|estes)|comparar essas|esses dois|"
    r"essas duas|os dois primeiros|as duas primeiras)\b"
)
_FOLLOW_PREFIX = re.compile(r"(?i)^(?:e|e a|e o|agora|entao|então)\b")


class ChatSessionStore(Protocol):
    async def load(self, conversation_id: uuid.UUID) -> ChatSessionState | None: ...

    async def save(self, conversation_id: uuid.UUID, state: ChatSessionState) -> None: ...


@dataclass(frozen=True, kw_only=True)
class ChatSessionState:
    intent: str
    query: str
    category: str | None = None
    brand: str | None = None
    price_sort: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    task: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    product_ids: tuple[str, ...] = ()
    offset: int = 0

    def to_json(self) -> str:
        return json.dumps(
            {
                "intent": self.intent[:40],
                "query": self.query[:MAX_QUERY_CHARS],
                "category": _optional(self.category, 60),
                "brand": _optional(self.brand, 80),
                "price_sort": _optional(self.price_sort, 8),
                "price_min": _price(self.price_min),
                "price_max": _price(self.price_max),
                "task": _optional(self.task, 120),
                "attributes": dict(list(self.attributes.items())[:MAX_ATTRIBUTES]),
                "product_ids": list(self.product_ids[:MAX_PRODUCT_IDS]),
                "offset": max(0, min(int(self.offset), MAX_OFFSET)),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str) -> ChatSessionState | None:
        if not raw or len(raw) > MAX_STATE_CHARS:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        intent = data.get("intent")
        query = data.get("query")
        if not isinstance(intent, str) or intent not in {item.value for item in IntentName}:
            return None
        if not isinstance(query, str):
            return None
        attributes = _attributes(data.get("attributes"))
        product_ids = _product_ids(data.get("product_ids"))
        price_sort = data.get("price_sort")
        if price_sort not in {None, PriceSort.ASC.value, PriceSort.DESC.value}:
            price_sort = None
        return cls(
            intent=intent,
            query=query[:MAX_QUERY_CHARS],
            category=_optional(data.get("category"), 60),
            brand=_optional(data.get("brand"), 80),
            price_sort=price_sort,
            price_min=_price(data.get("price_min")),
            price_max=_price(data.get("price_max")),
            task=_optional(data.get("task"), 120),
            attributes=attributes,
            product_ids=product_ids,
            offset=max(0, min(_int(data.get("offset")), MAX_OFFSET)),
        )


def session_from_decision(
    decision: IntentDecision, *, product_ids: tuple[str, ...]
) -> ChatSessionState:
    """Serializa somente campos validados do servidor (nunca o texto bruto)."""
    offset = 0
    if decision.offset > 0:
        offset = min(decision.offset + len(product_ids), MAX_OFFSET)
    return ChatSessionState(
        intent=decision.intent.value,
        query=decision.query[:MAX_QUERY_CHARS],
        category=decision.category,
        brand=decision.brand,
        price_sort=decision.price_sort.value if decision.price_sort else None,
        price_min=float(decision.price_min) if decision.price_min is not None else None,
        price_max=float(decision.price_max) if decision.price_max is not None else None,
        task=decision.task,
        attributes=dict(list(decision.attributes.items())[:MAX_ATTRIBUTES]),
        product_ids=tuple(product_ids[:MAX_PRODUCT_IDS]),
        offset=offset,
    )


def follow_up_decision(
    session: ChatSessionState, message: str, *, locale: str
) -> IntentDecision | None:
    """Reescreve follow-ups curtos reutilizando o estado do servidor."""
    if not _is_follow_up(message):
        return None
    try:
        base_intent = IntentName(session.intent)
    except ValueError:
        return None
    price_sort, price_min, price_max = extract_price_constraints(message)
    size = _size(message)
    is_more = bool(_MORE.search(message))
    is_compare = bool(_COMPARE.search(message))
    attributes = dict(session.attributes)
    if size is not None:
        attributes["tamanho"] = size
    intent = base_intent
    product_refs: list[str] = []
    if is_compare:
        intent = IntentName.PRODUCT_COMPARE
        product_refs = list(session.product_ids[:2])
    elif (
        size is not None or price_sort is not None or price_min is not None or price_max is not None
    ):
        intent = IntentName.PRODUCT_SEARCH
    offset = 0
    if is_more:
        offset = min(session.offset + len(session.product_ids), MAX_OFFSET)
    return IntentDecision(
        intent=intent,
        query=session.query,
        category=session.category,
        brand=session.brand,
        price_sort=price_sort or (PriceSort(session.price_sort) if session.price_sort else None),
        price_min=price_min if price_min is not None else session.price_min,
        price_max=price_max if price_max is not None else session.price_max,
        attributes=attributes,
        product_refs=product_refs,
        task=session.task,
        offset=offset,
        language=locale,
    )


class InMemoryChatSessionStore:
    """Store TTL em memoria (testes/single process; Redis em producao)."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 1800.0,
        max_entries: int = 5000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._data: OrderedDict[uuid.UUID, tuple[float, ChatSessionState]] = OrderedDict()

    async def load(self, conversation_id: uuid.UUID) -> ChatSessionState | None:
        self._purge()
        entry = self._data.get(conversation_id)
        if entry is None:
            return None
        if entry[0] <= self._clock():
            self._data.pop(conversation_id, None)
            return None
        return entry[1]

    async def save(self, conversation_id: uuid.UUID, state: ChatSessionState) -> None:
        self._purge()
        if len(self._data) >= self._max_entries and conversation_id not in self._data:
            self._data.popitem(last=False)
        self._data[conversation_id] = (self._clock() + self._ttl, state)
        self._data.move_to_end(conversation_id)

    def _purge(self) -> None:
        now = self._clock()
        expired = [key for key, (expires, _) in self._data.items() if expires <= now]
        for key in expired:
            self._data.pop(key, None)


def _is_follow_up(message: str) -> bool:
    if not message or len(message) > 80:
        return False
    if first_product_term(message) is not None and not (
        _MORE.search(message) or _COMPARE.search(message)
    ):
        return False
    price_words = re.search(r"(?i)\b(?:mais barat|mais car|mais opcoes|mais opções)\b", message)
    return bool(
        _FOLLOW_PREFIX.search(message)
        or _MORE.search(message)
        or _COMPARE.search(message)
        or _size(message) is not None
        or price_words is not None
    )


def _size(message: str) -> str | None:
    match = _SIZE.search(message)
    if match is None:
        return None
    value = match.group(1).upper()
    return "GG" if value == "GG" else value


def _optional(value: object, max_chars: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:max_chars] or None


def _price(value: object) -> float | None:
    try:
        parsed = float(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
    if parsed is None or parsed < 0 or parsed > 1_000_000:
        return None
    return parsed


def _int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _attributes(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for raw_key, raw_value in list(value.items())[:MAX_ATTRIBUTES]:
        key = str(raw_key).strip()[:40]
        item = str(raw_value).strip()[:MAX_ATTRIBUTE_CHARS]
        if key and item:
            result[key] = item
    return result


def _product_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip()[:64] for item in value[:MAX_PRODUCT_IDS] if str(item).strip())
