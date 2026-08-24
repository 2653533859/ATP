"""
MinIO 客户端封装

提供：
  - upload_file      上传本地文件
  - upload_bytes     上传字节内容
  - download_file    下载到本地路径
  - read_bytes       读取为字节
  - presigned_url    生成预签名访问 URL
  - delete_file      删除对象
  - ensure_bucket    确保 Bucket 存在（启动时调用）
"""

import io
import logging
from pathlib import Path
from minio import Minio
from minio.error import S3Error
import urllib3
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
            http_client=urllib3.PoolManager(
                maxsize=10,
                block=True,
                timeout=urllib3.Timeout(
                    connect=settings.MINIO_CONNECT_TIMEOUT_SECONDS,
                    read=settings.MINIO_READ_TIMEOUT_SECONDS,
                ),
                retries=urllib3.Retry(total=0),
            ),
        )
    return _client


def ensure_bucket() -> None:
    """确保默认 Bucket 存在，应用启动时调用一次"""
    client = get_client()
    bucket = settings.MINIO_BUCKET
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info(f"MinIO bucket '{bucket}' created")
    except S3Error as e:
        logger.warning(f"MinIO ensure_bucket skipped: {e}")
    except Exception as e:
        logger.warning(f"MinIO ensure_bucket skipped: {e}")


def upload_bytes(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """上传字节内容，返回 object_name"""
    client = get_client()
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def upload_file(object_name: str, local_path: str | Path, content_type: str = "application/octet-stream") -> str:
    """上传本地文件，返回 object_name"""
    client = get_client()
    client.fput_object(settings.MINIO_BUCKET, object_name, str(local_path), content_type=content_type)
    return object_name


def download_file(object_name: str, local_path: str | Path) -> None:
    """下载对象到本地路径"""
    client = get_client()
    client.fget_object(settings.MINIO_BUCKET, object_name, str(local_path))


def read_bytes(object_name: str) -> bytes:
    """读取对象内容为字节"""
    client = get_client()
    resp = client.get_object(settings.MINIO_BUCKET, object_name)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def presigned_url(object_name: str, expires_seconds: int = 3600 * 24) -> str:
    """生成预签名访问 URL（默认 24 小时有效）"""
    from datetime import timedelta

    client = get_client()
    return client.presigned_get_object(
        settings.MINIO_BUCKET,
        object_name,
        expires=timedelta(seconds=expires_seconds),
    )


def delete_file(object_name: str) -> None:
    client = get_client()
    client.remove_object(settings.MINIO_BUCKET, object_name)


def list_objects(prefix: str = "") -> list:
    """列出指定前缀下的所有对象"""
    client = get_client()
    return list(client.list_objects(settings.MINIO_BUCKET, prefix=prefix, recursive=True))
