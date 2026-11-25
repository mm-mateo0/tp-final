"""Reparación convergente y coordinación durable por event_id."""
from botocore.exceptions import BotoCoreError, ClientError
from fenix.config.settings import client
from fenix.utils.state import load, save
from fenix.services.events import validate
from fenix.services.notifications import notify
from fenix.utils.errors import RetryableError, PermanentError, ValidationError

TRANSIENT_CODES = {"Throttling", "ThrottlingException", "RequestLimitExceeded",
                   "ServiceUnavailable", "InternalError", "RequestTimeout"}


def _cloud_error(error):
    code = error.response.get("Error", {}).get("Code", "")
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    if code in TRANSIENT_CODES or status >= 500:
        raise RetryableError("Fallo temporal de la API cloud") from error
    raise PermanentError(f"Fallo cloud no recuperable: {code or 'ClientError'}") from error


def repair(resource: dict, event_type: str) -> str:
    try:
        if event_type == "instance.stopped" and resource.get("type") == "ec2":
            ec2 = client("ec2")
            response = ec2.describe_instances(InstanceIds=[resource["id"]])
            instances = [i for r in response["Reservations"] for i in r["Instances"]]
            if not instances:
                raise PermanentError("La instancia del inventario no existe")
            observed_tags = {item["Key"]: item["Value"] for item in instances[0].get("Tags", [])}
            expected = resource.get("expected_tags", {})
            if any(observed_tags.get(key) != value for key, value in expected.items()):
                raise PermanentError("La instancia no conserva las etiquetas de propiedad esperadas")
            state = instances[0]["State"]["Name"]
            if state == "running":
                return "already_ok"
            if state in ("pending", "stopping"):
                raise RetryableError(f"La instancia todavía está en transición: {state}")
            if state != "stopped":
                raise PermanentError(f"Estado EC2 no reparable: {state}")
            ec2.start_instances(InstanceIds=[resource["id"]])
            check = ec2.describe_instances(InstanceIds=[resource["id"]])
            final_state = check["Reservations"][0]["Instances"][0]["State"]["Name"]
            if final_state != "running":
                raise RetryableError(f"Estado EC2 observado: {final_state}")
            return "repaired"
        if event_type == "bucket.tags_missing" and resource.get("type") == "s3":
            s3 = client("s3")
            bucket = resource["id"]
            try:
                current = s3.get_bucket_tagging(Bucket=bucket)["TagSet"]
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchTagSet", "NoSuchTagSetError"):
                    current = []
                else:
                    _cloud_error(error)
            tags = {item["Key"]: item["Value"] for item in current}
            expected = resource.get("expected_tags", {})
            ownership_keys = ("ManagedBy", "Project", "GroupId")
            if any(tags.get(key) != expected.get(key) for key in ownership_keys):
                raise PermanentError("El bucket no conserva las etiquetas de propiedad")
            changed = any(tags.get(key) != value for key, value in expected.items())
            if not changed:
                return "already_ok"
            tags.update(expected)
            s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": [
                {"Key": key, "Value": value} for key, value in sorted(tags.items())]})
            observed = s3.get_bucket_tagging(Bucket=bucket)["TagSet"]
            observed_map = {item["Key"]: item["Value"] for item in observed}
            if any(observed_map.get(k) != v for k, v in expected.items()):
                raise RetryableError("No se verificaron todas las etiquetas obligatorias")
            return "repaired"
        raise PermanentError("Recurso o tipo de evento no autorizado")
    except ClientError as error:
        _cloud_error(error)
    except BotoCoreError as error:
        raise RetryableError("Fallo de transporte al consultar el servicio cloud") from error


def handle(event: dict) -> None:
    inventory = load("data/inventory.json")
    clean = validate(event, inventory)
    ledger = load("data/events.json")
    event_id = clean["event_id"]
    existing = ledger.get(event_id)
    if existing and existing.get("event") != clean:
        raise PermanentError("Conflicto: event_id reutilizado con otro contenido")
    record = existing or {"event": clean, "attempts": 0, "repair_done": False,
                          "repair_result": None, "notified": False, "status": "pending"}
    record["attempts"] += 1
    ledger[event_id] = record
    save("data/events.json", ledger)
    if record["attempts"] <= clean["simulate_failures"]:
        raise RetryableError("Falla temporal simulada antes de reparar")
    resource = inventory[clean["resource_id"]]
    if not record["repair_done"]:
        result = repair(resource, clean["event_type"])
        record["repair_result"] = result
        record["repair_done"] = True
        record["status"] = "repaired"
        ledger[event_id] = record
        save("data/events.json", ledger)
    if not record["notified"]:
        summary = (f"Fénix: {clean['event_type']} en {clean['resource_id']}; "
                   f"resultado={record['repair_result']}; evento={event_id}")
        notify(summary)
        record["notified"] = True
        record["status"] = "completed"
        ledger[event_id] = record
        save("data/events.json", ledger)
