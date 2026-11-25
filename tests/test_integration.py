"""Prueba real de DLQ usando el worker y SQS de LocalStack."""
import time
import uuid
import pytest
from botocore.exceptions import BotoCoreError, ClientError
from fenix.config.settings import client
from fenix.services.sqs import ensure_queues
from fenix.services.worker import run
from fenix.utils.errors import ValidationError


class QuietLogger:
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


@pytest.mark.integracion
def test_poison_message_reaches_real_dlq():
    try:
        sqs = client("sqs")
        sqs.list_queues()
    except (BotoCoreError, ClientError, ValidationError) as error:
        pytest.skip(f"LocalStack no está disponible: {type(error).__name__}")
    prefix = f"fenix-it-{uuid.uuid4().hex[:8]}"
    work_url, dead_url = ensure_queues(prefix)
    original = "{mensaje-corrupto"
    sqs.send_message(QueueUrl=work_url, MessageBody=original)
    # El worker real recibe el JSON corrupto, no llama al handler y programa
    # backoff sobre el ReceiptHandle original. SQS aplica la RedrivePolicy.
    for delay in (2, 4, 8):
        run(work_url, lambda event: None, QuietLogger(), once=True)
        time.sleep(delay + 1)
    run(work_url, lambda event: None, QuietLogger(), once=True)
    deadline = time.monotonic() + 120
    found = None
    while time.monotonic() < deadline:
        response = sqs.receive_message(QueueUrl=dead_url, MaxNumberOfMessages=1,
            WaitTimeSeconds=2)
        if response.get("Messages"):
            found = response["Messages"][0]
            break
    assert found is not None, "El mensaje venenoso no apareció en la DLQ en 120 segundos"
    assert found["Body"] == original
    # No borrar el mensaje: queda disponible para documentar la evidencia.
    print(f"DLQ={dead_url}; MessageId={found['MessageId']}; Body preservado")
