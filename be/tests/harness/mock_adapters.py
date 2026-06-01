"""Mock 어댑터 — AWS 없이 로컬 테스트용."""

from __future__ import annotations


from shared.models import (
    ChangeRecord,
    Classification,
    CrawlData,
    FeedbackEntry,
    HospitalDescription,
    HospitalMeta,
    RelatedHospital,
    ServicesAndDoctors,
)


class MockDynamoAdapter:
    """인메모리 DynamoDB."""

    def __init__(self):
        self._hospitals: dict[str, HospitalMeta] = {}
        self._classifications: dict[str, Classification] = {}
        self._descriptions: dict[str, HospitalDescription] = {}
        self._services: dict[str, ServicesAndDoctors] = {}
        self._related: dict[str, list[RelatedHospital]] = {}
        self._feedback: dict[str, list[FeedbackEntry]] = {}
        self._changes: dict[str, list[ChangeRecord]] = {}

    # Hospitals
    def save_hospital_meta(self, meta: HospitalMeta) -> None:
        self._hospitals[meta.hospital_id] = meta

    def load_hospital_meta(self, hospital_id: str) -> HospitalMeta | None:
        return self._hospitals.get(hospital_id)

    def list_hospitals_by_sigungu(self, sigungu: str) -> list[HospitalMeta]:
        return [h for h in self._hospitals.values() if h.location.sigungu == sigungu]

    # Classifications
    def save_classification(self, data: Classification) -> None:
        self._classifications[data.hospital_id] = data

    def load_classification(self, hospital_id: str) -> Classification | None:
        return self._classifications.get(hospital_id)

    # Descriptions
    def save_description(self, data: HospitalDescription) -> None:
        self._descriptions[data.hospital_id] = data

    def load_description(self, hospital_id: str) -> HospitalDescription | None:
        return self._descriptions.get(hospital_id)

    # ServicesAndDoctors
    def save_services_and_doctors(self, hospital_id: str, data: ServicesAndDoctors) -> None:
        self._services[hospital_id] = data

    def load_services_and_doctors(self, hospital_id: str) -> ServicesAndDoctors | None:
        return self._services.get(hospital_id)

    # Related
    def save_related_hospitals(self, hospital_id: str, related: list[RelatedHospital]) -> None:
        self._related[hospital_id] = related

    def load_related_hospitals(self, hospital_id: str) -> list[RelatedHospital]:
        return self._related.get(hospital_id, [])

    # Feedback
    def save_feedback(self, entry: FeedbackEntry) -> None:
        if entry.hospital_id not in self._feedback:
            self._feedback[entry.hospital_id] = []
        self._feedback[entry.hospital_id].append(entry)

    def get_feedback_for_hospital(self, hospital_id: str) -> list[FeedbackEntry]:
        return self._feedback.get(hospital_id, [])

    def check_duplicate_feedback(self, hospital_id: str, device_id: str) -> bool:
        entries = self._feedback.get(hospital_id, [])
        return any(e.device_id == device_id for e in entries)

    # Changes
    def save_change_record(self, record: ChangeRecord) -> None:
        if record.hospital_id not in self._changes:
            self._changes[record.hospital_id] = []
        self._changes[record.hospital_id].append(record)

    def load_recent_changes(self, hospital_id: str, limit: int = 2) -> list[ChangeRecord]:
        changes = self._changes.get(hospital_id, [])
        return sorted(changes, key=lambda c: c.changed_at, reverse=True)[:limit]


class MockS3Adapter:
    """인메모리 S3."""

    def __init__(self):
        self._store: dict[str, CrawlData] = {}

    def save_crawl_data(self, hospital_id: str, data: CrawlData) -> str:
        self._store[hospital_id] = data
        return f"s3://mock-bucket/crawl/{hospital_id}/data.json"

    def load_crawl_data(self, hospital_id: str) -> CrawlData | None:
        return self._store.get(hospital_id)


class MockSQSAdapter:
    """인메모리 SQS — 발행된 메시지를 리스트에 저장."""

    def __init__(self):
        self.messages: dict[str, list[dict]] = {}

    def send_message(self, queue_name: str, body: dict) -> str:
        if queue_name not in self.messages:
            self.messages[queue_name] = []
        self.messages[queue_name].append(body)
        return f"mock-msg-{len(self.messages[queue_name])}"

    def send_batch(self, queue_name: str, messages: list[dict]) -> int:
        if queue_name not in self.messages:
            self.messages[queue_name] = []
        self.messages[queue_name].extend(messages)
        return len(messages)
