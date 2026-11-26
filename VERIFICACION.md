# Verificación técnica del Proyecto Fénix

**Fecha de revisión:** 25/11/2026  
**Responsable:** Mateo Ismael Liendro  
**Modalidad:** Trabajo individual

## 1. Entorno de ejecución

- Sistema operativo: Windows.
- Python: 3.15.2.
- Docker: 29.9.3.
- Docker Compose: 5.7.1.
- LocalStack: 2026.10.0.
- Servicio de LocalStack: ejecutándose correctamente en Docker.

Se verificó la disponibilidad de LocalStack mediante el endpoint `http://localhost:4566/_localstack/health`, que respondió con código HTTP 200.

## 2. Verificaciones realizadas

| Verificación | Resultado |
|---|---|
| Instalación editable del proyecto (`python -m pip install -e .`) | Correcta |
| Compilación de módulos (`python -m compileall -q src tests`) | Correcta |
| Disponibilidad de LocalStack | Correcta |
| Pruebas automatizadas completas | 25 aprobadas |

## 3. Resultado de las pruebas

Comando ejecutado:

```powershell
python -m pytest -q
```

Resultado:

```text
25 passed, 1 warning in 39.90s
```

Las 25 pruebas finalizaron correctamente.

Se observó una advertencia de compatibilidad relacionada con el uso de `httpx` en `starlette.testclient`. Esta advertencia no impidió la ejecución ni la aprobación de las pruebas.

## 4. Prueba de integración con SQS y DLQ

Prueba ejecutada:

`tests/test_integration.py::test_poison_message_reaches_real_dlq`

Resultado: **APROBADA**.

Se utilizó LocalStack 2026.10.0 ejecutándose en Docker para comprobar el funcionamiento real de las colas SQS.

La prueba realizó las siguientes verificaciones:

1. Creación de una cola de eventos y una Dead Letter Queue (DLQ).
2. Envío de un mensaje con contenido JSON corrupto.
3. Recepción del mensaje por el worker.
4. Aplicación de los reintentos y tiempos de espera.
5. Redirección automática del mensaje a la DLQ.
6. Conservación del contenido original del mensaje.

Resultado de la ejecución individual:

```text
1 passed in 36.27s
```

La ejecución completa posterior también aprobó las 25 pruebas.

## 5. Alcance y observaciones

Las pruebas automatizadas verifican los componentes y comportamientos cubiertos por la suite del proyecto, incluyendo validación, HMAC, receptor HTTP, persistencia, idempotencia, ACK, reintentos, notificaciones y rotación de logs.

La prueba de integración con SQS y DLQ fue ejecutada satisfactoriamente contra LocalStack.

No se presentan como verificadas integraciones externas que no hayan sido ejecutadas específicamente.

## 6. Configuración y seguridad

- Las credenciales de prueba utilizadas corresponden al entorno emulado.
- La configuración local se almacena en `.env`.
- El archivo `.env` no debe publicarse en GitHub.
- `.env.example` contiene las variables necesarias como referencia, sin credenciales personales.
- No se utilizaron credenciales de una cuenta AWS real para las pruebas locales.

## 7. Estado final

El proyecto fue instalado, compilado y probado en el entorno local.

**Resultado final: 25 pruebas aprobadas y prueba de integración real con SQS y DLQ satisfactoria.**


## Verificación final — 26/11/2026

### Prueba de integración real con LocalStack

Se realizó una prueba completa del flujo de autorreparación de Proyecto Fénix.

**Resultado obtenido:**

1. Se inicializaron las colas SQS principal y DLQ.
2. Se configuraron los recursos de demostración en LocalStack.
3. Se provocó una falla controlada en el recurso `node-01`.
4. Se envió el evento `evt-node-001` mediante el webhook autenticado.
5. El servidor respondió `HTTP 202 Accepted`.
6. El worker consumió y procesó el mensaje de la cola.
7. El sistema ejecutó la reparación de la instancia EC2.
8. Se verificó mediante Boto3 que la instancia terminó en estado `running`.
9. Se recibió correctamente una notificación real en Telegram:

`Fénix: instance.stopped en node-01; resultado=repaired; evento=evt-node-001`

### Pruebas automatizadas

Ejecución de la suite completa:

`python -m pytest -q`

Resultado: **25 pruebas aprobadas**.

### Evidencias

- Captura de la notificación recibida en Telegram.
- Captura de la consulta Boto3 mostrando el estado `running`.
- Respuesta HTTP 202 del webhook.
- Resultado de las pruebas automatizadas.

### Estado

El flujo principal de recepción, procesamiento, reparación y notificación fue ejecutado satisfactoriamente con LocalStack.

La grabación del video de defensa queda pendiente de incorporación al repositorio.