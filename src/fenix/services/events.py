"""Validación estricta del contrato de eventos Fénix."""
from fenix.utils.errors import ValidationError
from fenix.utils.validation import identifier, utc_text

FIELDS = {"schema_version", "event_id", "event_type", "resource_id",
          "occurred_at", "simulate_failures"}
ALLOWED = {"instance.stopped": "ec2", "bucket.tags_missing": "s3"}


def validate(event: dict, inventory: dict) -> dict:
    if not isinstance(event, dict):
        raise ValidationError("El evento debe ser un objeto JSON")
    if set(event) != FIELDS:
        raise ValidationError("El evento tiene campos ausentes o no permitidos")
    if type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise ValidationError("schema_version debe ser el entero 1")
    event_id = identifier(event["event_id"])
    alias = identifier(event["resource_id"])
    event_type = event["event_type"]
    if event_type not in ALLOWED:
        raise ValidationError("event_type no permitido")
    utc_text(event["occurred_at"])
    failures = event["simulate_failures"]
    if type(failures) is not int or not 0 <= failures <= 5:
        raise ValidationError("simulate_failures debe ser un entero entre 0 y 5")
    if not isinstance(inventory, dict) or alias not in inventory:
        raise ValidationError("El recurso no pertenece al inventario")
    resource = inventory[alias]
    if not isinstance(resource, dict) or resource.get("type") != ALLOWED[event_type]:
        raise ValidationError("El tipo de evento no coincide con el recurso")
    return dict(event)
