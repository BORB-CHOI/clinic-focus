"""DynamoDB 어댑터 — 단일 테이블 설계 (kmuproj-02-team3-backend).

테이블 구조:
  PK: hospital_id (String)
  SK: entity      (String)

entity 값:
  META              → HospitalMeta
  CLASSIFICATION    → Classification
  DESCRIPTION       → HospitalDescription
  SERVICES          → ServicesAndDoctors
  RELATED           → RelatedHospitals list
  FEEDBACK#{id}     → FeedbackEntry (병원당 여러 개)
  HISTORY#{iso}     → ClassificationChange (병원당 여러 개)

GSI:
  sigungu-index: sigungu(PK) + hospital_id(SK) — META 아이템에만 sigungu 필드 존재 (sparse)
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
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

TABLE_NAME = os.environ.get("DYNAMO_TABLE", "kmuproj-02-team3-backend")

# entity 상수
E_META           = "META"
E_CLASSIFICATION = "CLASSIFICATION"
E_DESCRIPTION    = "DESCRIPTION"
E_SERVICES       = "SERVICES"
E_RELATED        = "RELATED"
E_FEEDBACK       = "FEEDBACK"
E_HISTORY        = "HISTORY"


def _float_to_decimal(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_float_to_decimal(i) for i in obj]
    return obj


class DynamoAdapter:
    def __init__(self):
        self._resource = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        self._table = self._resource.Table(TABLE_NAME)

    # ── Hospitals (META) ──

    def save_hospital_meta(self, meta: HospitalMeta) -> None:
        item = _float_to_decimal(meta.model_dump(mode="json"))
        item["entity"]   = E_META
        item["sigungu"]  = meta.location.sigungu   # GSI sigungu-index 용
        item["sido"]     = meta.location.sido
        self._table.put_item(Item=item)

    def load_hospital_meta(self, hospital_id: str) -> HospitalMeta | None:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": E_META})
        item = resp.get("Item")
        if not item:
            return None
        item.pop("entity", None)
        item.pop("sigungu", None)
        item.pop("sido", None)
        return HospitalMeta(**item)

    def list_hospitals_by_sigungu(self, sigungu: str) -> list[HospitalMeta]:
        results = []
        kwargs: dict = {
            "IndexName": "sigungu-index",
            "KeyConditionExpression": Key("sigungu").eq(sigungu),
        }
        while True:
            resp = self._table.query(**kwargs)
            for item in resp.get("Items", []):
                item.pop("entity", None)
                item.pop("sigungu", None)
                item.pop("sido", None)
                results.append(HospitalMeta(**item))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return results

    # ── Classifications ──

    def save_classification(self, data: Classification) -> None:
        item = _float_to_decimal(data.model_dump(mode="json"))
        item["entity"] = E_CLASSIFICATION
        self._table.put_item(Item=item)

    def load_classification(self, hospital_id: str) -> Classification | None:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": E_CLASSIFICATION})
        item = resp.get("Item")
        if not item:
            return None
        item.pop("entity", None)
        return Classification(**item)

    # ── Descriptions ──

    def save_description(self, data: HospitalDescription) -> None:
        item = _float_to_decimal(data.model_dump(mode="json"))
        item["entity"] = E_DESCRIPTION
        self._table.put_item(Item=item)

    def load_description(self, hospital_id: str) -> HospitalDescription | None:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": E_DESCRIPTION})
        item = resp.get("Item")
        if not item:
            return None
        item.pop("entity", None)
        return HospitalDescription(**item)

    # ── ServicesAndDoctors ──

    def save_services_and_doctors(self, hospital_id: str, data: ServicesAndDoctors) -> None:
        item = _float_to_decimal(data.model_dump(mode="json"))
        item["hospital_id"] = hospital_id
        item["entity"]      = E_SERVICES
        self._table.put_item(Item=item)

    def load_services_and_doctors(self, hospital_id: str) -> ServicesAndDoctors | None:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": E_SERVICES})
        item = resp.get("Item")
        if not item:
            return None
        item.pop("hospital_id", None)
        item.pop("entity", None)
        return ServicesAndDoctors(**item)

    # ── Related Hospitals ──

    def save_related_hospitals(self, hospital_id: str, related: list[RelatedHospital]) -> None:
        item = {
            "hospital_id": hospital_id,
            "entity":      E_RELATED,
            "related":     [r.model_dump(mode="json") for r in related],
        }
        self._table.put_item(Item=item)

    def load_related_hospitals(self, hospital_id: str) -> list[RelatedHospital]:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": E_RELATED})
        item = resp.get("Item")
        if not item:
            return []
        return [RelatedHospital(**r) for r in item.get("related", [])]

    def update_website_url(self, hospital_id: str, url: str) -> None:
        self._table.update_item(
            Key={"hospital_id": hospital_id, "entity": E_META},
            UpdateExpression="SET contact.website_url = :url",
            ExpressionAttributeValues={":url": url},
        )

    # ── Feedback ──

    def save_feedback(self, entry: FeedbackEntry) -> None:
        item = entry.model_dump(mode="json")
        item["entity"] = f"{E_FEEDBACK}#{entry.feedback_id}"
        self._table.put_item(Item=item)

    def get_feedback_for_hospital(self, hospital_id: str) -> list[FeedbackEntry]:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("hospital_id").eq(hospital_id) &
                Key("entity").begins_with(f"{E_FEEDBACK}#")
            ),
        )
        results = []
        for item in resp.get("Items", []):
            item.pop("entity", None)
            results.append(FeedbackEntry(**item))
        return results

    def check_duplicate_feedback(self, hospital_id: str, device_id: str) -> bool:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("hospital_id").eq(hospital_id) &
                Key("entity").begins_with(f"{E_FEEDBACK}#")
            ),
            FilterExpression="device_id = :did",
            ExpressionAttributeValues={":did": device_id},
            Limit=1,
        )
        return len(resp.get("Items", [])) > 0

    # ── Change History ──

    def save_change_record(self, record: ChangeRecord) -> None:
        item = record.model_dump(mode="json")
        item["entity"] = f"{E_HISTORY}#{record.changed_at}"
        self._table.put_item(Item=item)

    def load_recent_changes(self, hospital_id: str, limit: int = 2) -> list[ChangeRecord]:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("hospital_id").eq(hospital_id) &
                Key("entity").begins_with(f"{E_HISTORY}#")
            ),
            ScanIndexForward=False,
            Limit=limit,
        )
        results = []
        for item in resp.get("Items", []):
            item.pop("entity", None)
            results.append(ChangeRecord(**item))
        return results

    # ── 병원 상세 전체 한 번에 조회 (단일 테이블 설계 핵심) ──

    def load_hospital_all(self, hospital_id: str) -> dict:
        """hospital_id 기준 모든 entity를 쿼리 1번으로 가져온다."""
        resp = self._table.query(
            KeyConditionExpression=Key("hospital_id").eq(hospital_id),
        )
        result: dict = {
            "meta": None,
            "classification": None,
            "description": None,
            "services": None,
            "related": [],
            "feedback": [],
            "history": [],
        }
        for item in resp.get("Items", []):
            entity = item.get("entity", "")
            clean = {k: v for k, v in item.items() if k != "entity"}

            if entity == E_META:
                clean.pop("sigungu", None)
                clean.pop("sido", None)
                result["meta"] = HospitalMeta(**clean)
            elif entity == E_CLASSIFICATION:
                result["classification"] = Classification(**clean)
            elif entity == E_DESCRIPTION:
                result["description"] = HospitalDescription(**clean)
            elif entity == E_SERVICES:
                clean.pop("hospital_id", None)
                result["services"] = ServicesAndDoctors(**clean)
            elif entity == E_RELATED:
                result["related"] = [RelatedHospital(**r) for r in clean.get("related", [])]
            elif entity.startswith(f"{E_FEEDBACK}#"):
                result["feedback"].append(FeedbackEntry(**clean))
            elif entity.startswith(f"{E_HISTORY}#"):
                result["history"].append(ChangeRecord(**clean))

        return result
