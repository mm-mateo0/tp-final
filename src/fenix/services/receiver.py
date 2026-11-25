"""Receptor HTTP que autentica, valida y publica en SQS."""
import os
import json
from fastapi import FastAPI, Request, HTTPException
from starlette.concurrency import run_in_threadpool
from botocore.exceptions import BotoCoreError, ClientError
from fenix.utils.crypto import verify
from fenix.utils.errors import ValidationError
from fenix.utils.state import load
from fenix.services.events import validate
from fenix.services.sqs import queue_url, publish

app = FastAPI(title="Fénix receptor de alertas")


@app.post("/webhook", status_code=202)
async def webhook(request: Request) -> dict:
    raw = await request.body()
    if len(raw) > 16384:
        raise HTTPException(413, "Cuerpo demasiado grande")
    try:
        secret = os.environ["WEBHOOK_SECRET"]
        verify(secret, request.headers.get("X-Webhook-Signature", ""), raw)
    except (ValidationError, KeyError):
        raise HTTPException(401, "Firma no válida") from None
    try:
        event = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "JSON inválido") from None
    try:
        inventory = await run_in_threadpool(load, "data/inventory.json")
        clean = validate(event, inventory)
    except ValidationError as error:
        raise HTTPException(422, str(error)) from error
    try:
        url = await run_in_threadpool(queue_url, os.environ["QUEUE_PREFIX"])
        message_id = await run_in_threadpool(publish, url, clean)
    except (BotoCoreError, ClientError, KeyError, OSError):
        raise HTTPException(503, "Servicio de mensajería no disponible") from None
    return {"status": "accepted", "event_id": clean["event_id"], "message_id": message_id}
