"""Normalizacao pt/en da consulta e ordenacao nos 11 idiomas."""

from __future__ import annotations

import pytest

from app.modules.ai.application.intent_router import PriceSort, deterministic_decision
from app.modules.ai.application.query_normalization import normalize_query


@pytest.mark.parametrize(
    "message",
    [
        "günstigste Handschuhe",
        "gants moins chers",
        "手袋 最便宜",
        "самые дешёвые перчатки",
        "أرخص القفازات",
        "guantes más baratos",
        "luvas mais baratas",
        "cheapest gloves",
    ],
)
def test_normaliza_produto_para_luvas_gloves(message: str) -> None:
    query_pt, query_en = normalize_query(message)
    assert "luvas" in query_pt
    assert "gloves" in query_en


@pytest.mark.parametrize(
    ("message", "language"),
    [
        ("günstigste Handschuhe", "de"),
        ("gants moins chers", "fr"),
        ("手袋 最便宜", "zh-CN"),
        ("самые дешёвые перчатки", "ru"),
        ("أرخص القفازات", "ar"),
        ("guantes más baratos", "es"),
        ("luvas mais baratas", "pt-BR"),
        ("cheapest gloves", "en"),
    ],
)
def test_roteador_devolve_ordem_e_consultas_normalizadas(message: str, language: str) -> None:
    decision = deterministic_decision(message, reply_language=language)
    assert decision is not None
    assert decision.intent.value == "product_search"
    assert decision.price_sort == PriceSort.ASC
    assert "luvas" in decision.query_pt
    assert "gloves" in decision.query_en


def test_sem_produto_reconhecido_deixa_normalizacao_vazia() -> None:
    assert normalize_query("quero algo bom para a obra") == ("", "")
