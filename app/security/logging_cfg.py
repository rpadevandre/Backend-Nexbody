"""Configuracion de logging estructurado con structlog."""
from __future__ import annotations

import logging
import os
import re

import structlog


def mask_email(email: str) -> str:
    """Enmascara un email: ab***@domain.com"""
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}" if domain else f"{local[:2]}***"


def mask_token(token: str) -> str:
    return f"{token[:8]}..." if len(token) > 8 else "***"


def configure_logging() -> None:
    env = os.getenv("ENV", "development")
    level = logging.DEBUG if env == "development" else logging.INFO

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if env == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "formaruta") -> structlog.BoundLogger:
    return structlog.get_logger(name)
