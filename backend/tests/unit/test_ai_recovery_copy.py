"""Testes da selecao deterministica de acao e da validacao do texto do e-mail."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.modules.ai.domain.recovery import (
    CartSnapshot,
    RecoveryAction,
    RecoveryConfig,
    RecoveryFacts,
    RecoveryPolicy,
    RecoveryReason,
    discount_for,
    evaluate_recovery,
    select_recovery_action,
)
from app.modules.ai.domain.recovery_copy import validate_recovery_copy

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
CONFIG = RecoveryConfig()


def snapshot(**overrides: object) -> CartSnapshot:
    values: dict[str, object] = {
        "item_count": 2,
        "subtotal": Decimal("1600.00"),
        "shipping_total": Decimal("25.00"),
        "non_negotiated_subtotal": Decimal("1600.00"),
        "company_paid_orders": 1,
        "last_activity_at": NOW - timedelta(hours=25),
        "has_order_after_activity": False,
        "opted_out": False,
    }
    values.update(overrides)
    return CartSnapshot(**values)  # type: ignore[arg-type]


def policy_for(snap: CartSnapshot) -> RecoveryPolicy:
    return evaluate_recovery(
        snap, config=CONFIG, now=NOW, last_attempt_at=None, attempts_for_state=0
    )


def facts_for(action: RecoveryAction, snap: CartSnapshot | None = None) -> RecoveryFacts:
    snap = snap or snapshot()
    discount = discount_for(snap) if action == RecoveryAction.DISCOUNT_3PCT else None
    return RecoveryFacts(
        company_name="Alfa",
        items_summary="- 1x Capacete",
        locale="pt-BR",
        action=action,
        subtotal=snap.subtotal,
        shipping_total=snap.shipping_total,
        discount_percent=Decimal("3.00") if discount is not None else None,
        discount_amount=discount,
        free_shipping_min=CONFIG.free_shipping_min_brl,
        cart_url="http://localhost:3000/pt-BR/cart",
    )


def test_desconto_de_3pct_arredonda_em_centavos() -> None:
    snap = snapshot(non_negotiated_subtotal=Decimal("1599.99"))
    assert discount_for(snap) == Decimal("48.00")


def test_desconto_escolhido_quando_beneficio_maior_que_frete() -> None:
    snap = snapshot()
    action, reason = select_recovery_action(snap, policy_for(snap), config=CONFIG)
    assert (action, reason) == (RecoveryAction.DISCOUNT_3PCT, RecoveryReason.REPEAT_CUSTOMER)


def test_frete_escolhido_quando_desconto_e_menor() -> None:
    snap = snapshot(shipping_total=Decimal("100.00"))
    action, reason = select_recovery_action(snap, policy_for(snap), config=CONFIG)
    assert (action, reason) == (
        RecoveryAction.FREE_SHIPPING,
        RecoveryReason.ABOVE_FREE_SHIPPING_MIN,
    )


def test_remind_quando_nao_ha_oferta() -> None:
    snap = snapshot(
        subtotal=Decimal("1000.00"),
        non_negotiated_subtotal=Decimal("1000.00"),
        company_paid_orders=0,
    )
    action, reason = select_recovery_action(snap, policy_for(snap), config=CONFIG)
    assert (action, reason) == (RecoveryAction.REMIND, RecoveryReason.CART_IDLE)


def test_escalar_por_risco_sem_oferta() -> None:
    snap = snapshot(
        subtotal=Decimal("1000.00"),
        non_negotiated_subtotal=Decimal("1000.00"),
        company_paid_orders=0,
        risk_signal=True,
    )
    action, reason = select_recovery_action(snap, policy_for(snap), config=CONFIG)
    assert (action, reason) == (RecoveryAction.ESCALATE_HUMAN, RecoveryReason.RISK_SIGNAL)


def test_copy_valido_com_percentual_e_valor_do_codigo() -> None:
    facts = facts_for(RecoveryAction.DISCOUNT_3PCT)
    result = validate_recovery_copy(
        "Volte e aproveite 3% de desconto: R$ 48,00 neste carrinho.", facts=facts
    )
    assert result.ok is True


def test_copy_com_percentual_diferente_reprova() -> None:
    result = validate_recovery_copy(
        "Aproveite 10% de desconto.", facts=facts_for(RecoveryAction.DISCOUNT_3PCT)
    )
    assert result.ok is False
    assert result.reason_code == "copy_percent_mismatch"


def test_copy_com_valor_diferente_reprova() -> None:
    result = validate_recovery_copy(
        "Aproveite R$ 99,00 de desconto.", facts=facts_for(RecoveryAction.DISCOUNT_3PCT)
    )
    assert result.ok is False
    assert result.reason_code == "copy_amount_mismatch"


def test_copy_com_url_html_ou_pii_reprova() -> None:
    facts = facts_for(RecoveryAction.DISCOUNT_3PCT)
    assert not validate_recovery_copy("Veja https://evil.test", facts=facts).ok
    assert not validate_recovery_copy("<script>alert(1)</script>", facts=facts).ok
    assert not validate_recovery_copy("Fale com a@b.test", facts=facts).ok


def test_frete_gratis_so_vale_quando_a_acao_e_frete_gratis() -> None:
    discount = facts_for(RecoveryAction.DISCOUNT_3PCT)
    assert not validate_recovery_copy("Seu frete grátis chegou.", facts=discount).ok

    free = facts_for(RecoveryAction.FREE_SHIPPING, snapshot(company_paid_orders=0))
    assert validate_recovery_copy("Seu frete grátis chegou.", facts=free).ok


def test_copy_vazio_reprova() -> None:
    result = validate_recovery_copy("   ", facts=facts_for(RecoveryAction.REMIND))
    assert result.ok is False
    assert result.reason_code == "copy_empty"
