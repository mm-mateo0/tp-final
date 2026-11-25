# Proyecto Fénix — Sistema de Autorreparación de Infraestructura

## Objetivo del sistema
Fénix recibe alertas de laboratorio mediante un webhook autenticado con HMAC-SHA256. El receptor valida el evento y lo publica en una cola SQS estándar. Un worker independiente procesa el mensaje, consulta el estado real de un recurso emulado en LocalStack, aplica una reparación convergente y envía una notificación. El mensaje solo se confirma después de completar reparación y aviso.

El laboratorio contempla dos casos: `node-01` (EC2 mock: `stopped` → `running`) y `bucket-01` (S3: recuperar etiquetas obligatorias). Una instancia EC2 mock no es una máquina virtual Linux real.

## Responsable del proyecto

| Modalidad | Apellido y nombre | Correo | Responsabilidad | Pruebas a defender |
|---|---|---|---|---|
| Trabajo individual | Mateo Ismael Liendro | No consignado | Desarrollo e integración completa del sistema | Todas las pruebas del proyecto |

El proyecto se desarrolla y presenta de manera individual. La responsabilidad sobre la implementación, integración, pruebas y defensa corresponde al estudiante indicado.

## Prerrequisitos y versiones
- Windows 10/11 de 64 bits o Linux/macOS.
- Python 3.11 o superior.
- Docker Desktop con WSL 2 y Docker Compose.
- Imagen de LocalStack aprobada por la cátedra y token si el plan lo requiere.
- Git recomendado para versionado.
- No se utilizan credenciales reales de AWS. Python corre en el equipo anfitrión; LocalStack corre en Docker.

## Instalación desde cero (PowerShell)
Desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copiar el valor generado en `WEBHOOK_SECRET` dentro de `.env`. Completar `LOCALSTACK_AUTH_TOKEN` solo si la imagen adoptada lo requiere. No compartir ni subir `.env`.

Después de instalar las dependencias en el entorno definitivo, generar el archivo de versiones efectivamente utilizadas:

```powershell
python -m pip freeze > requirements-lock.txt
```

## Variables de entorno
Ver `.env.example`. Las variables principales son:
- `AWS_ENDPOINT_URL`: debe apuntar a `http://localhost:4566`.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: credenciales ficticias para LocalStack.
- `AWS_DEFAULT_REGION`: región del laboratorio.
- `GROUP_ID` y `QUEUE_PREFIX`: identificadores del grupo y de las colas.
- `WEBHOOK_SECRET`: clave compartida del webhook, mínimo 16 caracteres.
- `NOTIFY_PROVIDER`: `console`, `telegram` o `slack`.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` o `SLACK_WEBHOOK_URL`: solo para el proveedor elegido.
- `LOCALSTACK_IMAGE` y `LOCALSTACK_AUTH_TOKEN`: configuración de la imagen local.

## Arquitectura

```mermaid
flowchart TD
    A[Alerta JSON] --> B[Webhook FastAPI]
    B --> C[Validación HMAC y esquema]
    C --> D[SQS estándar]
    D --> E[Worker]
    E --> F[Inventario y ledger]
    E --> G[EC2 mock o S3]
    G --> H[Verificación del estado]
    H --> I[Telegram, Slack o consola]
    I --> J[ACK con ReceiptHandle]
    D --> K[DLQ por RedrivePolicy]
    E --> L[Logs JSON por QueueHandler]
    L --> M[QueueListener y gzip]
```

## Contratos de entrada y salida
El evento JSON tiene exactamente estos campos:

```json
{
  "schema_version": 1,
  "event_id": "evt-node-001",
  "event_type": "instance.stopped",
  "resource_id": "node-01",
  "occurred_at": "2026-10-22T18:00:00Z",
  "simulate_failures": 0
}
```

`schema_version` debe ser el entero 1. `event_id` y `resource_id` cumplen `[a-z0-9-]{3,32}`. `event_type` admite `instance.stopped` o `bucket.tags_missing`, según el tipo del alias en el inventario. `occurred_at` requiere UTC explícito. `simulate_failures` es un entero entre 0 y 5; no se acepta `bool`.

El receptor devuelve HTTP 202 únicamente después de que SQS confirme `send_message`. La respuesta contiene `status`, `event_id` y `message_id`. `MessageId` identifica el mensaje SQS; `ReceiptHandle` identifica la recepción actual y se usa para el ACK.

## Ejecución
1. Iniciar Docker Desktop.
2. Desde la carpeta del proyecto, iniciar LocalStack:

```powershell
docker compose up -d
```

3. Crear las colas y los recursos del laboratorio:

```powershell
python -m fenix.cli init-queues
python -m fenix.cli setup-demo
```

4. Terminal 1: iniciar el receptor:

```powershell
python -m uvicorn fenix.services.receiver:app --host 127.0.0.1 --port 8000 --workers 1 --env-file .env
```

5. Terminal 2: iniciar el worker:

```powershell
python -m fenix.cli worker
```

6. Terminal 3: generar una falla y enviar el evento:

```powershell
python -m fenix.cli fault node-01
python -m fenix.cli send examples/node-event.json
```

Para el bucket:

```powershell
python -m fenix.cli fault bucket-01
python -m fenix.cli send examples/bucket-event.json
```

Actualizar `occurred_at` y usar un `event_id` nuevo para cada incidencia nueva. Para un ensayo de dos fallas temporales, copiar el JSON y cambiar `event_id` y `simulate_failures` a 2. Para DLQ, utilizar otro ID y `simulate_failures` a 5.

## Reintentos, DLQ e idempotencia
La cola principal es estándar y utiliza `VisibilityTimeout=45`, retención de cuatro días y `RedrivePolicy` hacia una DLQ con `maxReceiveCount=3`. Ante un fallo, el worker cambia la visibilidad del mensaje actual con demora `min(30, 2 ** ApproximateReceiveCount)`. No crea una copia nueva del mensaje.

El ledger `data/events.json` conserva el evento asociado a cada `event_id`, cantidad de intentos, reparación, resultado, aviso y estado. Si un `event_id` reaparece con otro contenido, se rechaza como conflicto. Las etapas verificadas no se repiten al volver a recibir un duplicado. No se promete entrega exactamente una vez: SQS estándar ofrece entrega al menos una vez y existe una ventana entre un efecto externo y su persistencia local.

## Pruebas
Ejecutar pruebas unitarias:

```powershell
python -m pytest -m base -v
```

Pruebas de integración (requieren LocalStack en ejecución y configuración correcta):

```powershell
python -m pytest -m integracion -v
```

| ID | Caso | Resultado esperado | Resultado observado |
|---|---|---|---|
| F01 | Crear colas y laboratorio dos veces | Sin duplicados | Pendiente de ejecutar |
| F02 | Nodo detenido y evento válido | Estado `running`, aviso y ACK | Pendiente de ejecutar |
| F03 | Bucket sin etiqueta Owner | Etiquetas obligatorias restauradas | Pendiente de ejecutar |
| F04–F07 | Firma, JSON y esquema inválidos | 401/400/422, sin publicar | Pruebas unitarias y HTTP por verificar |
| F08/F10 | Mensaje corrupto o persistente | Se conserva y llega a DLQ | Pendiente de integración |
| F09 | Dos fallas simuladas | Reintenta y completa en el tercer intento | Prueba unitaria incluida |
| F11/F12 | Duplicado y reinicio | No repite etapas confirmadas | Prueba unitaria incluida |
| F13 | SQS no disponible | HTTP 503 | Pendiente de integración |
| F14 | Error temporal de notificación | Reparación no se repite | Pendiente de ampliar/verificar |
| F15 | Mismo ID con contenido distinto | Conflicto sin sobrescribir ledger | Prueba unitaria incluida |
| F16 | Rotación gzip | Archivo comprimido con líneas JSON UTC | Prueba unitaria incluida |

No completar la columna de resultado observado hasta ejecutar cada prueba y guardar la evidencia correspondiente. Un test unitario no sustituye una prueba real de SQS/DLQ sobre LocalStack.

## Observabilidad y evidencia
Los logs se guardan en `logs/` como JSON Lines. `QueueHandler` entrega registros a una `queue.Queue` en memoria y `QueueListener` escribe en un archivo rotativo; esta cola de logging no reemplaza a SQS. Los históricos se comprimen con gzip. Cada proceso utiliza un archivo propio.

Guardar en `evidencias/` capturas o archivos anonimizados de logs nominales y de error, histórico gzip legible, consulta Boto3 del estado final y lectura de un mensaje real de la DLQ. Ocultar tokens, firmas, credenciales y URLs privadas.

## Limitaciones
- LocalStack emula las APIs; EC2 mock no ejecuta un sistema operativo.
- El ledger JSON presupone un solo proceso escritor.
- No existe una transacción distribuida entre SQS, el archivo local, el recurso cloud y el proveedor de avisos.
- Si el proceso cae después del envío externo y antes de guardar `notified`, podría repetirse el aviso.
- `NOTIFY_PROVIDER=console` sirve para desarrollo; la evidencia final requiere un envío real por Telegram o Slack.

## Limpieza del laboratorio
Detener primero el worker y el receptor. Conservar `data/inventory.json` mientras se necesite reconocer los recursos creados. Antes de eliminar recursos, consultar los IDs del inventario y borrar exclusivamente los recursos propios del grupo. No borrar recursos por nombre sin verificar sus etiquetas de propiedad.

## Video de defensa
Completar el vínculo y las marcas de tiempo después de grabar:

- Video: pendiente.
- Presentación y arquitectura: pendiente.
- Validación/HMAC y receptor: pendiente.
- SQS, worker, reparación e idempotencia: pendiente.
- Logs, notificación y pruebas: pendiente.

## Declaración de ayuda externa e IA
Se utilizó ChatGPT como apoyo para interpretar la consigna, revisar la plantilla, proponer y corregir código y preparar la defensa. El código final debe ser ejecutado, revisado y comprendido por el estudiante. Se deben declarar los cambios realizados y no presentar pruebas no ejecutadas como evidencia.
