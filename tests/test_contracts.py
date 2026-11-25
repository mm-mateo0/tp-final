"""Pruebas unitarias de los contratos de entrada."""
import pytest
from fenix.utils.validation import identifier, ttl_seconds, utc_text
from fenix.utils.errors import ValidationError
from fenix.services.events import validate

@pytest.mark.base
def test_identifier_contract():
    assert identifier("grupo-01") == "grupo-01"
    for value in ("../AJENO", "ab", "A123", None, "a"*33):
        with pytest.raises(ValidationError):
            identifier(value)

@pytest.mark.base
def test_ttl_contract():
    assert ttl_seconds("60") == 60
    assert ttl_seconds("600") == 600
    for value in ("601", "59", "1.5", "-1", "abc", "060"):
        with pytest.raises(ValidationError):
            ttl_seconds(value)

@pytest.mark.base
def test_utc_contract():
    assert utc_text("2026-10-22T18:00:00Z").utcoffset().total_seconds() == 0
    with pytest.raises(ValidationError):
        utc_text("2026-10-22T18:00:00")
    with pytest.raises(ValidationError):
        utc_text("2026-10-22T18:00:00+03:00")

@pytest.mark.base
def test_event_closed_schema():
    event = {"schema_version": 1, "event_id": "evt-node-001",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    inventory = {"node-01": {"type": "ec2", "id": "i-123"}}
    assert validate(event, inventory) == event
    for bad in ({**event, "extra": 1}, {**event, "schema_version": True},
                {**event, "simulate_failures": True},
                {**event, "resource_id": "other"},
                {**event, "event_type": "bucket.tags_missing"}):
        with pytest.raises(ValidationError):
            validate(bad, inventory)
