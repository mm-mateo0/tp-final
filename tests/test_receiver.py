"""Pruebas HTTP del receptor sin publicar en una cola real."""
import json
import pytest
from fastapi.testclient import TestClient
from fenix.services import receiver

@pytest.mark.base
def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "clave-de-prueba-segura")
    monkeypatch.setattr(receiver, "verify", lambda *args: (_ for _ in ()).throw(
        receiver.ValidationError("firma")))
    response = TestClient(receiver.app).post("/webhook", content=b"{}",
        headers={"X-Webhook-Signature": "invalid"})
    assert response.status_code == 401

@pytest.mark.base
def test_webhook_rejects_invalid_json_after_auth(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "clave-de-prueba-segura")
    monkeypatch.setattr(receiver, "verify", lambda *args: None)
    response = TestClient(receiver.app).post("/webhook", content=b"{broken",
        headers={"X-Webhook-Signature": "test"})
    assert response.status_code == 400

@pytest.mark.base
def test_webhook_validates_then_publishes(monkeypatch):
    event = {"schema_version": 1, "event_id": "evt-node-001",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    monkeypatch.setenv("WEBHOOK_SECRET", "clave-de-prueba-segura")
    monkeypatch.setenv("QUEUE_PREFIX", "fenix-test")
    monkeypatch.setattr(receiver, "verify", lambda *args: None)
    monkeypatch.setattr(receiver, "load", lambda path: {
        "node-01": {"type": "ec2", "id": "i-test"}})
    monkeypatch.setattr(receiver, "queue_url", lambda prefix: "queue-url")
    monkeypatch.setattr(receiver, "publish", lambda url, payload: "message-123")
    response = TestClient(receiver.app).post("/webhook", content=json.dumps(event),
        headers={"X-Webhook-Signature": "test"})
    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "event_id": "evt-node-001",
                               "message_id": "message-123"}

@pytest.mark.base
def test_webhook_rejects_contract_before_publish(monkeypatch):
    event = {"schema_version": True, "event_id": "evt-node-001",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    monkeypatch.setenv("WEBHOOK_SECRET", "clave-de-prueba-segura")
    monkeypatch.setattr(receiver, "verify", lambda *args: None)
    monkeypatch.setattr(receiver, "load", lambda path: {
        "node-01": {"type": "ec2", "id": "i-test"}})
    response = TestClient(receiver.app).post("/webhook", content=json.dumps(event),
        headers={"X-Webhook-Signature": "test"})
    assert response.status_code == 422


@pytest.mark.base
def test_webhook_returns_503_when_queue_unavailable(monkeypatch):
    from botocore.exceptions import EndpointConnectionError
    event = {"schema_version": 1, "event_id": "evt-node-001",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    monkeypatch.setenv("WEBHOOK_SECRET", "clave-de-prueba-segura")
    monkeypatch.setenv("QUEUE_PREFIX", "fenix-test")
    monkeypatch.setattr(receiver, "verify", lambda *args: None)
    monkeypatch.setattr(receiver, "load", lambda path: {
        "node-01": {"type": "ec2", "id": "i-test"}})
    monkeypatch.setattr(receiver, "queue_url", lambda prefix: (_ for _ in ()).throw(
        EndpointConnectionError(endpoint_url="http://localhost:4566")))
    response = TestClient(receiver.app).post("/webhook", content=json.dumps(event),
        headers={"X-Webhook-Signature": "test"})
    assert response.status_code == 503
