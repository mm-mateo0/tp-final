"""Pruebas del adaptador de notificaciones sin enviar mensajes externos."""
import pytest
import requests
from fenix.services import notifications
from fenix.utils.errors import RetryableError, PermanentError


@pytest.mark.base
def test_telegram_429_respects_retry_after_cap(monkeypatch):
    class Response:
        status_code = 429
        headers = {"Retry-After": "90"}
        def raise_for_status(self):
            error = requests.HTTPError("private URL must not be logged")
            error.response = self
            raise error
    monkeypatch.setenv("NOTIFY_PROVIDER", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-de-prueba")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(notifications.requests, "post", lambda *args, **kwargs: Response())
    with pytest.raises(RetryableError) as caught:
        notifications.notify("test")
    assert caught.value.retry_after == 30


@pytest.mark.base
def test_unknown_provider_is_permanent(monkeypatch):
    monkeypatch.setenv("NOTIFY_PROVIDER", "unknown")
    with pytest.raises(PermanentError):
        notifications.notify("test")
