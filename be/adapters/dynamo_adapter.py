"""DynamoDB 어댑터 — 단일 테이블 V2 (4 시그널 통합 single-table-design).

스키마: PK=hospital_id (S), SK=entity (S). 상세는 docs/plans/task-queue.md §3.

entity 종류는 docs/plans/task-queue.md §3-2 표 참조. 본 어댑터는 V1(7-table)에서 이미
사용되던 typed 메서드 (save_hospital_meta · save_classification 등)를 유지하면서,
새 entity 종류(NAVER#PLACE · SITE#PAGES · INGEST#STATE …)는 generic primitive
(get_entity · put_entity · query_hospital_entities · delete_entity)로 처리한다.

GSI 2개 — 모두 META 항목만 sparse 인덱싱 (다른 entity 는 키 attribute 자체가 없어 GSI 에 안 나타남):
  - sigungu-specialty-index: PK=sigungu_specialty(S "강남구#피부과") · SK=confidence_score(N desc)
  - geo-index:              PK=geohash_prefix(S)                · SK=lat_lng(S "{lat}#{lng}")

GSI 인덱싱 키(sigungu_specialty·confidence_score)는 분류 완료 시점에 META 에 patch 된다.
META 만 있고 분류 전인 병원은 GSI 에 등장하지 않음 — 그게 의도된 동작.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

from shared.models import (
    ChangeRecord,
    Classification,
    FeedbackEntry,
    HospitalDescription,
    HospitalMeta,
    RelatedHospital,
    ServicesAndDoctors,
)

TABLE_NAME = os.environ.get("DYNAMO_TABLE", "kmuproj-10-clinic-Main")

# entity 상수 — task-queue.md §3-2 의 SK 값과 1:1
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
    if isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(i) for i in obj]
    return obj


def _strip_meta_attrs(item: dict) -> dict:
    """META 아이템에서 PK/SK/GSI denormalized 필드를 빼고 HospitalMeta 로 파싱 가능한 dict 반환.

    DynamoDB 가 숫자를 Decimal 로 돌려주는데 Pydantic v2 가 float 타입 어노테이션에
    Decimal 을 자동 coerce 해 주긴 하지만, location.lat / location.lng 만큼은 명시적으로
    float 로 되돌려 직렬화 시 표현 일관성을 보장한다 (FE 가 number 기대).
    """
    drop = {"entity", "sigungu", "sido", "sigungu_specialty", "confidence_score",
            "geohash_prefix", "lat_lng"}
    cleaned = {k: v for k, v in item.items() if k not in drop}

    loc = cleaned.get("location")
    if isinstance(loc, dict):
        for k in ("lat", "lng"):
            if isinstance(loc.get(k), Decimal):
                loc[k] = float(loc[k])
    return cleaned


class DynamoAdapter:
    def __init__(self) -> None:
        self._resource = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
        self._table = self._resource.Table(TABLE_NAME)

    # ── Generic entity primitives ───────────────────────────────────────────
    # 신규 entity 종류 (NAVER#PLACE · SITE#PAGES · INGEST#STATE 등) 는 별도 typed 메서드
    # 추가 전까지 이 primitives 로 처리. caller 가 직접 dict 조립.

    def get_entity(self, hospital_id: str, entity: str) -> dict | None:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": entity})
        return resp.get("Item")

    def put_entity(self, hospital_id: str, entity: str, payload: dict) -> None:
        """payload 는 PK/SK 를 포함하지 않은 본문. 어댑터가 PK/SK 와 float→Decimal 변환을 책임."""
        item = _float_to_decimal(payload)
        item["hospital_id"] = hospital_id
        item["entity"] = entity
        self._table.put_item(Item=item)

    def delete_entity(self, hospital_id: str, entity: str) -> None:
        self._table.delete_item(Key={"hospital_id": hospital_id, "entity": entity})

    def iter_all_hospital_ids(self) -> Iterator[str]:
        """META 가 있는 모든 hospital_id 를 페이지네이션 처리해 yield.

        scan 비용 발생 — 1만 풀커버에서도 META 만 projection 해 가져오면 RU/s 가벼움.
        KB ingest 일괄 처리 등에서 사용.
        """
        kwargs: dict[str, Any] = {
            "FilterExpression": Attr("entity").eq(E_META),
            "ProjectionExpression": "hospital_id",
        }
        while True:
            resp = self._table.scan(**kwargs)
            for item in resp.get("Items", []):
                yield item["hospital_id"]
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def query_hospital_entities(
        self,
        hospital_id: str,
        entity_prefix: str | None = None,
    ) -> list[dict]:
        """한 병원의 entity 들을 한 번에 가져온다. entity_prefix 가 주어지면 begins_with 필터."""
        key_cond = Key("hospital_id").eq(hospital_id)
        if entity_prefix is not None:
            key_cond = key_cond & Key("entity").begins_with(entity_prefix)

        items: list[dict] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": key_cond}
        while True:
            resp = self._table.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return items

    # ── Hospitals (META) ────────────────────────────────────────────────────

    def save_hospital_meta(self, meta: HospitalMeta) -> None:
        """META 저장. sigungu/sido 는 GSI 폴백 Scan + 일관성 위해 denormalize.

        sigungu_specialty 와 confidence_score 는 분류 완료 시점에 ``save_classification``
        이 같은 META 아이템에 patch 한다 — 분류 전 병원은 sigungu-specialty-index 에 등장 X.
        lat/lng 가 있어도 geo-index 키(geohash_prefix·lat_lng)는 명시적으로 채우는
        쪽이 들어올 때까지 비워둔다 (geohash 라이브러리 결정 보류).
        """
        item = _float_to_decimal(meta.model_dump(mode="json"))
        item["entity"]   = E_META
        item["sigungu"]  = meta.location.sigungu
        item["sido"]     = meta.location.sido
        self._table.put_item(Item=item)

    def load_hospital_meta(self, hospital_id: str) -> HospitalMeta | None:
        resp = self._table.get_item(Key={"hospital_id": hospital_id, "entity": E_META})
        item = resp.get("Item")
        if not item:
            return None
        return HospitalMeta(**_strip_meta_attrs(item))

    def list_hospitals_by_sigungu(self, sigungu: str) -> list[HospitalMeta]:
        """sigungu-only 검색. 새 GSI(sigungu-specialty-index)는 PK 가 복합키라 sigungu
        단독으로는 쿼리 불가 → Scan + FilterExpression. PoC 단일 테이블 + 1만 row 가정이라
        용인. 1만 풀커버 이후 비용 측정 후 별도 GSI(sigungu-only) 추가 검토.
        """
        results: list[HospitalMeta] = []
        filter_expr = Attr("entity").eq(E_META) & Attr("sigungu").eq(sigungu)
        kwargs: dict[str, Any] = {"FilterExpression": filter_expr}
        while True:
            resp = self._table.scan(**kwargs)
            for item in resp.get("Items", []):
                results.append(HospitalMeta(**_strip_meta_attrs(item)))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return results

    def list_hospitals_by_sigungu_specialty(
        self,
        sigungu: str,
        standard_specialty: str,
        limit: int | None = None,
    ) -> list[HospitalMeta]:
        """sigungu + 표준 진료과목 복합 검색. confidence_score 내림차순 정렬됨."""
        composite = f"{sigungu}#{standard_specialty}"
        kwargs: dict[str, Any] = {
            "IndexName": "sigungu-specialty-index",
            "KeyConditionExpression": Key("sigungu_specialty").eq(composite),
            "ScanIndexForward": False,  # confidence_score 내림차순
        }
        if limit is not None:
            kwargs["Limit"] = limit

        results: list[HospitalMeta] = []
        while True:
            resp = self._table.query(**kwargs)
            for item in resp.get("Items", []):
                results.append(HospitalMeta(**_strip_meta_attrs(item)))
            if "LastEvaluatedKey" not in resp or (limit is not None and len(results) >= limit):
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return results[:limit] if limit is not None else results

    def update_website_url(self, hospital_id: str, url: str) -> None:
        self._table.update_item(
            Key={"hospital_id": hospital_id, "entity": E_META},
            UpdateExpression="SET contact.website_url = :url",
            ExpressionAttributeValues={":url": url},
        )

    # ── Classifications ─────────────────────────────────────────────────────

    def save_classification(self, data: Classification) -> None:
        """CLASSIFICATION entity 저장 + META 아이템에 GSI 키 denormalize.

        분류 완료 시점에야 sigungu_specialty(`{sigungu}#{standard_specialty}`) 와
        confidence_score 가 META 에 박힌다 → sigungu-specialty-index 에 등장 시작.
        META 가 없으면 정상 흐름 위반이므로 ValueError raise — silent skip 은 GSI 인덱싱이
        영원히 누락되는 위험을 캐스케이드 시킴.
        """
        item = _float_to_decimal(data.model_dump(mode="json"))
        item["entity"] = E_CLASSIFICATION
        self._table.put_item(Item=item)

        meta_item = self.get_entity(data.hospital_id, E_META)
        if not meta_item:
            raise ValueError(
                f"save_classification({data.hospital_id}): META 아이템이 없음. "
                "save_hospital_meta 선행 호출 필요."
            )
        sigungu = meta_item.get("sigungu") or meta_item.get("location", {}).get("sigungu")
        if not sigungu:
            raise ValueError(
                f"save_classification({data.hospital_id}): META 에 sigungu 없음 — GSI 키 patch 불가."
            )
        self._table.update_item(
            Key={"hospital_id": data.hospital_id, "entity": E_META},
            UpdateExpression="SET sigungu_specialty = :ss, confidence_score = :cs",
            ExpressionAttributeValues={
                ":ss": f"{sigungu}#{data.standard_specialty}",
                ":cs": Decimal(str(data.confidence.score)),
            },
        )

    def load_classification(self, hospital_id: str) -> Classification | None:
        resp = self._table.get_item(
            Key={"hospital_id": hospital_id, "entity": E_CLASSIFICATION}
        )
        item = resp.get("Item")
        if not item:
            return None
        item.pop("entity", None)
        return Classification(**item)

    # ── Descriptions ────────────────────────────────────────────────────────

    def save_description(self, data: HospitalDescription) -> None:
        item = _float_to_decimal(data.model_dump(mode="json"))
        item["entity"] = E_DESCRIPTION
        self._table.put_item(Item=item)

    def load_description(self, hospital_id: str) -> HospitalDescription | None:
        resp = self._table.get_item(
            Key={"hospital_id": hospital_id, "entity": E_DESCRIPTION}
        )
        item = resp.get("Item")
        if not item:
            return None
        item.pop("entity", None)
        return HospitalDescription(**item)

    # ── ServicesAndDoctors ──────────────────────────────────────────────────

    def save_services_and_doctors(
        self, hospital_id: str, data: ServicesAndDoctors
    ) -> None:
        item = _float_to_decimal(data.model_dump(mode="json"))
        item["hospital_id"] = hospital_id
        item["entity"]      = E_SERVICES
        self._table.put_item(Item=item)

    def load_services_and_doctors(self, hospital_id: str) -> ServicesAndDoctors | None:
        resp = self._table.get_item(
            Key={"hospital_id": hospital_id, "entity": E_SERVICES}
        )
        item = resp.get("Item")
        if not item:
            return None
        item.pop("hospital_id", None)
        item.pop("entity", None)
        return ServicesAndDoctors(**item)

    # ── Related Hospitals ───────────────────────────────────────────────────

    def save_related_hospitals(
        self, hospital_id: str, related: list[RelatedHospital]
    ) -> None:
        item = {
            "hospital_id": hospital_id,
            "entity":      E_RELATED,
            "related":     [r.model_dump(mode="json") for r in related],
        }
        self._table.put_item(Item=_float_to_decimal(item))

    def load_related_hospitals(self, hospital_id: str) -> list[RelatedHospital]:
        resp = self._table.get_item(
            Key={"hospital_id": hospital_id, "entity": E_RELATED}
        )
        item = resp.get("Item")
        if not item:
            return []
        return [RelatedHospital(**r) for r in item.get("related", [])]

    # ── Feedback ────────────────────────────────────────────────────────────

    def save_feedback(self, entry: FeedbackEntry) -> None:
        item = entry.model_dump(mode="json")
        item["entity"] = f"{E_FEEDBACK}#{entry.feedback_id}"
        self._table.put_item(Item=item)

    def get_feedback_for_hospital(self, hospital_id: str) -> list[FeedbackEntry]:
        items = self.query_hospital_entities(hospital_id, entity_prefix=f"{E_FEEDBACK}#")
        results = []
        for item in items:
            item.pop("entity", None)
            results.append(FeedbackEntry(**item))
        return results

    def check_duplicate_feedback(self, hospital_id: str, device_id: str) -> bool:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("hospital_id").eq(hospital_id) &
                Key("entity").begins_with(f"{E_FEEDBACK}#")
            ),
            FilterExpression=Attr("device_id").eq(device_id),
            Limit=1,
        )
        return len(resp.get("Items", [])) > 0

    # ── Change History ──────────────────────────────────────────────────────

    def save_change_record(self, record: ChangeRecord) -> None:
        item = record.model_dump(mode="json")
        item["entity"] = f"{E_HISTORY}#{record.changed_at}"
        self._table.put_item(Item=item)

    def load_recent_changes(
        self, hospital_id: str, limit: int = 2
    ) -> list[ChangeRecord]:
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

    # ── 병원 상세 전체 한 번에 조회 (single-table-design 핵심) ───────────────

    def load_hospital_all(self, hospital_id: str) -> dict:
        """hospital_id 기준 모든 entity 를 쿼리 1번으로 가져와 9영역 응답 조립용 dict 반환.

        새 entity (NAVER#*, SITE#*, INGEST#STATE 등) 는 typed 키 ``extras`` 아래에
        dict 그대로 담아 둠 — 호출자가 Phase B/C/D 진입 시 typed parser 로 후처리.
        """
        items = self.query_hospital_entities(hospital_id)
        result: dict[str, Any] = {
            "meta": None,
            "classification": None,
            "description": None,
            "services": None,
            "related": [],
            "feedback": [],
            "history": [],
            "extras": {},
        }
        for item in items:
            entity = item.get("entity", "")
            clean = {k: v for k, v in item.items() if k != "entity"}

            if entity == E_META:
                result["meta"] = HospitalMeta(**_strip_meta_attrs(item))
            elif entity == E_CLASSIFICATION:
                result["classification"] = Classification(**clean)
            elif entity == E_DESCRIPTION:
                result["description"] = HospitalDescription(**clean)
            elif entity == E_SERVICES:
                clean.pop("hospital_id", None)
                result["services"] = ServicesAndDoctors(**clean)
            elif entity == E_RELATED:
                result["related"] = [
                    RelatedHospital(**r) for r in clean.get("related", [])
                ]
            elif entity.startswith(f"{E_FEEDBACK}#"):
                result["feedback"].append(FeedbackEntry(**clean))
            elif entity.startswith(f"{E_HISTORY}#"):
                result["history"].append(ChangeRecord(**clean))
            else:
                # 새 entity 종류 — typed parser 미정. raw dict 그대로 보존.
                result["extras"][entity] = clean

        return result
