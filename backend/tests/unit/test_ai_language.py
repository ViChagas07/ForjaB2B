"""Deteccao de idioma do chat (Fase 1) - regras puras e adaptador offline."""

from __future__ import annotations

import pytest

from app.modules.ai.application.chat_graph import knowledge_numbers_grounded
from app.modules.ai.domain.language import (
    LanguageDetection,
    detect_script,
    extract_explicit_language_request,
    is_substantial,
    looks_truncated,
    max_tokens_for,
    preprocess_for_detection,
    resolve_reply_language,
)
from app.modules.ai.domain.types import Locale


class FakeDetector:
    def __init__(self, language: Locale | None, confidence: float = 0.95) -> None:
        self.language = language
        self.confidence = confidence

    def detect(self, _text: str) -> LanguageDetection:
        return LanguageDetection(
            language=self.language,
            confidence=self.confidence,
            source="detector",
        )


def test_preprocess_remove_sku_numeros_urls_marcas_e_simbolos() -> None:
    cleaned = preprocess_for_detection(
        "Quero CAP-SOL-001 da VULCANO por R$ 1.234,56 em https://forja.example/x 😀"
    )
    assert cleaned == "quero da por em"
    assert "cap-sol" not in cleaned and "vulcano" not in cleaned


def test_scripts_fortes() -> None:
    cases = {
        Locale.KO: "안녕하세요 반갑습니다",
        Locale.JA: "こんにちはカタログ",
        Locale.ZH_CN: "你好 请给我看看目录",
        Locale.AR: "مرحبا كيف يمكنني المساعدة",
        Locale.RU: "Здравствуйте чем я могу помочь",
    }
    for expected, text in cases.items():
        detection = detect_script(text)
        assert detection is not None
        assert detection.language == expected
        assert detection.confidence >= 0.9


def test_scripts_nao_disparam_com_texto_latino() -> None:
    assert detect_script("quero luvas de seguranca") is None


def test_texto_curto_nao_e_substancial() -> None:
    assert is_substantial("ok") is False
    assert is_substantial("hola") is False
    assert is_substantial("quero luvas") is True


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("please answer in English", Locale.EN),
        ("responda em espanhol, por favor", Locale.ES),
        ("en français", Locale.FR),
        ("antworten Sie bitte auf Deutsch", Locale.DE),
        ("rispondi in italiano", Locale.IT),
        ("ответь по-русски", Locale.RU),
        ("أجب بالعربية", Locale.AR),
        ("日本語で答えてください", Locale.JA),
        ("한국어로 대답해 주세요", Locale.KO),
        ("请用中文回答", Locale.ZH_CN),
        ("responda em português", Locale.PT_BR),
    ],
)
def test_pedido_explicito_de_idioma(message: str, expected: Locale) -> None:
    assert extract_explicit_language_request(message) == expected


def test_pedido_explicito_ignora_mencoes_sem_pedido() -> None:
    assert extract_explicit_language_request("quero uma luva english style") is None
    assert extract_explicit_language_request("qual o preco do produto?") is None


def test_confianca_alta_troca_o_idioma_da_mensagem() -> None:
    resolved = resolve_reply_language(
        message="Quiero ver los guantes más baratos del catálogo",
        detection=LanguageDetection(language=Locale.ES, confidence=0.95, source="detector"),
        conversation_language="pt-BR",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.ES
    assert resolved.changed is True


def test_confianca_baixa_mantem_idioma_da_conversa() -> None:
    resolved = resolve_reply_language(
        message="La normativa aplica el criterio general",
        detection=LanguageDetection(language=Locale.ES, confidence=0.4, source="detector"),
        conversation_language="en",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.EN
    assert resolved.changed is False


def test_lexico_desempata_mensagem_curta_portuguesa() -> None:
    resolved = resolve_reply_language(
        message="quero luvas",
        detection=LanguageDetection(language=Locale.ES, confidence=0.52, source="detector"),
        conversation_language="en",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.PT_BR
    assert resolved.source == "lexicon"
    assert resolved.changed is True


def test_lexico_nao_decide_quando_ha_termos_de_dois_idiomas() -> None:
    resolved = resolve_reply_language(
        message="quero guantes",
        detection=LanguageDetection(language=Locale.ES, confidence=0.5, source="detector"),
        conversation_language="en",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.EN
    assert resolved.changed is False


def test_lexico_ingles_curto_sem_detector() -> None:
    resolved = resolve_reply_language(
        message="best gloves",
        detection=None,
        conversation_language="pt-BR",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.EN
    assert resolved.source == "lexicon"


def test_mensagem_curta_ou_ambigua_mantem_idioma_da_conversa() -> None:
    for message in ("ok", "hola", "sim", "👍"):
        resolved = resolve_reply_language(
            message=message,
            detection=LanguageDetection(language=Locale.ES, confidence=0.99, source="detector"),
            conversation_language="en",
            site_locale="pt-BR",
        )
        assert resolved.language == Locale.EN, message


def test_primeira_mensagem_sem_confianca_usa_locale_do_site() -> None:
    resolved = resolve_reply_language(
        message="ok",
        detection=None,
        conversation_language="pt-BR",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.PT_BR
    assert resolved.changed is False


def test_script_forte_vence_mesmo_em_mensagem_curta() -> None:
    resolved = resolve_reply_language(
        message="привет",
        detection=LanguageDetection(language=Locale.RU, confidence=0.99, source="script"),
        conversation_language="pt-BR",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.RU
    assert resolved.changed is True


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Quero ver as luvas mais baratas do catálogo", Locale.PT_BR),
        ("Show me the cheapest safety gloves in your catalog", Locale.EN),
        ("¿Cuáles son los guantes más baratos del catálogo?", Locale.ES),
        ("Zeigen Sie mir die günstigsten Sicherheitshandschuhe im Katalog", Locale.DE),
        ("Montrez-moi les gants de sécurité les moins chers du catalogue", Locale.FR),
        ("Mostrami i guanti di sicurezza più economici del catalogo", Locale.IT),
    ],
)
def test_adaptador_real_detecta_idiomas_latinos(message: str, expected: Locale) -> None:
    pytest.importorskip("langid")
    from app.modules.ai.infrastructure.language_detector import LangidLanguageDetector

    detector = LangidLanguageDetector()
    detection = detector.detect(message)
    assert detection.language == expected
    assert detection.confidence >= 0.75


def test_adaptador_real_curto_e_desempatado_pelo_lexico() -> None:
    pytest.importorskip("langid")
    from app.modules.ai.infrastructure.language_detector import LangidLanguageDetector

    detector = LangidLanguageDetector()
    detection = detector.detect("quero luvas")
    resolved = resolve_reply_language(
        message="quero luvas",
        detection=detection,
        conversation_language="en",
        site_locale="pt-BR",
    )
    assert resolved.language == Locale.PT_BR
    assert resolved.source == "lexicon"


def test_termo_forte_curto_vence_detector_errado() -> None:
    for message in ("Capacete para soldador", "Como funciona o frete"):
        resolved = resolve_reply_language(
            message=message,
            detection=LanguageDetection(language=Locale.ES, confidence=0.95, source="detector"),
            conversation_language="pt-BR",
            site_locale="pt-BR",
        )
        assert resolved.language == Locale.PT_BR, message
        assert resolved.source == "lexicon", message


def test_max_tokens_por_idioma_respeita_teto() -> None:
    assert max_tokens_for(Locale.PT_BR, cap=512) == 220
    assert max_tokens_for(Locale.JA, cap=512) == 360
    assert max_tokens_for(Locale.PT_BR, cap=200) == 200
    assert max_tokens_for(Locale.ZH_CN, cap=128) == 128


def test_detecta_resposta_truncada_no_meio_da_frase() -> None:
    assert looks_truncated("This answer keeps going and ends without", Locale.EN)
    assert looks_truncated("Esta e uma resposta longa que termina no meio,", Locale.PT_BR)
    assert not looks_truncated("Resposta completa.", Locale.PT_BR)
    assert not looks_truncated("Curta", Locale.PT_BR)


def test_numeros_de_ca_e_nr_precisam_existir_no_trecho() -> None:
    assert knowledge_numbers_grounded("CA 12345 e NRR 22 dB", "CA 12345, NRR 22 dB")
    assert not knowledge_numbers_grounded("CA 99999", "CA 12345")
    assert not knowledge_numbers_grounded("CA 12345", "")
    assert knowledge_numbers_grounded("Sem numeros de norma.", "")
