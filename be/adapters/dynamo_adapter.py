"""DynamoDB 어댑터 — 실제 AWS 호출."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from shared.models import (
    ChangeRecord,
    Classification,
    CrawlData,
    FeedbackEntry,
    FeedbackStats,
    HospitalDescription,
    HospitalMeta,
    RelatedHospital,
    ServicesAndDoctors,
)

TABLE_PREFIX = os.environ.get("TABLE_PREFIX", "")


def _table_name(name: str) -> str:
    return f"{TABLE_PREFIX}{name}" if TABLE_PREFIX else name


class DynamoAdapter:
    def __init__(self):
        self._resource = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))

    def _table(self, name: str):
        return self._resource.Table(_table_name(name))

    # ── Hospitals ──

    def save_hospital_meta(self, meta: HospitalMeta) -> None:
        self._table("Hospitals").put_item(Item=meta.model_dump(mode="json"))

    def load_hospital_meta(self, hospital_id: str) -> HospitalMeta | None:
        resp = self._table("Hospitals").get_item(Key={"hospital_id": hospital_id})
        item = resp.get("Item")
        return HospitalMeta(**item) if item else None

    def list_hospitals_by_sigungu(self, sigungu: str) -> list[HospitalMeta]:
        resp = self._table("Hospitals").query(
            IndexName="sigungu-index",
            KeyConditionExpression=Key("sigungu").eq(sigungu),
        )
        return [HospitalMeta(**item) for item in resp.get("Items", [])]

    # ── Classifications ──

    def save_classification(self, data: Classification) -> None:
        self._table("Classifications").put_item(Item=data.model_dump(mode="json"))

    def load_classification(self, hospital_id: str) -> Classification | None:
        resp = self._table("Classifications").get_item(Key={"hospital_id": hospital_id})
        item = resp.get("Item")
        return Classification(**item) if item else None

    # ── Descriptions ──

    def save_description(self, data: HospitalDescription) -> None:
        self._table("HospitalDescriptions").put_item(Item=data.model_dump(mode="json"))

    def load_description(self, hospital_id: str) -> HospitalDescription | None:
        resp = self._table("HospitalDescriptions").get_item(Key={"hospital_id": hospital_id})
        item = resp.get("Item")
        return HospitalDescription(**item) if item else None

    # ── ServicesAndDoctors ──

    def save_services_and_doctors(self, hospital_id: str, data: ServicesAndDoctors) -> None:
        item = data.model_dump(mode="json")
        item["hospital_id"] = hospital_id
        self._table("ServicesAndDoctors").put_item(Item=item)

    def load_services_and_doctors(self, hospital_id: str) -> ServicesAndDoctors | None:
        resp = self._table("ServicesAndDoctors").get_item(Key={"hospital_id": hospital_id})
        item = resp.get("Item")
        if not item:
            return None
        item.pop("hospital_id", None)
        return ServicesAndDoctors(**item)

    # ── Related Hospitals ──

    def save_related_hospitals(self, hospital_id: str, related: list[RelatedHospital]) -> None:
        item = {
            "hospital_id": hospital_id,
            "related": [r.model_dump(mode="json") for r in related],
        }
        self._table("RelatedHospitals").put_item(Item=item)

    def load_related_hospitals(self, hospital_id: str) -> list[RelatedHospital]:
        resp = self._table("RelatedHospitals").get_item(Key={"hospital_id": hospital_id})
        item = resp.get("Item")
        if not item:
            return []
        return [RelatedHospital(**r) for r in item.get("related", [])]

    # ── Feedback ──

    def save_feedback(self, entry: FeedbackEntry) -> None:
        self._table("Feedback").put_item(Item=entry.model_dump(mode="json"))

    def get_feedback_for_hospital(self, hospital_id: str) -> list[FeedbackEntry]:
        resp = self._table("Feedback").query(
            KeyConditionExpression=Key("hospital_id").eq(hospital_id),
        )
        return [FeedbackEntry(**item) for item in resp.get("Items", [])]

    def check_duplicate_feedback(self, hospital_id: str, device_id: str) -> bool:
        resp = self._table("Feedback").query(
            KeyConditionExpression=Key("hospital_id").eq(hospital_id),
            FilterExpression="device_id = :did",
            ExpressionAttributeValues={":did": device_id},
            Limit=1,
        )
        return len(resp.get("Items", [])) > 0

    # ── Change History ──

    def save_change_record(self, record: ChangeRecord) -> None:
        self._table("ChangeHistory").put_item(Item=record.model_dump(mode="json"))

    def load_recent_changes(self, hospital_id: str, limit: int = 2) -> list[ChangeRecord]:
        resp = self._table("ChangeHistory").query(
            KeyConditionExpression=Key("hospital_id").eq(hospital_id),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [ChangeRecord(**item) for item in resp.get("Items", [])]
