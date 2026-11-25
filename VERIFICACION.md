# Verificación técnica del proyecto

Fecha de revisión: 25/11/2026.

## Comprobaciones ejecutadas en la PC del estudiante

- `python -m pip install -e .`: instalación editable completada correctamente.
- `python -m compileall -q src tests`: correcto, sin errores de compilación.
- `python -m pytest -q`: **24 passed, 1 skipped**.
- Se generó una advertencia de compatibilidad de Starlette relacionada con `httpx`; no impidió la ejecución de las pruebas.

Las pruebas automatizadas cubren validación, HMAC, receptor HTTP, persistencia, idempotencia, ACK, reintentos, notificaciones y rotación gzip.

## Prueba de integración pendiente

La prueba `tests/test_integration.py::test_poison_message_reaches_real_dlq` quedó omitida.

La imagen de LocalStack utilizada por el proyecto requiere un token de autorización (`LOCALSTACK_AUTH_TOKEN`). El estudiante no dispone de un token proporcionado por la cátedra, por lo que no fue posible iniciar LocalStack y ejecutar la integración.

Por este motivo, todavía no hay evidencia de funcionamiento real de redrive a DLQ, EC2 mock, S3 ni notificaciones externas mediante el entorno integrado.

## Archivo de bloqueo de dependencias

Después de instalar las dependencias en el entorno definitivo, se puede generar el archivo de versiones con:

```powershell
python -m pip freeze > requirements-lock.txt
```

## Estado de la verificación

Las pruebas automatizadas disponibles y la compilación de los archivos Python finalizaron correctamente. La integración con LocalStack permanece pendiente por falta de autorización para utilizar la imagen requerida.

No presentar la prueba omitida como aprobada ni afirmar que se verificaron funcionalidades de integración que no pudieron ejecutarse.