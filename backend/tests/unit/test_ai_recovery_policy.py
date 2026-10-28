"""Testes da politica de recuperacao de carrinho (FASE 4) — dominio puro."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.modules.ai.domain.recovery import (
    CartSnapshot,
    RecoveryAction,
    RecoveryConfig,
    RecoveryReason,
    evaluate_recovery,
)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def snapshot(**overrides: object) -> CartSnapshot:
    values: dict[str, object] = {
        "item_count": 2,
        "subtotal": Decimal("1000.00"),
        "shipping_total": Decimal("25.00"),
        "non_negotiated_subtotal": Decimal("1000.00"),
        "company_paid_orders": 0,
        "last_activity_at": NOW - timedelta(hours=25),
        "has_order_after_activity": False,
        "opted_out": False,
    }
    values.update(overrides)
    return CartSnapshot(**values)  # type: ignore[arg-type]


def evaluate(**overrides: object):
    return evaluate_recovery(
        snapshot(**overrides),
        config=RecoveryConfig(),
        now=NOW,
        last_attempt_at=None,
        attempts_for_state=0,
    )


def test_23h59_nao_e_elegivel() -> None:
    policy = evaluate(last_activity_at=NOW - timedelta(hours=23, minutes=59))
    assert policy.eligible is False
    assert policy.stop_reason == "not_idle_enough"


def test_24h_exatas_e_elegivel() -> None:
    assert evaluate(last_activity_at=NOW - timedelta(hours=24)).eligible is True


def test_mais_de_7_dias_nao_e_elegivel() -> None:
    policy = evaluate(last_activity_at=NOW - timedelta(days=7, seconds=1))
    assert policy.stop_reason == "too_old"


def test_carrinho_vazio_optout_e_pedido_depois_nao_sao_elegiveis() -> None:
    assert evaluate(item_count=0).stop_reason == "cart_empty"
    assert evaluate(opted_out=True).stop_reason == "opt_out"
    assert evaluate(has_order_after_activity=True).stop_reason == "order_after_activity"


def test_remind_sempre_disponivel() -> None:
    assert RecoveryAction.REMIND in evaluate().eligible_actions


def test_frete_gratis_exatamente_no_minimo() -> None:
    policy = evaluate(subtotal=Decimal("1500.00"), non_negotiated_subtotal=Decimal("1500.00"))
    assert RecoveryAction.FREE_SHIPPING in policy.eligible_actions
    assert RecoveryReason.ABOVE_FREE_SHIPPING_MIN in policy.reason_hints


def test_frete_gratis_um_centavo_abaixo_nao() -> None:
    policy = evaluate(subtotal=Decimal("1499.99"), non_negotiated_subtotal=Decimal("1499.99"))
    assert RecoveryAction.FREE_SHIPPING not in policy.eligible_actions
    assert RecoveryReason.BELOW_FREE_SHIPPING_MIN in policy.reason_hints


def test_frete_alto_gera_hint_mas_nao_amplia_regra() -> None:
    policy = evaluate(subtotal=Decimal("1000.00"), shipping_total=Decimal("200.00"))
    assert RecoveryReason.HIGH_SHIPPING_SHARE in policy.reason_hints
    assert RecoveryAction.FREE_SHIPPING not in policy.eligible_actions


def test_desconto_exige_pedido_pago_anterior() -> None:
    without = evaluate(company_paid_orders=0, subtotal=Decimal("1600.00"))
    assert RecoveryAction.DISCOUNT_3PCT not in without.eligible_actions
    with_prior = evaluate(company_paid_orders=1, subtotal=Decimal("1600.00"))
    assert RecoveryAction.DISCOUNT_3PCT in with_prior.eligible_actions
    assert RecoveryReason.REPEAT_CUSTOMER in with_prior.reason_hints


def test_desconto_nao_aplica_se_todas_as_linhas_sao_negociadas() -> None:
    policy = evaluate(
        company_paid_orders=3,
        subtotal=Decimal("1600.00"),
        non_negotiated_subtotal=Decimal("0.00"),
    )
    assert RecoveryAction.DISCOUNT_3PCT not in policy.eligible_actions


def test_escalar_por_valor_alto_no_limite() -> None:
    policy = evaluate(subtotal=Decimal("20000.00"), non_negotiated_subtotal=Decimal("20000.00"))
    assert RecoveryAction.ESCALATE_HUMAN in policy.eligible_actions
    assert RecoveryReason.HIGH_VALUE in policy.reason_hints


def test_escalar_por_sinal_de_risco() -> None:
    policy = evaluate(risk_signal=True)
    assert RecoveryAction.ESCALATE_HUMAN in policy.eligible_actions
    assert RecoveryReason.RISK_SIGNAL in policy.reason_hints


def test_carrinho_que_mudou_reinicia_estado() -> None:
    # attempts_for_state conta apenas tentativas DESDE o last_activity_at.
    policy = evaluate_recovery(
        snapshot(last_activity_at=NOW - timedelta(hours=30)),
        config=RecoveryConfig(),
        now=NOW,
        last_attempt_at=None,
        attempts_for_state=0,
    )
    assert policy.eligible is True


def test_duas_tentativas_no_mesmo_estado_param() -> None:
    policy = evaluate_recovery(
        snapshot(),
        config=RecoveryConfig(),
        now=NOW,
        last_attempt_at=NOW - timedelta(days=10),
        attempts_for_state=2,
    )
    assert policy.stop_reason == "attempts_exhausted_for_state"


def test_uma_tentativa_por_7_dias() -> None:
    policy = evaluate_recovery(
        snapshot(),
        config=RecoveryConfig(),
        now=NOW,
        last_attempt_at=NOW - timedelta(days=6, hours=23),
        attempts_for_state=1,
    )
    assert policy.stop_reason == "cooldown_7_days"


def test_hints_de_estoque_e_item_removido() -> None:
    policy = evaluate(low_stock_items=1, item_removed_recently=True)
    assert RecoveryReason.LOW_STOCK in policy.reason_hints
    assert RecoveryReason.ITEM_REMOVED in policy.reason_hints


def test_nunca_ha_acao_fora_da_lista_fechada() -> None:
    policy = evaluate(
        subtotal=Decimal("25000.00"),
        non_negotiated_subtotal=Decimal("25000.00"),
        company_paid_orders=5,
        risk_signal=True,
    )
    assert set(policy.eligible_actions) <= set(RecoveryAction)
    assert len(policy.eligible_actions) == 4
