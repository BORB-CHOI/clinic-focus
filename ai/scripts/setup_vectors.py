"""
S3 Vectors 버킷 + 인덱스 생성 스크립트 (개인 계정, AI_AWS_* 환경변수 사용).

실행:
    python ai/scripts/setup_vectors.py

이미 존재하면 에러 없이 skip 된다.
"""
import os
import sys


def _check_env() -> str:
    has_keys = os.environ.get("AI_AWS_ACCESS_KEY_ID") and os.environ.get("AI_AWS_SECRET_ACCESS_KEY")
    has_profile = os.environ.get("AI_AWS_PROFILE")
    bucket = os.environ.get("S3_VECTOR_BUCKET")
    if not (has_keys or has_profile):
        print("오류: AI_AWS_ACCESS_KEY_ID + AI_AWS_SECRET_ACCESS_KEY 또는 AI_AWS_PROFILE 을 설정하세요.")
        sys.exit(1)
    if not bucket:
        print("오류: S3_VECTOR_BUCKET 환경변수를 설정하세요. (예: username-hospital-vectors)")
        sys.exit(1)
    return bucket


def main():
    bucket_name = _check_env()
    index_name = os.environ.get("S3_VECTOR_INDEX", "hospital-index")

    from ai.core.aws_clients import get_s3vectors_client
    client = get_s3vectors_client()

    # 1. 버킷 생성
    try:
        client.create_vector_bucket(vectorBucketName=bucket_name)
        print(f"  버킷 생성됨: {bucket_name}")
    except Exception as e:
        if "already exists" in str(e).lower() or "BucketAlreadyExists" in str(type(e).__name__):
            print(f"  버킷 이미 존재: {bucket_name}")
        else:
            print(f"  버킷 생성 실패: {e}")
            raise

    # 2. 인덱스 생성 (차원 1024 = Titan Embed Text v2)
    try:
        client.create_index(
            vectorBucketName=bucket_name,
            indexName=index_name,
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
        )
        print(f"  인덱스 생성됨: {index_name} (bucket={bucket_name}, dim=1024, cosine)")
    except Exception as e:
        if "already exists" in str(e).lower() or "IndexAlreadyExists" in str(type(e).__name__):
            print(f"  인덱스 이미 존재: {index_name}")
        else:
            print(f"  인덱스 생성 실패: {e}")
            raise

    print("S3 Vectors 설정 완료.")


if __name__ == "__main__":
    main()
