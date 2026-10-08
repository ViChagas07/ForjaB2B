"""Testes unitarios da simulacao tributaria ICMS-ST (dominio compartilhado)."""

from __future__ import annotations

from decimal import Decimal

from app.domain.tax import compute_icms_st, icms_rate, icms_st_applies, round_money


def test_calculo_basico_icms_st() -> None:
    # base = 100.00; st_base = 100 * 1.40 = 140; imposto = 140 * 0.18 = 25.20
    result = compute_icms_st(
        product_value=Decimal("100.00"),
        ncm="33030000",
        origin_uf="SP",
        destination_uf="MG",
    )
    assert result == Decimal("25.20")


def test_icms_st_nao_aplicavel_mesma_uf() -> None:
    result = compute_icms_st(
        product_value=Decimal("100.00"),
        ncm="33030000",
        origin_uf="SP",
        destination_uf="SP",
    )
    assert result == Decimal("0.00")


def test_icms_st_nao_aplicavel_ncm_fora_da_lista() -> None:
    result = compute_icms_st(
        product_value=Decimal("100.00"),
        ncm="84713000",
        origin_uf="SP",
        destination_uf="MG",
    )
    assert result == Decimal("0.00")


def test_icms_st_nao_aplicavel_sem_ncm() -> None:
    result = compute_icms_st(
        product_value=Decimal("100.00"),
        ncm=None,
        origin_uf="SP",
        destination_uf="MG",
    )
    assert result == Decimal("0.00")


def test_ufs_diferentes_tem_aliquotas_diferentes() -> None:
    sp = compute_icms_st(
        product_value=Decimal("100.00"), ncm="33030000", origin_uf="SP", destination_uf="RJ"
    )
    rs = compute_icms_st(
        product_value=Decimal("100.00"), ncm="33030000", origin_uf="SP", destination_uf="RS"
    )
    assert sp == Decimal("25.20")  # 18%
    assert rs == Decimal("23.80")  # 17%


def test_frete_entra_na_base_de_calculo() -> None:
    sem_frete = compute_icms_st(
        product_value=Decimal("100.00"), ncm="33030000", origin_uf="SP", destination_uf="MG"
    )
    com_frete = compute_icms_st(
        product_value=Decimal("100.00"),
        freight=Decimal("20.00"),
        ncm="33030000",
        origin_uf="SP",
        destination_uf="MG",
    )
    assert sem_frete == Decimal("25.20")
    # base = 120; st_base = 168; imposto = 30.24
    assert com_frete == Decimal("30.24")


def test_arredondamento_monetario() -> None:
    # base = 10.00; st_base = 14.00; 14 * 0.18 = 2.52 (exato)
    assert round_money(Decimal("2.525")) == Decimal("2.53")
    assert round_money(Decimal("2.524")) == Decimal("2.52")


def test_icms_st_applies_regras() -> None:
    assert icms_st_applies(ncm="33030000", origin_uf="SP", destination_uf="MG") is True
    assert icms_st_applies(ncm="33030000", origin_uf="SP", destination_uf="SP") is False
    assert icms_st_applies(ncm="84713000", origin_uf="SP", destination_uf="MG") is False
    assert icms_st_applies(ncm=None, origin_uf="SP", destination_uf="MG") is False


def test_icms_rate_default_e_conhecido() -> None:
    assert icms_rate("SP") == Decimal("0.18")
    assert icms_rate("ZZ") == Decimal("0.18")


def test_determinismo() -> None:
    a = compute_icms_st(
        product_value=Decimal("333.33"),
        freight=Decimal("15.00"),
        ncm="39239000",
        origin_uf="SP",
        destination_uf="RS",
    )
    b = compute_icms_st(
        product_value=Decimal("333.33"),
        freight=Decimal("15.00"),
        ncm="39239000",
        origin_uf="SP",
        destination_uf="RS",
    )
    assert a == b


def test_valores_monetarios_sem_float() -> None:
    result = compute_icms_st(
        product_value=Decimal("0.10"), ncm="33030000", origin_uf="SP", destination_uf="MG"
    )
    assert result == Decimal("0.03")
