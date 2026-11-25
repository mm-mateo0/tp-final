"""Validaciones comunes de identificadores, TTL y fechas UTC."""
import re
from datetime import datetime, timedelta, timezone
from fenix.utils.errors import ValidationError


def identifier(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9-]{3,32}", value) is None:
        raise ValidationError("Identificador inválido")
    return value


def ttl_seconds(value: str) -> int:
    if not isinstance(value, str):
        raise ValidationError("TTL debe ser un entero expresado como texto")
    try:
        ttl = int(value)
    except ValueError as error:
        raise ValidationError("TTL debe ser un entero") from error
    if str(ttl) != value.strip() or not 60 <= ttl <= 600:
        raise ValidationError("TTL debe estar entre 60 y 600 segundos")
    return ttl


def utc_text(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError("Fecha UTC inválida")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError("Fecha ISO 8601 inválida") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValidationError("La fecha debe incluir zona UTC explícita")
    return parsed.astimezone(timezone.utc)
