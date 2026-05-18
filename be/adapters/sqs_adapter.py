"""SQS 어댑터 — 메시지 큐 발행."""

from __future__ import annotations

import json
import os

import boto3


class SQSAdapter:
    def __init__(self):
        self._client = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
        self._queue_urls: dict[str, str] = {}

    def _get_queue_url(self, queue_name: str) -> str:
        if queue_name not in self._queue_urls:
            resp = self._client.get_queue_url(QueueName=queue_name)
            self._queue_urls[queue_name] = resp["QueueUrl"]
        return self._queue_urls[queue_name]

    def send_message(self, queue_name: str, body: dict) -> str:
        """메시지 발행. message_id 반환."""
        url = self._get_queue_url(queue_name)
        resp = self._client.send_message(
            QueueUrl=url,
            MessageBody=json.dumps(body, ensure_ascii=False),
        )
        return resp["MessageId"]

    def send_batch(self, queue_name: str, messages: list[dict]) -> int:
        """최대 10개씩 배치 발행. 발행된 총 개수 반환."""
        url = self._get_queue_url(queue_name)
        sent = 0
        for i in range(0, len(messages), 10):
            batch = messages[i : i + 10]
            entries = [
                {"Id": str(idx), "MessageBody": json.dumps(msg, ensure_ascii=False)}
                for idx, msg in enumerate(batch)
            ]
            self._client.send_message_batch(QueueUrl=url, Entries=entries)
            sent += len(batch)
        return sent
