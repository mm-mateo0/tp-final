"""Worker secuencial con ACK posterior al handler y backoff SQS."""
import json
import time
from botocore.exceptions import BotoCoreError, ClientError
from fenix.services.sqs import receive, acknowledge, retry_later
from fenix.utils.errors import ProjectError


def run(url: str, handler, logger, once: bool = False) -> None:
    while True:
        try:
            messages = receive(url)
        except (BotoCoreError, ClientError) as error:
            logger.error("fallo_consulta_sqs", extra={"status": type(error).__name__,
                "action": "receive"})
            if once:
                return
            time.sleep(2)
            continue
        for message in messages:
            message_id = message.get("MessageId")
            attempt = int(message.get("Attributes", {}).get("ApproximateReceiveCount", 0))
            event = None
            context = {"message_id": message_id, "event_id": None,
                       "resource_id": None, "attempt": attempt}
            try:
                event = json.loads(message["Body"])
                if not isinstance(event, dict):
                    raise ValueError("El mensaje debe contener un objeto JSON")
                context["event_id"] = event.get("event_id")
                context["resource_id"] = event.get("resource_id")
                handler(event)
            except (ValueError, TypeError, KeyError, ProjectError) as error:
                logger.warning("mensaje_no_procesado", extra={
                    **context, "status": type(error).__name__, "action": "retry"})
                try:
                    requested = getattr(error, "retry_after", None)
                    delay = (retry_later(url, message) if requested is None
                             else retry_later(url, message, requested))
                    logger.info("reintento_programado", extra={
                        **context, "action": "change_visibility", "status": str(delay)})
                except (BotoCoreError, ClientError, KeyError, ValueError) as retry_error:
                    logger.error("fallo_al_programar_reintento", extra={
                        **context, "status": type(retry_error).__name__,
                        "action": "change_visibility"})
                    time.sleep(2)
            except Exception as error:
                # Error inesperado: conservar el mensaje; no se confirma un resultado incierto.
                logger.error("error_inesperado_handler", extra={
                    **context, "status": type(error).__name__, "action": "retry"})
                try:
                    retry_later(url, message)
                except (BotoCoreError, ClientError, KeyError, ValueError):
                    time.sleep(2)
            else:
                logger.info("evento_completado", extra={
                    **context, "status": "completed", "action": "handler"})
                try:
                    acknowledge(url, message["ReceiptHandle"])
                    logger.info("mensaje_confirmado", extra={
                        **context, "status": "acknowledged", "action": "delete_message"})
                except (BotoCoreError, ClientError, KeyError) as error:
                    logger.error("fallo_ack", extra={
                        **context, "status": type(error).__name__, "action": "delete_message"})
                    time.sleep(2)
        if once:
            return
