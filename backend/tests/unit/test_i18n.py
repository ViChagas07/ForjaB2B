"""Testes dos algoritmos de i18n do dominio e da aplicacao (sem banco).

Cobrem: negociacao de locale (Accept-Language + ?lang=), regra de fallback
campo-a-campo, hash de origem, stale, sanitizacao (rejeita HTML) e resolucao
de texto de produto (content_locale). Comportamentos validados contra o
codigo-fonte real (probe runtime) antes de serem asseridos.
"""

from __future__ import annotations

import pytest

from app.application.i18n import ProductTextTranslation, resolve_product_text
from app.domain.i18n import (
    CONTENT_LOCALES,
    DEFAULT_LOCALE,
    UI_LOCALES,
    TranslationStatus,
    is_translation_stale,
    match_supported_locale,
    negotiate_locale,
    product_source_hash,
    resolve_attributes,
    resolve_text,
    sanitize_translated_text,
)
from app.infrastructure.i18n.dictionary import category_name, load_attribute_dictionary

CONTENT_LOCALES_LIST = list(CONTENT_LOCALES)
UI_LOCALES_LIST = list(UI_LOCALES)


# ------------------------------------------------------------------ locale


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("pt-BR", "pt-BR"),
        ("PT-BR", "pt-BR"),
        ("pt-br", "pt-BR"),
        ("pt", "pt-BR"),
        ("en-US", "en"),
        ("es-419", "es"),
        ("ar-SA", "ar"),
    ],
)
def test_match_locale(locale: str, expected: str) -> None:
    assert match_supported_locale(locale, CONTENT_LOCALES_LIST) == expected


@pytest.mark.parametrize("locale", ["de", "fr-CA", "zh-Hans", "", "en "])
def test_match_locale_nao_suportado_devolve_none(locale: str) -> None:
    assert match_supported_locale(locale, CONTENT_LOCALES_LIST) is None


def test_negotiate_locale_respeita_parametro_explicito() -> None:
    _ui, content, fallback = negotiate_locale(
        lang_param="es", ui_locales=UI_LOCALES_LIST, content_locales=CONTENT_LOCALES_LIST
    )
    assert content == "es"
    assert fallback is False
    _ui, content, fallback = negotiate_locale(
        lang_param="en", ui_locales=UI_LOCALES_LIST, content_locales=CONTENT_LOCALES_LIST
    )
    assert content == "en"
    assert fallback is False


def test_negotiate_locale_lang_invalido_cai_no_default_sem_erro() -> None:
    # ?lang=de fora da lista: sem erro, cai no default (pt-BR). Um parametro
    # explicito invalido NAO promove o Accept-Language (comportamento
    # verificado em runtime): o cliente deve reenviar um ?lang= valido.
    _ui, content, fallback = negotiate_locale(
        lang_param="de", ui_locales=UI_LOCALES_LIST, content_locales=CONTENT_LOCALES_LIST
    )
    assert content == "en"  # de nao esta em CONTENT_LOCALES, cai em en
    assert fallback is True
    _ui, content, fallback = negotiate_locale(
        accept_language="ar",
        lang_param="de",
        ui_locales=UI_LOCALES_LIST,
        content_locales=CONTENT_LOCALES_LIST,
    )
    assert content == "en"  # lang invalido tem prioridade, cai em en
    assert fallback is True


def test_negotiate_locale_usa_accept_language() -> None:
    _ui, content, fallback = negotiate_locale(
        accept_language="en-US,en;q=0.9",
        ui_locales=UI_LOCALES_LIST,
        content_locales=CONTENT_LOCALES_LIST,
    )
    assert content == "en"
    assert fallback is False
    _ui, content, fallback = negotiate_locale(
        accept_language="es;q=0.8,en;q=0.9",
        ui_locales=UI_LOCALES_LIST,
        content_locales=CONTENT_LOCALES_LIST,
    )
    assert content == "en"  # en tem q=0.9 maior
    assert fallback is False


def test_negotiate_locale_sem_nada_devolve_default() -> None:
    _ui, content, fallback = negotiate_locale(
        ui_locales=UI_LOCALES_LIST, content_locales=CONTENT_LOCALES_LIST
    )
    assert content == DEFAULT_LOCALE
    assert fallback is False
    _ui, content, fallback = negotiate_locale(
        accept_language="fr",
        ui_locales=UI_LOCALES_LIST,
        content_locales=CONTENT_LOCALES_LIST,
    )
    assert content == "en"  # fr nao esta em CONTENT_LOCALES, cai em en
    assert fallback is True


# ------------------------------------------------------------------ resolve


def test_resolve_text_pt_br_entrega_origem_sem_fallback() -> None:
    r = resolve_text(source="Capacete", translated="X", locale="pt-BR")
    assert r.value == "Capacete"
    assert r.content_locale == "pt-BR"
    assert r.fallback is False


def test_resolve_text_com_traducao() -> None:
    r = resolve_text(source="Capacete", translated="Helmet", locale="en")
    assert r.value == "Helmet"
    assert r.content_locale == "en"
    assert r.fallback is False


def test_resolve_text_sem_traducao_faz_fallback() -> None:
    r = resolve_text(source="Capacete", translated=None, locale="en")
    assert r.value == "Capacete"
    assert r.content_locale == "pt-BR"
    assert r.fallback is True


def test_resolve_text_traducao_vazia_faz_fallback() -> None:
    r = resolve_text(source="Capacete", translated="   ", locale="en")
    assert r.value == "Capacete"
    assert r.content_locale == "pt-BR"
    assert r.fallback is True


def test_resolve_attributes_pt_br_entrega_origem() -> None:
    src = {"cor": "branco", "material": "abs", "potencia": "2cv"}
    attrs, fallback = resolve_attributes(source=src, translated=None, locale="pt-BR")
    assert attrs == src
    assert fallback is False


def test_resolve_attributes_fallback_campo_a_campo_preservando_codigos() -> None:
    src = {"cor": "branco", "material": "abs", "potencia": "2cv"}
    trad = {"cor": "White"}  # apenas 'cor' traduzido; codigos/unidades preservados
    attrs, fallback = resolve_attributes(source=src, translated=trad, locale="en")
    assert attrs == {"cor": "White", "material": "abs", "potencia": "2cv"}
    assert fallback is True


def test_resolve_attributes_sem_origem_usa_traducao() -> None:
    trad = {"cor": "White"}
    attrs, fallback = resolve_attributes(source=None, translated=trad, locale="en")
    assert attrs == {"cor": "White"}
    assert fallback is False


# ---------------------------------------------------------- hash + stale


def test_product_source_hash_deterministico() -> None:
    base = product_source_hash(name="Capacete", description="O", attributes={"cor": "branco"})
    same = product_source_hash(name="Capacete", description="O", attributes={"cor": "branco"})
    assert base == same
    assert len(base) == 64  # sha256


def test_product_source_hash_muda_com_a_origem() -> None:
    base = product_source_hash(name="Capacete", description="desc", attributes={"cor": "branco"})
    by_name = product_source_hash(
        name="Capacete X", description="desc", attributes={"cor": "branco"}
    )
    by_desc = product_source_hash(
        name="Capacete", description="desc2", attributes={"cor": "branco"}
    )
    by_attr = product_source_hash(name="Capacete", description="desc", attributes={"cor": "preto"})
    assert by_name != base
    assert by_desc != base
    assert by_attr != base


def test_is_translation_stale_detecta_divergencia_de_origem() -> None:
    stored = product_source_hash(name="Capacete", description="desc", attributes={})
    assert (
        is_translation_stale(
            stored_source_hash=stored,
            name="Capacete",
            description="desc",
            attributes={},
        )
        is False
    )
    assert (
        is_translation_stale(
            stored_source_hash=stored,
            name="Capacete Pro",
            description="desc",
            attributes={},
        )
        is True
    )


# ---------------------------------------------------------- product text


def _prod_text(translation=None, locale="en"):
    return resolve_product_text(
        source_name="Capacete",
        source_description="O",
        source_attributes={"cor": "branco"},
        locale=locale,
        translation=translation,
    )


def test_resolve_product_text_pt_br_ignora_traducao() -> None:
    r = _prod_text(
        translation=ProductTextTranslation(
            name="Helmet", description="Desc", attributes={"cor": "White"}
        ),
        locale="pt-BR",
    )
    assert r.content_locale == "pt-BR"
    assert r.fallback is False
    assert r.name.value == "Capacete"
    assert r.description.value == "O"
    assert r.attributes == {"cor": "branco"}


def test_resolve_product_text_sem_traducao_faz_fallback() -> None:
    r = resolve_product_text(
        source_name="Capacete de Seguranca",
        source_description="descricao",
        source_attributes={"cor": "branco"},
        locale="en",
        translation=None,
    )
    # content_locale e sempre o locale pedido (en), fallback indica field-by-field
    assert r.content_locale == "en"
    assert r.fallback is True
    assert r.name.value == "Capacete de Seguranca"


def test_resolve_product_text_com_traducao_entrega_locale() -> None:
    r = _prod_text(
        translation=ProductTextTranslation(
            name="Helmet", description="Descricao", attributes={"cor": "White"}
        )
    )
    assert r.content_locale == "en"
    assert r.fallback is False
    assert r.name.value == "Helmet"
    assert r.description.value == "Descricao"
    assert r.attributes == {"cor": "White"}


def test_resolve_product_text_fallback_campo_a_campo() -> None:
    # traducao parcial: nome traduzido, descricao e atributos faltam -> fallback
    r = _prod_text(
        translation=ProductTextTranslation(name="Helmet", description=None, attributes=None)
    )
    assert r.content_locale == "en"
    assert r.fallback is True
    assert r.name.value == "Helmet"
    assert r.description.value == "O"  # origem (fallback)
    assert r.attributes == {"cor": "branco"}  # origem (fallback)


# ---------------------------------------------------------- sanitize


def test_sanitize_translated_text_valores_basicos() -> None:
    assert sanitize_translated_text(None, max_length=4000) is None
    assert sanitize_translated_text("  hello  ", max_length=4000) == "hello"
    assert sanitize_translated_text("", max_length=4000) is None


@pytest.mark.parametrize(
    "bad",
    [
        "<script>alert(1)</script>",
        "<b>x</b>",
        "a<b>c",
    ],
)
def test_sanitize_translated_text_rejeita_html(bad: str) -> None:
    with pytest.raises(ValueError):
        sanitize_translated_text(bad, max_length=4000)


def test_sanitize_translated_text_respeita_limite() -> None:
    ok = "a" * 4000
    assert sanitize_translated_text(ok, max_length=4000) == ok
    with pytest.raises(ValueError):
        sanitize_translated_text("a" * 4001, max_length=4000)


def test_translation_status_valores() -> None:
    assert {s.value for s in TranslationStatus} == {
        "machine",
        "reviewed",
        "stale",
    }


# ---------------------------------------------------------- category names


def test_category_name_pt_br_usa_origem() -> None:
    assert (
        category_name(slug="protecao-cabeca", locale="pt-BR", default_name="Proteção da Cabeça")
        == "Proteção da Cabeça"
    )


def test_category_name_traduzido() -> None:
    assert (
        category_name(slug="protecao-cabeca", locale="en", default_name="Proteção da Cabeça")
        == "Head Protection"
    )
    assert (
        category_name(slug="protecao-maos", locale="es", default_name="Proteção das Mãos")
        == "Protección de las Manos"
    )
    assert (
        category_name(
            slug="protecao-respiratoria", locale="ar", default_name="Proteção Respiratória"
        )
        == "الحماية التنفسية"
    )


def test_category_name_slug_desconhecido_fallback() -> None:
    assert category_name(slug="inexistente", locale="en", default_name="Original") == "Original"


def test_category_name_locale_nao_suportado_fallback() -> None:
    assert (
        category_name(slug="protecao-cabeca", locale="de", default_name="Proteção da Cabeça")
        == "Proteção da Cabeça"
    )


# ---------------------------------------------------------- attribute dictionary


def test_attribute_dictionary_labels_carregados() -> None:
    d = load_attribute_dictionary()
    assert d["labels"]["en"]["cor"] == "Color"
    assert d["labels"]["es"]["material"] == "Material"
    assert d["labels"]["ar"]["tamanho"] == "المقاس"


def test_attribute_dictionary_options_carregados() -> None:
    d = load_attribute_dictionary()
    assert d["options"]["en"]["cor"]["branco"] == "white"
    assert d["options"]["es"]["cor"]["preto"] == "negro"
    assert d["options"]["ar"]["material"]["couro"] == "جلد"


def test_attribute_dictionary_chave_ausente_fallback_implicito() -> None:
    # O dicionario e usado como fallback: chave ausente = usa valor original
    d = load_attribute_dictionary()
    assert "chave_inexistente" not in d["labels"]["en"]
    assert "chave_inexistente" not in d["options"]["en"]
