# Verificación técnica del proyecto

Fecha de revisión: 24/11/2026.

## Comprobaciones ejecutadas en el entorno de revisión
- `python -m compileall -q src tests`: correcto.
- `python -m pytest -q`: **24 passed, 1 skipped**.
- Las pruebas unitarias cubren validación, HMAC, receptor HTTP, persistencia, idempotencia, ACK, reintentos, notificaciones y rotación gzip.

## Prueba pendiente
La prueba de integración `tests/test_integration.py::test_poison_message_reaches_real_dlq` quedó omitida porque este entorno de revisión no tiene LocalStack configurado ni ejecutándose. Por lo tanto, todavía no hay evidencia real de redrive a DLQ, EC2 mock, S3 o notificación externa.

## Instalación pendiente en el equipo de entrega
La instalación editable (`python -m pip install -e .`) no pudo verificarse en el entorno de revisión porque no tiene acceso a Internet para descargar los requisitos de construcción. Debe ejecutarse en la PC del estudiante con conexión y con Docker Desktop/LocalStack disponibles.

## Archivo de bloqueo de dependencias
`requirements-lock.txt` contiene la instrucción de generación, no versiones inventadas. Después de instalar las dependencias en el entorno definitivo, ejecutar:

```powershell
python -m pip freeze > requirements-lock.txt
```

No presentar la prueba omitida como aprobada. Guardar la salida real de la prueba de integración y la evidencia del estado consultado por Boto3 antes de entregar.
