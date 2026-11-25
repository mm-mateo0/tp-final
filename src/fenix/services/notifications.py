"""Adaptador de notificaciones por consola, Telegram o Slack."""
import os
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from fenix.utils.errors import PermanentError, RetryableError


def notify(text: str) -> None:
    provider = os.getenv("NOTIFY_PROVIDER", "console").lower()
    message = text[:1000]
    if provider == "console":
        print(f"[FENIX AVISO] {message}")
        return
    try:
        if provider == "telegram":
            token = os.environ["TELEGRAM_BOT_TOKEN"]
            chat_id = os.environ["TELEGRAM_CHAT_ID"]
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message}, timeout=(2, 5))
            response.raise_for_status()
            if response.json().get("ok") is not True:
                raise PermanentError("Telegram rechazó el aviso")
            return
        if provider == "slack":
            url = os.environ["SLACK_WEBHOOK_URL"]
            response = requests.post(url, json={"text": message}, timeout=(2, 5))
            response.raise_for_status()
            if response.text.strip() != "ok":
                raise PermanentError("Slack no confirmó el aviso")
            return
        raise PermanentError("NOTIFY_PROVIDER debe ser console, telegram o slack")
    except requests.Timeout as error:
        raise RetryableError("Timeout al enviar notificación") from error
    except requests.ConnectionError as error:
        raise RetryableError("No se pudo conectar con el proveedor de avisos") from error
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else 0
        if status == 429 or status >= 500:
            requested = None
            if error.response is not None:
                header = error.response.headers.get("Retry-After")
                if header:
                    try:
                        requested = max(0, int(header))
                    except ValueError:
                        try:
                            retry_date = parsedate_to_datetime(header)
                            requested = max(0, int((retry_date - datetime.now(
                                timezone.utc)).total_seconds()))
                        except (TypeError, ValueError, OverflowError):
                            requested = None
            # La espera solicitada se limita a 30 s; si el proveedor pide más,
            # se conserva el evento pendiente y se documenta esta limitación.
            if requested is not None:
                requested = min(30, requested)
            raise RetryableError(f"Proveedor de avisos respondió HTTP {status}",
                                 retry_after=requested) from error
        raise PermanentError(f"Proveedor de avisos rechazó la configuración (HTTP {status})") from error
