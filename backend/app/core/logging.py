"""Logging estruturado (JSON por padrao) com correlacao de request/trace.

Regras de higiene: nunca logar senhas, tokens, secrets, credenciais de banco
ou PII desnecessaria. Campos sensiveis sao responsabilidade de quem chama;
esta fundacao oferece apenas o pipeline estruturado e a correlacao.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import Settings
from app.core.correlation import get_request_id
from app.core.telemetry import current_trace_id


def _add_correlation_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    request_id = get_request_id()
    if request_id is not None:
        event_dict["request_id"] = request_id
    trace_id = current_trace_id()
    if trace_id is not None:
        event_dict["trace_id"] = trace_id
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configura stdlib logging + structlog uma vez por processo."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    renderer: structlog.types.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _add_correlation_context,
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn mantem seus proprios handlers; alinhamos ao pipeline JSON.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
