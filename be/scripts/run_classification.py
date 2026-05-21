"""크롤링 완료된 병원에 대해 AI 분류 실행 → DynamoDB 적재.

비성님 AI 모듈(classify_hospital, generate_description 등) 연동.
AI 모듈 완성 후 실행.

스펙: .claude/docs/API-BE-AI.md > BE 호출 패턴 예시 > 새 병원 등록 시
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter


def main():
    db = DynamoAdapter()
    s3 = S3Adapter()

    print("=" * 60)
    print("AI 분류 파이프라인 실행")
    print("=" * 60)

    # 크롤링 데이터 디렉토리에서 JSON 파일 목록
    crawl_dir = os.environ.get("CRAWL_DATA_DIR", os.path.expanduser("~/clinic-focus/data/crawl"))
    if not os.path.exists(crawl_dir):
        print("❌ 크롤링 데이터가 없습니다. crawl_all.py를 먼저 실행하세요.")
        return

    json_files = [f for f in os.listdir(crawl_dir) if f.endswith(".json")]
    print(f"  크롤링된 병원 수: {len(json_files)}개")

    # AI 모듈 import 시도
    try:
        from ai import (
            classify_hospital,
            generate_description,
            extract_services_and_doctors,
            find_related_hospitals,
            index_hospital,
        )
    except ImportError as e:
        print(f"❌ AI 모듈 import 실패: {e}")
        print("  → 비성님 AI 모듈이 완성되면 다시 실행하세요.")
        return

    success = 0
    failed = 0

    for i, filename in enumerate(json_files, 1):
        hospital_id = filename.replace(".json", "")

        try:
            # 1. 크롤링 데이터 로드
            crawl_data = s3.load_crawl_data(hospital_id)
            if not crawl_data or len(crawl_data.pages) == 0:
                continue

            hospital_meta = db.load_hospital_meta(hospital_id)
            if not hospital_meta:
                continue

            # 2. AI 분류
            classification = classify_hospital(crawl_data)

            # 3. 진료 항목·의료기기·의료진 추출
            services_and_doctors = extract_services_and_doctors(
                crawl_data=crawl_data,
                classification=classification,
                vision_results=[],
            )

            # 4. AI 통합 상세 설명 생성
            description = generate_description(
                classification=classification,
                detailed_signals=classification.detailed_signals,
                hospital_meta=hospital_meta,
            )

            # 5. 관련 병원 추천
            related = find_related_hospitals(
                hospital_id=hospital_id,
                location=hospital_meta.location,
                primary_focus=classification.primary_focus,
                excluded_services=services_and_doctors.excluded_services,
            )

            # 6. DynamoDB 적재
            db.save_classification(classification)
            db.save_description(description)
            db.save_services_and_doctors(hospital_id, services_and_doctors)
            db.save_related_hospitals(hospital_id, related)

            # 7. S3 Vectors 인덱싱 (벡터 검색용)
            embedding_text = "\n".join(p.text for p in description.paragraphs)
            index_hospital(
                hospital_id,
                classification,
                embedding_text,
                sido=hospital_meta.location.sido,
                sigungu=hospital_meta.location.sigungu,
                lat=hospital_meta.location.lat,
                lng=hospital_meta.location.lng,
            )

            success += 1
            print(f"  [{i}/{len(json_files)}] ✅ {hospital_meta.name} — {classification.primary_focus}")

        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(json_files)}] ❌ {hospital_id} — {e}")

    print("\n" + "=" * 60)
    print("AI 분류 완료!")
    print(f"  ✅ 성공: {success}개")
    print(f"  ❌ 실패: {failed}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
