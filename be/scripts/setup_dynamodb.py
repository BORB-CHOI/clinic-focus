"""
DynamoDB 테이블 생성 스크립트 (지원 계정, 인스턴스 프로파일 사용).

실행:
    python be/scripts/setup_dynamodb.py

이미 테이블이 있으면 ResourceInUseException 이 발생하고 무시된다.
"""
import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-1")
PREFIX = os.environ.get("TABLE_PREFIX", "")


def tbl(name: str) -> str:
    return f"{PREFIX}{name}" if PREFIX else name


def create_table_if_not_exists(ddb, **kwargs):
    try:
        table = ddb.create_table(**kwargs)
        table.wait_until_exists()
        print(f"  생성됨: {kwargs['TableName']}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"  이미 존재: {kwargs['TableName']}")
        else:
            raise


def main():
    ddb = boto3.resource("dynamodb", region_name=REGION)

    print("DynamoDB 테이블 생성 시작...")

    # Hospitals — PK: hospital_id, GSI: sigungu-index(sigungu)
    create_table_if_not_exists(
        ddb,
        TableName=tbl("Hospitals"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "hospital_id", "AttributeType": "S"},
            {"AttributeName": "sigungu", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "sigungu-index",
            "KeySchema": [{"AttributeName": "sigungu", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )

    # Classifications — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("Classifications"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # HospitalDescriptions — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("HospitalDescriptions"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # ServicesAndDoctors — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("ServicesAndDoctors"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # RelatedHospitals — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("RelatedHospitals"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Feedback — PK: hospital_id, SK: feedback_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("Feedback"),
        KeySchema=[
            {"AttributeName": "hospital_id", "KeyType": "HASH"},
            {"AttributeName": "feedback_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "hospital_id", "AttributeType": "S"},
            {"AttributeName": "feedback_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # ChangeHistory — PK: hospital_id, SK: changed_at
    create_table_if_not_exists(
        ddb,
        TableName=tbl("ChangeHistory"),
        KeySchema=[
            {"AttributeName": "hospital_id", "KeyType": "HASH"},
            {"AttributeName": "changed_at", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "hospital_id", "AttributeType": "S"},
            {"AttributeName": "changed_at", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    print("DynamoDB 테이블 생성 완료.")


if __name__ == "__main__":
    main()
