"""
Storage file serving endpoints.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import os

router = APIRouter()


@router.get("/{storage_key:path}")
async def get_file(storage_key: str):
    """
    Serve a file from storage by its storage key.

    Args:
        storage_key: The storage path (e.g., "datasets/uuid/image.jpg")

    Returns:
        The file as a response
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Requesting file with storage_key: {storage_key}")

    # 보안: storage_key가 상위 디렉토리 접근을 시도하는지 확인
    if ".." in storage_key or storage_key.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid storage key")

    # 파일 경로 구성 (절대 경로)
    file_path = Path(os.getcwd()) / "storage" / storage_key
    logger.info(f"Resolved file path: {file_path}")
    logger.info(f"File exists: {file_path.exists()}")

    # Fallback: 파일이 없고 storage_key에 "datasets/"가 없으면 추가해보기
    if not file_path.exists() and not storage_key.startswith("datasets/"):
        fallback_path = Path(os.getcwd()) / "storage" / "datasets" / storage_key
        logger.info(f"Trying fallback path: {fallback_path}")
        if fallback_path.exists():
            file_path = fallback_path

    # 파일 존재 여부 확인
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {storage_key}")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # MIME 타입 추정
    mime_type = None
    ext = file_path.suffix.lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.json': 'application/json',
    }
    mime_type = mime_types.get(ext, 'application/octet-stream')

    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=file_path.name
    )
