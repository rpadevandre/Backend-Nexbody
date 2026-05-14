"""Sanitizacion de inputs — proteccion contra NoSQL injection."""
from __future__ import annotations

import re
from typing import Any

# Patrones peligrosos en contexto MongoDB
_MONGO_OP = re.compile(
    r"^\$"          # Operador MongoDB ($gt, $where, $regex…)
    r"|\.\$"        # Operador en path anidado
    r"|__proto__"   # Prototype pollution
    r"|constructor" # Prototype pollution alternativo
)

_MAX_STRING_LEN = 2_000
_MAX_DEPTH      = 5


class SanitizationError(ValueError):
    """Input rechazado por contener patrones inseguros."""


def sanitize_str(value: str, field: str = "campo") -> str:
    """Limpia un string de operadores MongoDB y trunca a largo maximo."""
    if not isinstance(value, str):
        raise SanitizationError(f"{field}: se esperaba string")
    if _MONGO_OP.search(value):
        raise SanitizationError(f"{field}: caracter no permitido")
    return value[:_MAX_STRING_LEN].strip()


def sanitize_dict(data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Sanitiza recursivamente un diccionario rechazando claves/valores inseguros."""
    if depth > _MAX_DEPTH:
        raise SanitizationError("Estructura demasiado anidada")
    result: dict[str, Any] = {}
    for key, value in data.items():
        if _MONGO_OP.search(str(key)):
            raise SanitizationError(f"Clave no permitida: {str(key)[:20]}")
        result[key] = _sanitize_value(value, key, depth)
    return result


def _sanitize_value(value: Any, field: str, depth: int) -> Any:
    if isinstance(value, str):
        return sanitize_str(value, field)
    if isinstance(value, dict):
        return sanitize_dict(value, depth + 1)
    if isinstance(value, list):
        return [_sanitize_value(item, field, depth) for item in value]
    return value


def safe_filter(field: str, value: str) -> dict[str, str]:
    """Construye un filtro MongoDB seguro (solo igualdad, nunca operadores)."""
    return {field: sanitize_str(value, field)}
