# ruff: noqa: RUF001 - pontuacao intencional em CJK/arabe
"""Idioma de resposta do chat: deteccao e regras por mensagem (Fase 1).

O idioma do site nao decide a resposta do assistente. A CADA mensagem:

- scripts Unicode sao sinal forte (ar, ru, ja, ko, zh-CN) e vencem o detector;
- um detector offline restrito aos 11 locales decide os idiomas latinos;
- pedido explicito ("responda em espanhol") vence a deteccao;
- mensagem curta/ambigua ("ok", "hola", emoji) mantem o idioma da conversa;
- a primeira mensagem sem confianca usa o locale do site;
- mensagem com idiomas misturados usa o idioma do trecho que contem o pedido.

O modulo e puro (sem I/O) para ser usado tambem pelo output guard.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from app.modules.ai.domain.types import Locale, resolve_locale

LANGUAGE_NAMES: dict[Locale, str] = {
    Locale.PT_BR: "Português (Brasil)",
    Locale.EN: "English",
    Locale.ZH_CN: "中文 (简体)",
    Locale.JA: "日本語",
    Locale.KO: "한국어",
    Locale.RU: "Русский",
    Locale.ES: "Español",
    Locale.DE: "Deutsch",
    Locale.FR: "Français",
    Locale.IT: "Italiano",
    Locale.AR: "العربية",
}

# Teto de tokens de SAIDA por idioma. Idiomas nao latinos gastam mais tokens
# por palavra; o adapter recebe este limite no complete_structured/text.
MAX_TOKENS_BY_LANGUAGE: dict[Locale, int] = {
    Locale.PT_BR: 220,
    Locale.EN: 220,
    Locale.ES: 220,
    Locale.DE: 220,
    Locale.FR: 220,
    Locale.IT: 220,
    Locale.RU: 300,
    Locale.AR: 300,
    Locale.JA: 360,
    Locale.KO: 360,
    Locale.ZH_CN: 360,
}

_TERMINAL = frozenset(".!?;:…。！？；：؟")
_TRAILING_CLOSERS = frozenset("\"'”’)）]】」』")
_TRUNCATED_TAIL = (
    " and",
    " e",
    " und",
    " et",
    " y",
    " и",
    " و",
    "と",
    "그리고",
    "和",
)

LANGUAGE_CONFIDENCE_MIN = 0.75
MIN_DETECTION_WORDS = 2
MIN_DETECTION_LETTERS = 8
GUARD_CONFIDENCE_MIN = 0.70
GUARD_MIN_WORDS = 4
GUARD_MIN_LETTERS = 20

LATIN_LOCALES = frozenset({Locale.PT_BR, Locale.EN, Locale.ES, Locale.DE, Locale.FR, Locale.IT})
NON_LATIN_SCRIPTS: dict[Locale, frozenset[str]] = {
    Locale.AR: frozenset({"arabic"}),
    Locale.RU: frozenset({"cyrillic"}),
    Locale.JA: frozenset({"kana", "han"}),
    Locale.KO: frozenset({"hangul"}),
    Locale.ZH_CN: frozenset({"han"}),
}

_SCRIPT_PATTERNS: dict[str, re.Pattern[str]] = {
    "latin": re.compile(r"[A-Za-z\u00c0-\u024f\u1e00-\u1eff]"),
    "cyrillic": re.compile(r"[\u0400-\u04ff]"),
    "greek": re.compile(r"[\u0370-\u03ff]"),
    "arabic": re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]"),
    "han": re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]"),
    "kana": re.compile(r"[\u3040-\u30ff]"),
    "hangul": re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]"),
}

_URL_OR_EMAIL = re.compile(
    r"(?i)(?:https?://|www\.)\S+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_CODE_TOKEN = re.compile(
    r"\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9_-]*\b"
)
_CURRENCY = re.compile(r"(?i)R\$|US\$|[€£$]")
_NUMBER = re.compile(r"\b\d[\d.,]*\b")
_KNOWN_BRANDS = re.compile(
    r"(?i)\b(?:forja|forjasafe|protec|norton|vulcano|aegis|guardian|ferrum|titan|sentinel)\b"
)
_WORD = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*", re.UNICODE)
_KEEP_CHAR = re.compile(r"[^\W\d_]", re.UNICODE)

_ALIASES: dict[Locale, tuple[str, ...]] = {
    Locale.PT_BR: (
        "português",
        "portugues",
        "portuguese",
        "portugais",
        "portoghese",
        "portugiesisch",
        "португальский",
        "البرتغالية",
        "葡萄牙语",
        "ポルトガル語",
        "포르투갈어",
    ),
    Locale.EN: (
        "inglês",
        "ingles",
        "english",
        "anglais",
        "inglese",
        "englisch",
        "английский",
        "الإنجليزية",
        "英语",
        "英語",
        "영어",
    ),
    Locale.ES: (
        "espanhol",
        "español",
        "espanol",
        "spanish",
        "espagnol",
        "spagnolo",
        "spanisch",
        "испанский",
        "الإسبانية",
        "西班牙语",
        "スペイン語",
        "스페인어",
    ),
    Locale.DE: (
        "alemão",
        "alemao",
        "german",
        "allemand",
        "tedesco",
        "deutsch",
        "немецкий",
        "الألمانية",
        "德语",
        "ドイツ語",
        "독일어",
    ),
    Locale.FR: (
        "francês",
        "frances",
        "french",
        "français",
        "francais",
        "francese",
        "französisch",
        "franzosisch",
        "французский",
        "الفرنسية",
        "法语",
        "フランス語",
        "프랑스어",
    ),
    Locale.IT: (
        "italiano",
        "italian",
        "italien",
        "italienisch",
        "итальянский",
        "الإيطالية",
        "意大利语",
        "イタリア語",
        "이탈리아어",
    ),
    Locale.RU: (
        "russo",
        "russian",
        "russe",
        "russisch",
        "русский",
        "русски",
        "الروسية",
        "俄语",
        "ロシア語",
        "러시아어",
    ),
    Locale.AR: (
        "árabe",
        "arabe",
        "arabic",
        "arabisch",
        "арабский",
        "بالعربية",
        "العربية",
        "阿拉伯语",
        "アラビア語",
        "아랍어",
    ),
    Locale.JA: (
        "japonês",
        "japones",
        "japanese",
        "japonais",
        "giapponese",
        "japanisch",
        "японский",
        "اليابانية",
        "日语",
        "日本語",
        "日本语",
        "일본어",
    ),
    Locale.KO: (
        "coreano",
        "korean",
        "coréen",
        "coreen",
        "koreanisch",
        "корейский",
        "الكورية",
        "韩语",
        "韓国語",
        "한국어",
    ),
    Locale.ZH_CN: (
        "chinês",
        "chines",
        "chinese",
        "chinois",
        "cinese",
        "chinesisch",
        "китайский",
        "الصينية",
        "中文",
        "汉语",
        "中国語",
        "중국어",
    ),
}

_REQUEST_VERBS = re.compile(
    r"(?i)\b(?:answer|reply|respond|write|speak|talk|use|switch|change|"
    r"responda|responder|responde|fale|falar|escreva|escrever|use|mude|troque|"
    r"antworten|antworte|schreibe|rede|sprich|wechsle|"
    r"réponds|répondez|répondre|écris|écrivez|parle|change|"
    r"rispondi|risponda|rispondere|scrivi|parla|cambia|"
    r"ответь|ответьте|отвечай|пиши|напиши|говори|переключи|"
    r"أجب|جاوب|اكتب|تحدث|غيّر|"
    r"回答|回复|答えて|返信|话|說|답변|대답|답해|말해)\b"
)
_PREPOSITION_END = re.compile(
    r"(?i)(?:^|\s)(?:in|em|en|auf|su|na|no|v|по-|用|で|로|으로|بال|ب)\s*$"
)
_POLITE_AFTER = re.compile(
    r"(?i)^\s*(?:please|por favor|s'il vous plaît|s'il vous plait|per favore|"
    r"bitte|пожалуйста|من فضلك|请|お願いします|제발)"
)
_LANGUAGE_VERB_AFTER = re.compile(
    r"(?i)^\s*(?:で\s*(?:答えて|回答して|返信して|話して)|"
    r"(?:로|으로)\s*(?:대답해|답변해|말해)|回答|回复|作答)"
)
_REQUEST_MARKERS = re.compile(
    r"(?i)\b(?:quero|preciso|busco|procuro|mostre|mande|envie|tem|como|qual|onde|quanto|"
    r"show|need|want|looking|find|how|what|where|which|price|compare|give|tell|search|"
    r"quiero|necesito|busco|muestra|precio|cómo|como|cuál|cual|dónde|donde|cuánto|cuanto|"
    r"zeig|brauche|möchte|moechte|such|preis|wie|welche|"
    r"montre|besoin|cherche|prix|comment|quel|"
    r"mostra|cerco|prezzo|come|quale|"
    r"покаж|нужн|хочу|ищу|цена|сколько|как|какой|"
    r"أرني|أريد|أحتاج|ابحث|سعر|كيف|كم|"
    r"見せ|ください|欲しい|探|価格|どの|いくら|"
    r"보여|주세요|원하|찾|가격|얼마|어떤|"
    r"请|想|找|价格|多少|怎么)"
)
_SENTENCE_SPLIT = re.compile(r"[.!?;¡¿\n]+")
_MIXED_SPLIT = re.compile(r"(?i)\s+(?:and|und|et|y|e|и|و|と|그리고|和)\s+")

# Sinais curtos e especificos para mensagens latinas em que o modelo estatistico
# fica na duvida (ex.: "quero luvas" saiu como espanhol/italiano no langid).
# So decide quando o termo e exclusivo de UM idioma e o texto e substancial.
_STRONG_LATIN_TERMS: dict[Locale, tuple[str, ...]] = {
    Locale.PT_BR: (
        "quero",
        "preciso",
        "luvas",
        "luva",
        "capacete",
        "carrinho",
        "frete",
        "obrigado",
        "obrigada",
        "você",
        "vocês",
        "não",
        "mais barato",
        "mais barata",
        "mais caro",
        "mais cara",
    ),
    Locale.EN: (
        "show",
        "need",
        "want",
        "looking",
        "cheapest",
        "price",
        "shipping",
        "cart",
        "order",
        "gloves",
        "helmet",
        "how much",
        "compare",
        "more options",
    ),
    Locale.ES: (
        "quiero",
        "necesito",
        "guantes",
        "guante",
        "casco",
        "carrito",
        "envío",
        "envio",
        "gracias",
        "cuánto",
        "cuanto",
        "dónde",
        "donde",
        "más barato",
        "más barata",
        "más caro",
        "más cara",
    ),
    Locale.DE: (
        "ich",
        "bitte",
        "danke",
        "versand",
        "warenkorb",
        "bestellung",
        "wie viel",
        "kostet",
        "günstig",
        "günstiger",
        "teuer",
    ),
    Locale.FR: (
        "bonjour",
        "merci",
        "combien",
        "livraison",
        "panier",
        "commande",
        "besoin",
        "cherche",
        "je",
        "vous",
        "moins cher",
        "plus cher",
        "s'il vous plaît",
    ),
    Locale.IT: (
        "voglio",
        "bisogno",
        "guanti",
        "guanto",
        "carrello",
        "spedizione",
        "grazie",
        "quanto",
        "dove",
        "più economico",
        "più caro",
    ),
}


@dataclass(frozen=True, kw_only=True)
class LanguageDetection:
    """Resultado de uma deteccao: idioma, confianca e origem do sinal."""

    language: Locale | None
    confidence: float = 0.0
    source: str = "none"


@dataclass(frozen=True, kw_only=True)
class ReplyLanguage:
    """Idioma escolhido para ESTA resposta, com a origem da decisao."""

    language: Locale
    confidence: float = 0.0
    source: str = "conversation"
    changed: bool = False


class LanguageDetectorPort(Protocol):
    """Porta do detector offline (adaptador real carregado uma vez)."""

    def detect(self, text: str) -> LanguageDetection: ...


def preprocess_for_detection(text: str) -> str:
    """Remove SKUs, numeros, URLs, marcas e simbolos antes de detectar."""
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text)
    value = _URL_OR_EMAIL.sub(" ", value)
    value = _UUID.sub(" ", value)
    value = _CODE_TOKEN.sub(" ", value)
    value = _KNOWN_BRANDS.sub(" ", value)
    value = _CURRENCY.sub(" ", value)
    value = _NUMBER.sub(" ", value)
    value = "".join(
        char for char in value if _KEEP_CHAR.match(char) or char.isspace() or char in "'\u2019-"
    )
    return " ".join(value.lower().split())


def script_counts(text: str) -> dict[str, int]:
    """Conta letras por script Unicode (sem pontuacao/numeros)."""
    return {name: len(pattern.findall(text)) for name, pattern in _SCRIPT_PATTERNS.items()}


def detect_script(text: str) -> LanguageDetection | None:
    """Sinal forte por script; None = texto latino/indefinido para o detector."""
    counts = script_counts(text)
    total = sum(counts.values())
    if total == 0:
        return None
    latin = counts["latin"]
    cyrillic = counts["cyrillic"]
    arabic = counts["arabic"]
    han = counts["han"]
    kana = counts["kana"]
    hangul = counts["hangul"]
    if kana >= 2 and kana + han >= 2:
        return LanguageDetection(language=Locale.JA, confidence=0.99, source="script")
    if hangul >= 2 and hangul / total >= 0.5:
        return LanguageDetection(language=Locale.KO, confidence=0.99, source="script")
    if han >= 2 and kana == 0 and hangul == 0 and han / total >= 0.5:
        return LanguageDetection(language=Locale.ZH_CN, confidence=0.99, source="script")
    if arabic >= 2 and arabic / total >= 0.5:
        return LanguageDetection(language=Locale.AR, confidence=0.99, source="script")
    if cyrillic >= 2 and cyrillic / total >= 0.5:
        return LanguageDetection(language=Locale.RU, confidence=0.99, source="script")
    if latin == 0 and total > 0:
        return None
    return None


def is_substantial(text: str) -> bool:
    """Texto suficiente para uma deteccao latina confiavel (evita 'ok', 'hola')."""
    words = _WORD.findall(text)
    letters = sum(1 for char in text if char.isalpha())
    return len(words) >= MIN_DETECTION_WORDS and letters >= MIN_DETECTION_LETTERS


def detect_strong_latin_terms(text: str) -> Locale | None:
    """Idioma por vocabulario exclusivo quando o detector estatistico duvida."""
    cleaned = preprocess_for_detection(text)
    if not is_substantial(cleaned):
        return None
    matches = [
        locale
        for locale, terms in _STRONG_LATIN_TERMS.items()
        if any(_term_present(cleaned, term) for term in terms)
    ]
    return matches[0] if len(matches) == 1 else None


def _term_present(text: str, term: str) -> bool:
    if " " in term or "'" in term:
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def is_guard_substantial(text: str) -> bool:
    """Texto suficiente para validar o idioma de uma RESPOSTA (menos falso positivo)."""
    words = _WORD.findall(text)
    letters = sum(1 for char in text if char.isalpha())
    return len(words) >= GUARD_MIN_WORDS and letters >= GUARD_MIN_LETTERS


def extract_explicit_language_request(text: str) -> Locale | None:
    """Idioma pedido explicitamente ("answer in English", "en français")."""
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", text).casefold()
    for locale, aliases in _ALIASES.items():
        for alias in aliases:
            if _alias_requested(normalized, alias):
                return locale
    return None


def _alias_requested(text: str, alias: str) -> bool:
    folded = alias.casefold()
    if _is_cjk(folded):
        # CJK nao tem fronteira de palavra util: o idioma e seguido de
        # particula/verbo (日本語で, 한국어로, 中文回答).
        pattern = re.compile(re.escape(folded))
    else:
        pattern = re.compile(rf"(?<!\w){re.escape(folded)}(?!\w)")
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - 40) : match.start()]
        after = text[match.end() : match.end() + 40]
        if (
            _REQUEST_VERBS.search(before)
            or _PREPOSITION_END.search(before)
            or _POLITE_AFTER.match(after)
            or _LANGUAGE_VERB_AFTER.match(after)
        ):
            return True
    return False


def _is_cjk(text: str) -> bool:
    return any(
        "\u3040" <= char <= "\u30ff"
        or "\u3400" <= char <= "\u4dbf"
        or "\u4e00" <= char <= "\u9fff"
        or "\uac00" <= char <= "\ud7af"
        for char in text
    )


def resolve_reply_language(
    *,
    message: str,
    detection: LanguageDetection | None,
    conversation_language: str | None,
    site_locale: str,
) -> ReplyLanguage:
    """Aplica as regras do idioma de resposta para a mensagem atual."""
    current = resolve_locale(conversation_language or site_locale)
    explicit = extract_explicit_language_request(message)
    if explicit is not None:
        return ReplyLanguage(
            language=explicit,
            confidence=1.0,
            source="explicit",
            changed=explicit != current,
        )
    # Em mensagem curta, um termo exclusivo de UM idioma vence o detector:
    # "capacete para soldador" e "como funciona o frete" sao portugues, mesmo
    # quando o langid devolve espanhol com confianca alta.
    strong = detect_strong_latin_terms(message)
    if strong is not None and len(_WORD.findall(message)) <= 8:
        return ReplyLanguage(
            language=strong,
            confidence=0.80,
            source="lexicon",
            changed=strong != current,
        )
    confident = (
        detection is not None
        and detection.language is not None
        and detection.confidence >= LANGUAGE_CONFIDENCE_MIN
    )
    if not confident and strong is not None:
        return ReplyLanguage(
            language=strong,
            confidence=0.80,
            source="lexicon",
            changed=strong != current,
        )
    if detection is None or detection.language is None:
        return ReplyLanguage(language=current, source="conversation")
    if detection.source != "script" and not is_substantial(preprocess_for_detection(message)):
        return ReplyLanguage(
            language=current,
            confidence=detection.confidence,
            source="conversation",
        )
    if detection.confidence < LANGUAGE_CONFIDENCE_MIN:
        return ReplyLanguage(
            language=current,
            confidence=detection.confidence,
            source="conversation",
        )
    return ReplyLanguage(
        language=detection.language,
        confidence=detection.confidence,
        source=detection.source,
        changed=detection.language != current,
    )


def guard_language_diverges(
    text: str,
    *,
    expected: Locale,
    detector: LanguageDetectorPort | None = None,
) -> bool:
    """True se a resposta diverge do idioma esperado (guard do chat)."""
    cleaned = preprocess_for_detection(text)
    counts = script_counts(cleaned)
    total = sum(counts.values())
    if total == 0:
        return False
    expected_scripts = NON_LATIN_SCRIPTS.get(expected)
    if expected_scripts is not None:
        return _non_latin_diverges(counts, total=total, expected_scripts=expected_scripts)
    foreign = sum(count for name, count in counts.items() if name != "latin")
    if foreign / total > 0.5:
        return True
    if detector is None or not is_guard_substantial(cleaned):
        return False
    detection = detector.detect(cleaned)
    return (
        detection.language is not None
        and detection.confidence >= GUARD_CONFIDENCE_MIN
        and detection.language in LATIN_LOCALES
        and detection.language != expected
    )


def _non_latin_diverges(
    counts: dict[str, int], *, total: int, expected_scripts: frozenset[str]
) -> bool:
    expected = sum(counts[name] for name in expected_scripts)
    foreign = sum(
        count for name, count in counts.items() if name != "latin" and name not in expected_scripts
    )
    if expected == 0:
        return True
    if expected / total < 0.25:
        return True
    return foreign / total > 0.5


def split_mixed_segments(text: str) -> list[str]:
    """Divide frases/conjuncoes para achar o trecho que contem o pedido."""
    segments: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        pieces = _MIXED_SPLIT.split(sentence)
        segments.extend(piece.strip() for piece in pieces if piece.strip())
    return segments or [text.strip()]


def select_request_segment(segments: list[str]) -> str:
    """Trecho com verbo/pergunta do pedido; senao, o mais longo."""
    for segment in segments:
        if has_request_marker(segment):
            return segment
    return max(segments, key=len, default="")


def has_request_marker(text: str) -> bool:
    """True se o trecho contem um verbo/pergunta de pedido reconhecido."""
    return bool(_REQUEST_MARKERS.search(text))


def language_name(locale: Locale | str) -> str:
    return LANGUAGE_NAMES[resolve_locale(locale)]


def max_tokens_for(locale: Locale | str, *, cap: int = 512) -> int:
    """Limite de saida do idioma, nunca acima do teto global do provedor."""
    return max(16, min(int(cap), MAX_TOKENS_BY_LANGUAGE[resolve_locale(locale)]))


def looks_truncated(text: str, locale: Locale | str) -> bool:
    """Heuristica de resposta cortada no meio da frase (sem finish_reason)."""
    cleaned = (text or "").strip()
    if len(cleaned) < 40:
        return False
    last = cleaned[-1]
    while last in _TRAILING_CLOSERS and len(cleaned) > 1:
        cleaned = cleaned[:-1].rstrip()
        last = cleaned[-1]
    if last in _TERMINAL:
        return False
    if last in ",，、;；:":
        return True
    lowered = cleaned.casefold()
    if any(lowered.endswith(tail) for tail in _TRUNCATED_TAIL):
        return True
    # Texto longo sem pontuacao final: sinal de corte no meio da frase.
    return True
