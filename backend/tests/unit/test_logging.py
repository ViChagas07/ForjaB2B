"""Testes unitarios do pipeline de logging estruturado."""

from __future__ import annotations

import io
import json
import logging

from app.core.config import Settings
from app.core.correlation import reset_request_id, set_request_id
from app.core.logging import configure_logging, get_logger


def _attach_memory_stream() -> io.StringIO:
    """Redireciona o handler raiz para memoria (sem depender de capsys)."""
    stream = io.StringIO()
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(stream)
    return stream


def test_logging_json_com_request_id() -> None:
    configure_logging(Settings(log_format="json", log_level="INFO", otel_enabled=False))
    stream = _attach_memory_stream()

    token = set_request_id("req-test-123")
    try:
        get_logger("teste").info("evento_teste", chave="valor")
    finally:
        reset_request_id(token)

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert lines, "esperava ao menos uma linha de log"
    payload = json.loads(lines[-1])
    assert payload["event"] == "evento_teste"
    assert payload["chave"] == "valor"
    assert payload["request_id"] == "req-test-123"
    assert payload["level"] == "info"


def test_logging_console_sem_request_id() -> None:
    configure_logging(Settings(log_format="console", log_level="INFO", otel_enabled=False))
    stream = _attach_memory_stream()
    get_logger("teste").info("evento_console")
    assert "evento_console" in stream.getvalue()
