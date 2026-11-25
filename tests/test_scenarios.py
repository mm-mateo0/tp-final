"""Pruebas de idempotencia, orden de ACK y clasificación de eventos."""
import json
import pytest
from fenix.services import remediation, worker
from fenix.utils.errors import RetryableError, PermanentError

@pytest.mark.base
def test_duplicate_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fenix.utils.state import save, load
    event = {"schema_version": 1, "event_id": "evt-node-001",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    save("data/inventory.json", {"node-01": {"type": "ec2", "id": "i-test",
         "expected_tags": {"ManagedBy": "ppa2"}}})
    calls = {"repair": 0, "notify": 0}
    monkeypatch.setattr(remediation, "repair", lambda resource, kind: (
        calls.__setitem__("repair", calls["repair"] + 1) or "repaired"))
    monkeypatch.setattr(remediation, "notify", lambda text: calls.__setitem__(
        "notify", calls["notify"] + 1))
    remediation.handle(event)
    # Simula reinicio: el segundo handler vuelve a leer el ledger desde disco.
    remediation.handle(event)
    assert calls == {"repair": 1, "notify": 1}
    assert load("data/events.json")[event["event_id"]]["status"] == "completed"

@pytest.mark.base
def test_event_id_conflict_does_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fenix.utils.state import save, load
    event = {"schema_version": 1, "event_id": "evt-node-001",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    save("data/inventory.json", {"node-01": {"type": "ec2", "id": "i-test"}})
    monkeypatch.setattr(remediation, "repair", lambda *args: "repaired")
    monkeypatch.setattr(remediation, "notify", lambda *args: None)
    remediation.handle(event)
    changed = {**event, "occurred_at": "2026-10-23T18:00:00Z"}
    with pytest.raises(PermanentError):
        remediation.handle(changed)
    assert load("data/events.json")[event["event_id"]]["event"] == event

@pytest.mark.base
def test_ack_happens_only_after_success(monkeypatch):
    calls = []
    msg = {"MessageId": "m-1", "ReceiptHandle": "receipt-1",
           "Body": json.dumps({"x": 1}), "Attributes": {"ApproximateReceiveCount": "1"}}
    monkeypatch.setattr(worker, "receive", lambda url: [msg])
    monkeypatch.setattr(worker, "retry_later", lambda url, message: calls.append("retry") or 2)
    monkeypatch.setattr(worker, "acknowledge", lambda url, receipt: calls.append("ack"))
    def fail(event):
        calls.append("handler")
        raise RetryableError("test")
    worker.run("queue", fail, _Logger(), once=True)
    assert calls == ["handler", "retry"]
    calls.clear()
    worker.run("queue", lambda event: calls.append("handler"), _Logger(), once=True)
    assert calls == ["handler", "ack"]

class _Logger:
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass

@pytest.mark.base
def test_simulated_failures_persist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fenix.utils.state import save, load
    event = {"schema_version": 1, "event_id": "evt-node-002",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 2}
    save("data/inventory.json", {"node-01": {"type": "ec2", "id": "i-test"}})
    monkeypatch.setattr(remediation, "repair", lambda *args: "repaired")
    monkeypatch.setattr(remediation, "notify", lambda *args: None)
    with pytest.raises(RetryableError): remediation.handle(event)
    assert load("data/events.json")[event["event_id"]]["attempts"] == 1
    with pytest.raises(RetryableError): remediation.handle(event)
    assert load("data/events.json")[event["event_id"]]["attempts"] == 2
    remediation.handle(event)
    assert load("data/events.json")[event["event_id"]]["status"] == "completed"


@pytest.mark.base
def test_notification_retry_does_not_repeat_repair(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fenix.utils.state import save, load
    event = {"schema_version": 1, "event_id": "evt-node-003",
             "event_type": "instance.stopped", "resource_id": "node-01",
             "occurred_at": "2026-10-22T18:00:00Z", "simulate_failures": 0}
    save("data/inventory.json", {"node-01": {"type": "ec2", "id": "i-test"}})
    calls = {"repair": 0, "notify": 0}
    def repair_once(*args):
        calls["repair"] += 1
        return "repaired"
    def fail_notification_once(*args):
        calls["notify"] += 1
        if calls["notify"] == 1:
            raise RetryableError("simulated notification timeout")
    monkeypatch.setattr(remediation, "repair", repair_once)
    monkeypatch.setattr(remediation, "notify", fail_notification_once)
    with pytest.raises(RetryableError):
        remediation.handle(event)
    assert load("data/events.json")[event["event_id"]]["repair_done"] is True
    remediation.handle(event)
    assert calls == {"repair": 1, "notify": 2}
    assert load("data/events.json")[event["event_id"]]["notified"] is True
