"""Testes unitarios do calculo de frete (dominio compartilhado)."""

from __future__ import annotations

from decimal import Decimal

from app.domain.shipping import compute_shipping, compute_total_weight


def test_peso_de_um_item() -> None:
    total = compute_total_weight([(3, Decimal("2.000"))])
    assert total == Decimal("6.000")


def test_peso_de_multiplos_itens() -> None:
    total = compute_total_weight(
        [(2, Decimal("1.500")), (5, Decimal("0.400")), (1, Decimal("3.000"))]
    )
    assert total == Decimal("8.000")  # 3.0 + 2.0 + 3.0


def test_peso_ausente_conta_como_zero() -> None:
    total = compute_total_weight([(4, None), (2, Decimal("1.000"))])
    assert total == Decimal("2.000")


def test_peso_total_zero_para_lista_vazia() -> None:
    assert compute_total_weight([]) == Decimal("0.00")


def test_frete_proporcional_ao_peso() -> None:
    # base 15.00 + 5.00 * 2.000 = 25.00
    assert compute_shipping(total_weight_kg=Decimal("2.000")) == Decimal("25.00")


def test_frete_zero_para_peso_zero() -> None:
    assert compute_shipping(total_weight_kg=Decimal("0.00")) == Decimal("0.00")


def test_frete_zero_para_pedido_sem_peso() -> None:
    assert compute_shipping(total_weight_kg=Decimal("0.000")) == Decimal("0.00")


def test_frete_com_arredondamento_monetario() -> None:
    # base 15.00 + 5.00 * 1.333 = 21.665 -> 21.67 (ROUND_HALF_UP)
    assert compute_shipping(total_weight_kg=Decimal("1.333")) == Decimal("21.67")


def test_determinismo() -> None:
    weights = [(1, Decimal("0.500")), (3, Decimal("1.250"))]
    first = compute_shipping(total_weight_kg=compute_total_weight(weights))
    second = compute_shipping(total_weight_kg=compute_total_weight(weights))
    assert first == second


def test_sem_ponto_flutuante() -> None:
    total = compute_total_weight([(3, Decimal("0.100"))])
    assert total == Decimal("0.300")
