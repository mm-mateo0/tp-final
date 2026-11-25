"""Preparación idempotente del inventario de laboratorio y fallas controladas."""
from botocore.exceptions import ClientError
import time
from fenix.config.settings import client
from fenix.services.cloud_support import aws_tags, mock_inputs, create_bucket, create_group, create_instance
from fenix.utils.state import load, save
from fenix.utils.validation import identifier
from fenix.utils.errors import ValidationError, PermanentError


def _owned(tags, group):
    values = {tag.get("Key"): tag.get("Value") for tag in tags or []}
    return values.get("ManagedBy") == "ppa2" and values.get("Project") == "fenix" and values.get("GroupId") == group


def setup_demo(group: str) -> dict:
    group = identifier(group)
    path = "data/inventory.json"
    inventory = load(path)
    base = {"ManagedBy": "ppa2", "Project": "fenix", "GroupId": group, "Owner": group}
    ec2 = client("ec2")
    vpc_id, image_id = mock_inputs()

    sg_name = f"fenix-{group}-sg"
    groups = ec2.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [sg_name]}, {"Name": "vpc-id", "Values": [vpc_id]}])["SecurityGroups"]
    if groups:
        sg = groups[0]
        if not _owned(sg.get("Tags"), group):
            raise PermanentError("El grupo de seguridad existente no pertenece al laboratorio")
        sg_id = sg["GroupId"]
    else:
        sg_id = create_group(sg_name, vpc_id, base)

    node = inventory.get("node-01")
    if node and node.get("id"):
        found = ec2.describe_instances(InstanceIds=[node["id"]])
        instances = [i for r in found["Reservations"] for i in r["Instances"]]
    else:
        found = ec2.describe_instances(Filters=[
            {"Name": "tag:Project", "Values": ["fenix"]},
            {"Name": "tag:GroupId", "Values": [group]},
            {"Name": "tag:Name", "Values": [f"fenix-{group}-node"]}])
        instances = [i for r in found["Reservations"] for i in r["Instances"]]
    if instances:
        instance = instances[0]
        if not _owned(instance.get("Tags"), group):
            raise PermanentError("La instancia existente no pertenece al laboratorio")
        instance_id = instance["InstanceId"]
    else:
        token = f"fenix-{group}-node-v1"[:64]
        instance_id = create_instance(image_id, sg_id, token,
            {**base, "Name": f"fenix-{group}-node"})
    inventory["node-01"] = {"type": "ec2", "id": instance_id,
        "security_group_id": sg_id, "expected_tags": base}
    save(path, inventory)

    bucket_name = f"fenix-{group}-demo".lower()
    s3 = client("s3")
    try:
        s3.head_bucket(Bucket=bucket_name)
        try:
            tags_now = s3.get_bucket_tagging(Bucket=bucket_name)["TagSet"]
            tag_map = {x["Key"]: x["Value"] for x in tags_now}
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in ("NoSuchTagSet", "NoSuchTagSetError"):
                raise
            tag_map = {}
        if tag_map and not _owned(tags_now, group):
            raise PermanentError("El bucket existente no pertenece al laboratorio")
        if not tag_map:
            recorded = inventory.get("bucket-01", {})
            if recorded.get("id") != bucket_name or recorded.get("type") != "s3":
                raise PermanentError("No se adopta un bucket existente sin etiquetas de propiedad")
            s3.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": aws_tags(base)})
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in ("404", "NoSuchBucket") or status == 404:
            create_bucket(bucket_name, base)
        else:
            raise
    inventory["bucket-01"] = {"type": "s3", "id": bucket_name, "expected_tags": base}
    save(path, inventory)
    return inventory


def inject_fault(alias: str) -> None:
    if alias not in ("node-01", "bucket-01"):
        raise ValidationError("Alias de laboratorio no permitido")
    inventory = load("data/inventory.json")
    if alias not in inventory:
        raise ValidationError("El alias no existe en el inventario")
    resource = inventory[alias]
    if alias == "node-01":
        ec2 = client("ec2")
        response = ec2.describe_instances(InstanceIds=[resource["id"]])
        instance = response["Reservations"][0]["Instances"][0]
        observed = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
        if any(observed.get(k) != v for k, v in resource.get("expected_tags", {}).items()):
            raise PermanentError("La instancia no pertenece al inventario esperado")
        ec2.stop_instances(InstanceIds=[resource["id"]])
        for _ in range(10):
            response = ec2.describe_instances(InstanceIds=[resource["id"]])
            state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
            if state == "stopped":
                return
            if state != "stopping":
                raise PermanentError(f"No se pudo detener la instancia: {state}")
            time.sleep(0.5)
        raise PermanentError("La instancia no llegó a stopped dentro del tiempo de espera")
    s3 = client("s3")
    try:
        current = s3.get_bucket_tagging(Bucket=resource["id"])["TagSet"]
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in ("NoSuchTagSet", "NoSuchTagSetError"):
            current = []
        else:
            raise
    current_map = {tag["Key"]: tag["Value"] for tag in current}
    expected = resource.get("expected_tags", {})
    if any(current_map.get(k) != expected.get(k) for k in ("ManagedBy", "Project", "GroupId")):
        raise PermanentError("El bucket no pertenece al inventario esperado")
    remaining = [tag for tag in current if tag["Key"] != "Owner"]
    if remaining:
        s3.put_bucket_tagging(Bucket=resource["id"], Tagging={"TagSet": remaining})
    else:
        # S3 no ofrece una operación para guardar un TagSet vacío; borrar etiquetas.
        s3.delete_bucket_tagging(Bucket=resource["id"])
