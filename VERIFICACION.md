# Verificación técnica del proyecto

Fecha de revisión: 25/11/2026.

## Comprobaciones ejecutadas en la PC del estudiante

- `python -m pip install -e .`: instalación editable completada correctamente.
- `python -m compileall -q src tests`: correcto, sin errores de compilación.
- Docker y Docker Compose: disponibles y operativos.
- LocalStack `localstack/localstack:2026.10.0`: contenedor iniciado y estado `healthy`.
- Endpoint de salud de LocalStack (`http://localhost:4566/_localstack/health`): respondió HTTP 200.
- `python -m pytest -v -s tests/test_integration.py`: **1 passed**. Se comprobó que un mensaje JSON corrupto enviado a SQS fue recibido por el worker y terminó en la Dead Letter Queue (DLQ), conservando su contenido original.
- `python -m pytest -q`: **25 passed, 0 failed**.
- Se generó una advertencia de compatibilidad de Starlette relacionada con `httpx`; no impidió la ejecución de las pruebas.

Las pruebas automatizadas cubren validación, HMAC, receptor HTTP, persistencia, idempotencia, ACK, reintentos, notificaciones y rotación gzip. La prueba de integración confirmó el redrive real de un mensaje venenoso hacia la DLQ en LocalStack.

## Alcance de la evidencia

La integración SQS/DLQ fue ejecutada y aprobada en LocalStack. Esta verificación no debe interpretarse como evidencia de integración con servicios AWS reales ni como aprobación de funcionalidades externas que no hayan sido probadas por separado, como notificaciones mediante Telegram o Slack.

## Archivo de bloqueo de dependencias

Después de instalar las dependencias en el entorno definitivo, se puede generar el archivo de versiones con:

```powershell
python -m pip freeze > requirements-lock.txt
```

## Estado de la verificación

La compilación, las 25 pruebas automatizadas y la prueba de integración SQS/DLQ finalizaron correctamente en el entorno local del estudiante. Se conserva la advertencia de Starlette relacionada con `httpx` como observación no bloqueante.
