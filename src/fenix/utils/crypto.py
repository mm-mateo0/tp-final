"""Autenticación HMAC-SHA256 de webhooks sobre los bytes originales."""
import hashlib
import hmac
import re
import time
from fenix.utils.errors import ValidationError


def signature(secret: str, timestamp: int, body: bytes) -> str:
    if not isinstance(secret, str) or len(secret) < 16:
        raise ValidationError("Configurar WEBHOOK_SECRET de 16 caracteres o más")
    if not isinstance(body, bytes) or type(timestamp) is not int:
        raise ValidationError("Parámetros de firma inválidos")
    signed = str(timestamp).encode("ascii") + b"." + body
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def verify(secret: str, header: str, body: bytes, now: int | None = None) -> None:
    if not isinstance(header, str):
        raise ValidationError("Firma inválida")
    parts = header.split(",")
    values = {}
    for part in parts:
        if part.count("=") != 1:
            raise ValidationError("Firma inválida")
        key, value = part.split("=", 1)
        if key not in ("t", "v1") or key in values or not value:
            raise ValidationError("Firma inválida")
        values[key] = value
    if set(values) != {"t", "v1"} or not values["t"].isdigit():
        raise ValidationError("Firma inválida")
    digest = values["v1"]
    if re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
        raise ValidationError("Firma inválida")
    try:
        timestamp = int(values["t"])
        current = int(time.time()) if now is None else now
        expected = signature(secret, timestamp, body)
    except (ValueError, TypeError) as error:
        raise ValidationError("Firma inválida") from error
    if abs(current - timestamp) > 300 or not hmac.compare_digest(expected, digest.lower()):
        raise ValidationError("Firma inválida")
