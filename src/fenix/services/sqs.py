"""Operaciones SQS estándar, con redrive y reintento por visibilidad."""
import json
from fenix.config.settings import client


def ensure_queues(prefix: str) -> tuple[str, str]:
    sqs = client("sqs")
    dead = sqs.create_queue(QueueName=f"{prefix}-dlq",
        Attributes={"MessageRetentionPeriod": "1209600"})["QueueUrl"]
    arn = sqs.get_queue_attributes(QueueUrl=dead, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    work = sqs.create_queue(QueueName=f"{prefix}-events", Attributes={
        "VisibilityTimeout": "45", "MessageRetentionPeriod": "345600"})["QueueUrl"]
    policy = {"deadLetterTargetArn": arn, "maxReceiveCount": "3"}
    sqs.set_queue_attributes(QueueUrl=work, Attributes={
        "VisibilityTimeout": "45", "MessageRetentionPeriod": "345600",
        "RedrivePolicy": json.dumps(policy)})
    return work, dead


def queue_url(prefix: str) -> str:
    return client("sqs").get_queue_url(QueueName=f"{prefix}-events")["QueueUrl"]


def publish(url: str, event: dict, delay: int = 0) -> str:
    if type(delay) is not int or not 0 <= delay <= 900:
        raise ValueError("DelaySeconds debe estar entre 0 y 900")
    response = client("sqs").send_message(QueueUrl=url, MessageBody=json.dumps(event),
        DelaySeconds=delay, MessageAttributes={"EventId": {"DataType": "String",
        "StringValue": event["event_id"]}})
    return response["MessageId"]


def receive(url: str) -> list[dict]:
    response = client("sqs").receive_message(QueueUrl=url, MaxNumberOfMessages=1,
        WaitTimeSeconds=10, VisibilityTimeout=45,
        MessageSystemAttributeNames=["ApproximateReceiveCount"], MessageAttributeNames=["All"])
    return response.get("Messages", [])


def acknowledge(url: str, receipt: str) -> None:
    client("sqs").delete_message(QueueUrl=url, ReceiptHandle=receipt)


def retry_later(url: str, message: dict, minimum_delay: int | None = None) -> int:
    count = int(message["Attributes"]["ApproximateReceiveCount"])
    delay = min(30, 2 ** count)
    if minimum_delay is not None:
        delay = min(30, max(delay, int(minimum_delay)))
    client("sqs").change_message_visibility(QueueUrl=url,
        ReceiptHandle=message["ReceiptHandle"], VisibilityTimeout=delay)
    return delay
