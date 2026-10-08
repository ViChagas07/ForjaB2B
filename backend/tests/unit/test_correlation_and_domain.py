"""Testes unitarios de correlacao (request ID) e bases de dominio."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.correlation import get_request_id, new_request_id, reset_request_id, set_request_id
from app.domain.entity import AggregateRoot, Entity
from app.domain.errors import DomainError
from app.domain.events import DomainEvent


def test_request_id_set_get_reset() -> None:
    assert get_request_id() is None
    request_id = new_request_id()
    assert len(request_id) == 32
    token = set_request_id(request_id)
    assert get_request_id() == request_id
    reset_request_id(token)
    assert get_request_id() is None


def test_domain_error_tem_codigo_estavel() -> None:
    class RegraViolada(DomainError):
        code = "regra_violada"

    err = RegraViolada("mensagem de dominio")
    assert err.code == "regra_violada"
    assert err.message == "mensagem de dominio"


def test_aggregate_root_coleta_e_drena_eventos() -> None:
    @dataclass(frozen=True, kw_only=True)
    class AlgoAconteceu(DomainEvent):
        valor: int

    @dataclass(kw_only=True)
    class MeuAgregado(AggregateRoot):
        nome: str

    agregado = MeuAgregado(nome="x")
    evento = AlgoAconteceu(valor=1)
    agregado.register_event(evento)

    coletados = agregado.collect_events()
    assert coletados == [evento]
    assert coletados[0].event_id is not None
    assert agregado.collect_events() == []


def test_entity_tem_id_uuid() -> None:
    entidade = Entity()
    assert entidade.id.version == 4


def test_uow_sessao_antes_de_iniciar_falha() -> None:
    """Acessar a sessao fora de 'async with' e erro explicito, nao None."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.infrastructure.db.unit_of_work import (
        SqlAlchemyUnitOfWork,
        UnitOfWorkNotStartedError,
    )

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker()
    uow = SqlAlchemyUnitOfWork(factory, tenant=None)
    with pytest.raises(UnitOfWorkNotStartedError):
        _ = uow.session
