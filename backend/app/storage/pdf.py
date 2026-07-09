import io
import uuid

import boto3
from botocore.client import Config
from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()


class StorageService:
    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.minio_secure else 'http'}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def upload_file(self, file: UploadFile, organization_id: uuid.UUID) -> tuple[str, int]:
        self.ensure_bucket()
        content = file.file.read()
        size = len(content)
        key = f"{organization_id}/{uuid.uuid4()}/{file.filename}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=file.content_type or "application/pdf",
        )
        return key, size

    def upload_bytes(
        self, data: bytes, organization_id: uuid.UUID, filename: str, content_type: str = "application/pdf"
    ) -> tuple[str, int]:
        self.ensure_bucket()
        key = f"{organization_id}/{uuid.uuid4()}/{filename}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key, len(data)

    def download_bytes(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        return response["Body"].read()

    def get_presigned_url(self, storage_key: str, expires: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=expires,
        )


storage_service = StorageService()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts).strip()
