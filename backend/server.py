from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import cloudinary
import cloudinary.uploader
import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Configuration
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("dogs-music-parody")

APP_NAME = "dogs-music-parody"
ONE_MIN_BASE_URL = "https://api.1min.ai"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
}

ALLOWED_AUDIO_EXTENSIONS = {
    "mp3",
    "m4a",
    "wav",
    "aac",
    "ogg",
    "flac",
}

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4",
    "mov",
    "m4v",
    "webm",
}


def require_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


MONGO_URL = require_env("MONGO_URL")
DB_NAME = require_env("DB_NAME")
ONE_MIN_AI_API_KEY = require_env("ONE_MIN_AI_API_KEY")


cloudinary.config(
    cloud_name=require_env("CLOUDINARY_CLOUD_NAME"),
    api_key=require_env("CLOUDINARY_API_KEY"),
    api_secret=require_env("CLOUDINARY_API_SECRET"),
    secure=True,
)


mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]


app = FastAPI(
    title="Naughty Dawgz API",
    version="2.0.0",
)

api_router = APIRouter(prefix="/api")


# ============================================================
# Models
# ============================================================

class MediaUpload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )

    storage_path: str
    original_filename: str
    content_type: str
    size: int
    media_type: str
    is_deleted: bool = False

    created_at: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class GenerateVideoRequest(BaseModel):
    subject_media_ids: List[str]
    audio_file_id: Optional[str] = None
    prompt: str
    duration: int = 10
    aspect_ratio: str = "16:9"


class VideoGeneration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )

    subject_media_ids: List[str]
    audio_file_id: Optional[str] = None
    prompt: str
    duration: int = 10
    aspect_ratio: str = "16:9"

    status: str = "pending"
    provider_job_id: Optional[str] = None
    video_path: Optional[str] = None
    error_message: Optional[str] = None

    created_at: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    completed_at: Optional[str] = None


# ============================================================
# File helpers
# ============================================================

def file_extension(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ""

    return filename.rsplit(".", 1)[-1].lower().strip()


def validate_upload(
    filename: Optional[str],
    content_type: Optional[str],
    media_type: str,
    size: int,
) -> str:

    if size <= 0:
        raise HTTPException(
            status_code=400,
            detail="The selected file is empty.",
        )

    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File is larger than 50 MB.",
        )

    ext = file_extension(filename)
    normalized_type = media_type.strip().lower()

    if normalized_type in {"image", "subject"}:
        valid_content_type = (
            content_type is not None
            and content_type.startswith("image/")
        )

        if (
            ext not in ALLOWED_IMAGE_EXTENSIONS
            and not valid_content_type
        ):
            raise HTTPException(
                status_code=400,
                detail="Select a valid image file.",
            )

        return "image"

    if normalized_type in {"audio", "music"}:
        valid_content_type = (
            content_type is not None
            and content_type.startswith("audio/")
        )

        if (
            ext not in ALLOWED_AUDIO_EXTENSIONS
            and not valid_content_type
        ):
            raise HTTPException(
                status_code=400,
                detail="Select a valid audio file.",
            )

        return "audio"

    if normalized_type == "welcome_video":
        valid_content_type = (
            content_type is not None
            and content_type.startswith("video/")
        )

        if (
            ext not in ALLOWED_VIDEO_EXTENSIONS
            and not valid_content_type
        ):
            raise HTTPException(
                status_code=400,
                detail="Select a valid video file.",
            )

        return "welcome_video"

    raise HTTPException(
        status_code=400,
        detail="Invalid media type.",
    )


# ============================================================
# Cloudinary
# ============================================================

def upload_to_cloudinary(
    path: str,
    data: bytes,
    resource_type: str = "auto",
) -> str:

    public_id = str(Path(path).with_suffix(""))

    result = cloudinary.uploader.upload(
        BytesIO(data),
        public_id=public_id,
        resource_type=resource_type,
        overwrite=True,
    )

    secure_url = result.get("secure_url")

    if not secure_url:
        raise RuntimeError(
            "Cloudinary did not return a file URL."
        )

    return secure_url


async def download_bytes(
    url: str,
    timeout: float = 180.0,
) -> bytes:

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
    ) as client:

        response = await client.get(url)
        response.raise_for_status()

        return response.content


# ============================================================
# 1min.AI
# ============================================================

async def upload_image_to_1min(
    filename: str,
    content_type: str,
    image_data: bytes,
) -> str:

    headers = {
        "API-KEY": ONE_MIN_AI_API_KEY,
    }

    files = {
        "asset": (
            filename,
            image_data,
            content_type,
        )
    }

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:

        response = await client.post(
            f"{ONE_MIN_BASE_URL}/api/assets",
            headers=headers,
            files=files,
        )

    if response.status_code >= 400:
        raise RuntimeError(
            "1min.AI image upload failed "
            f"({response.status_code}): "
            f"{response.text[:500]}"
        )

    payload = response.json()

    asset_path = (
        payload.get("fileContent", {}).get("path")
        or payload.get("asset", {}).get("key")
    )

    if not asset_path:
        raise RuntimeError(
            "1min.AI did not return an asset path: "
            f"{payload}"
        )

    return asset_path


def normalize_duration(duration: int) -> str:
    if duration >= 10:
        return "10s"

    return "5s"


def normalize_aspect_ratio(value: str) -> str:
    allowed = {
        "1:1",
        "16:9",
        "9:16",
        "4:3",
        "3:4",
        "21:9",
        "9:21",
    }

    if value in allowed:
        return value

    return "16:9"


async def start_1min_video_job(
    image_path: str,
    prompt: str,
    duration: int,
    aspect_ratio: str,
) -> str:

    headers = {
        "API-KEY": ONE_MIN_AI_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "type": "IMAGE_TO_VIDEO",
        "model": "luma",
        "async": True,
        "promptObject": {
            "imageUrl": image_path,
            "prompt": prompt,
            "modelName": "ray-v2",
            "duration": normalize_duration(duration),
            "aspectRatio": normalize_aspect_ratio(
                aspect_ratio
            ),
            "resolution": "720p",
            "loop": False,
        },
    }

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:

        response = await client.post(
            f"{ONE_MIN_BASE_URL}/api/features",
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(
            "1min.AI generation request failed "
            f"({response.status_code}): "
            f"{response.text[:500]}"
        )

    result = response.json()
    record = result.get("aiRecord") or {}

    job_id = (
        record.get("uuid")
        or result.get("uuid")
    )

    if not job_id:
        raise RuntimeError(
            "1min.AI did not return a job ID: "
            f"{result}"
        )

    return job_id


async def wait_for_1min_video(
    job_id: str,
) -> str:

    headers = {
        "API-KEY": ONE_MIN_AI_API_KEY,
    }

    async with httpx.AsyncClient(
        timeout=60.0,
        follow_redirects=True,
    ) as client:

        for _ in range(90):

            response = await client.get(
                f"{ONE_MIN_BASE_URL}/api/results/{job_id}",
                headers=headers,
            )

            response.raise_for_status()

            payload = response.json()
            record = payload.get("aiRecord")

            if not record:
                raise RuntimeError(
                    "1min.AI returned an unknown job ID."
                )

            status = str(
                record.get("status", "")
            ).upper()

            if status == "SUCCESS":
                temporary_url = record.get(
                    "temporaryUrl"
                )

                if temporary_url:
                    return temporary_url

                result_object = (
                    record
                    .get("aiRecordDetail", {})
                    .get("resultObject")
                    or []
                )

                if (
                    isinstance(result_object, list)
                    and result_object
                ):
                    first_result = result_object[0]

                    if (
                        isinstance(first_result, str)
                        and first_result.startswith("http")
                    ):
                        return first_result

                raise RuntimeError(
                    "1min.AI completed but returned "
                    "no download URL."
                )

            if status in {
                "FAILURE",
                "FAILED",
                "ERROR",
            }:
                error_result = (
                    record
                    .get("aiRecordDetail", {})
                    .get("resultObject")
                )

                if isinstance(error_result, dict):
                    message = (
                        error_result.get("message")
                        or str(error_result)
                    )
                else:
                    message = str(
                        error_result
                        or "Unknown 1min.AI error"
                    )

                raise RuntimeError(message)

            await asyncio.sleep(10)

    raise RuntimeError(
        "1min.AI video generation timed out "
        "after 15 minutes."
    )


# ============================================================
# Audio merging
# ============================================================

async def merge_music(
    video_data: bytes,
    audio_data: bytes,
    audio_ext: str,
) -> bytes:

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg is not installed on the server."
        )

    with tempfile.TemporaryDirectory() as temp_dir:

        video_path = Path(temp_dir) / "video.mp4"
        audio_path = Path(
            temp_dir
        ) / f"music.{audio_ext or 'mp3'}"
        output_path = Path(temp_dir) / "finished.mp4"

        video_path.write_bytes(video_data)
        audio_path.write_bytes(audio_data)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if (
            process.returncode != 0
            or not output_path.exists()
        ):
            raise RuntimeError(
                "FFmpeg could not add the music: "
                + stderr.decode(
                    errors="ignore"
                )[-600:]
            )

        return output_path.read_bytes()


# ============================================================
# Database status helpers
# ============================================================

async def set_video_status(
    video_id: str,
    status: str,
    **fields: object,
) -> None:

    await db.video_generations.update_one(
        {"id": video_id},
        {
            "$set": {
                "status": status,
                **fields,
            }
        },
    )


# ============================================================
# Background video job
# ============================================================

async def generate_video_background(
    video_id: str,
) -> None:

    try:
        record = await db.video_generations.find_one(
            {"id": video_id},
            {"_id": 0},
        )

        if not record:
            return

        subject_ids = (
            record.get("subject_media_ids")
            or []
        )

        if not subject_ids:
            raise RuntimeError(
                "Upload at least one subject image."
            )

        subject = await db.media_uploads.find_one(
            {
                "id": subject_ids[0],
                "media_type": "image",
                "is_deleted": False,
            },
            {"_id": 0},
        )

        if not subject:
            raise RuntimeError(
                "The selected subject image "
                "was not found."
            )

        await set_video_status(
            video_id,
            "uploading_to_1min",
        )

        image_data = await download_bytes(
            subject["storage_path"]
        )

        image_path = await upload_image_to_1min(
            subject.get(
                "original_filename",
                "subject.jpg",
            ),
            subject.get(
                "content_type",
                "image/jpeg",
            ),
            image_data,
        )

        await set_video_status(
            video_id,
            "generating",
        )

        provider_job_id = await start_1min_video_job(
            image_path=image_path,
            prompt=record["prompt"],
            duration=record.get("duration", 10),
            aspect_ratio=record.get(
                "aspect_ratio",
                "16:9",
            ),
        )

        await set_video_status(
            video_id,
            "generating",
            provider_job_id=provider_job_id,
        )

        generated_url = await wait_for_1min_video(
            provider_job_id
        )

        video_data = await download_bytes(
            generated_url,
            timeout=300.0,
        )

        audio_file_id = record.get(
            "audio_file_id"
        )

        if audio_file_id:
            await set_video_status(
                video_id,
                "adding_music",
            )

            audio_record = (
                await db.media_uploads.find_one(
                    {
                        "id": audio_file_id,
                        "media_type": "audio",
                        "is_deleted": False,
                    },
                    {"_id": 0},
                )
            )

            if not audio_record:
                raise RuntimeError(
                    "The selected music file "
                    "was not found."
                )

            audio_data = await download_bytes(
                audio_record["storage_path"]
            )

            video_data = await merge_music(
                video_data,
                audio_data,
                file_extension(
                    audio_record.get(
                        "original_filename"
                    )
                ),
            )

        await set_video_status(
            video_id,
            "saving",
        )

        video_url = upload_to_cloudinary(
            f"{APP_NAME}/videos/{video_id}.mp4",
            video_data,
            resource_type="video",
        )

        await set_video_status(
            video_id,
            "completed",
            video_path=video_url,
            completed_at=datetime.now(
                timezone.utc
            ).isoformat(),
            error_message=None,
        )

    except Exception as exc:
        logger.exception(
            "Video generation failed for %s",
            video_id,
        )

        await set_video_status(
            video_id,
            "failed",
            error_message=str(exc)[:1000],
        )


# ============================================================
# API routes
# ============================================================

@api_router.get("/")
async def api_root() -> dict:
    return {
        "message": (
            "NAUGHTY DAWGZ - "
            "AN ODB PRODUCTION API"
        ),
        "version": "2.0.0",
        "video_provider": "1min.AI",
    }


@api_router.get("/health")
async def health() -> dict:

    try:
        await db.command("ping")
        database = "connected"

    except Exception:
        database = "unavailable"

    return {
        "status": (
            "ok"
            if database == "connected"
            else "degraded"
        ),
        "database": database,
        "ffmpeg": bool(shutil.which("ffmpeg")),
    }


@api_router.post(
    "/upload-media",
    response_model=MediaUpload,
)
async def upload_media(
    file: UploadFile = File(...),
    media_type: str = Query(...),
) -> MediaUpload:

    data = await file.read()

    normalized_type = validate_upload(
        file.filename,
        file.content_type,
        media_type,
        len(data),
    )

    media_id = str(uuid.uuid4())

    guessed_extension = mimetypes.guess_extension(
        file.content_type or ""
    )

    ext = (
        file_extension(file.filename)
        or (
            guessed_extension.lstrip(".")
            if guessed_extension
            else ""
        )
        or "bin"
    )

    if normalized_type == "image":
        resource_type = "image"

    elif normalized_type == "welcome_video":
        resource_type = "video"

    else:
        resource_type = "auto"

    storage_path = upload_to_cloudinary(
        (
            f"{APP_NAME}/uploads/"
            f"{media_id}.{ext}"
        ),
        data,
        resource_type=resource_type,
    )

    upload = MediaUpload(
        id=media_id,
        storage_path=storage_path,
        original_filename=(
            file.filename
            or f"upload.{ext}"
        ),
        content_type=(
            file.content_type
            or "application/octet-stream"
        ),
        size=len(data),
        media_type=normalized_type,
    )

    await db.media_uploads.insert_one(
        upload.model_dump()
    )

    return upload


@api_router.get("/files/{file_id}")
async def get_file(file_id: str):

    record = await db.media_uploads.find_one(
        {
            "id": file_id,
            "is_deleted": False,
        },
        {"_id": 0},
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return RedirectResponse(
        record["storage_path"]
    )


@api_router.post(
    "/welcome-video",
    response_model=MediaUpload,
)
async def upload_welcome_video(
    file: UploadFile = File(...),
) -> MediaUpload:

    data = await file.read()

    validate_upload(
        file.filename,
        file.content_type,
        "welcome_video",
        len(data),
    )

    await db.media_uploads.update_many(
        {
            "media_type": "welcome_video",
            "is_deleted": False,
        },
        {
            "$set": {
                "is_deleted": True,
            }
        },
    )

    media_id = str(uuid.uuid4())
    ext = file_extension(file.filename) or "mp4"

    storage_path = upload_to_cloudinary(
        (
            f"{APP_NAME}/welcome/"
            f"{media_id}.{ext}"
        ),
        data,
        resource_type="video",
    )

    upload = MediaUpload(
        id=media_id,
        storage_path=storage_path,
        original_filename=(
            file.filename
            or "welcome-video.mp4"
        ),
        content_type=(
            file.content_type
            or "video/mp4"
        ),
        size=len(data),
        media_type="welcome_video",
    )

    await db.media_uploads.insert_one(
        upload.model_dump()
    )

    return upload


@api_router.get("/welcome-video")
async def get_welcome_video():

    record = await db.media_uploads.find_one(
        {
            "media_type": "welcome_video",
            "is_deleted": False,
        },
        sort=[("created_at", -1)],
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="No welcome video uploaded.",
        )

    return RedirectResponse(
        record["storage_path"]
    )


@api_router.post(
    "/generate-video",
    response_model=VideoGeneration,
)
async def generate_video(
    request: GenerateVideoRequest,
) -> VideoGeneration:

    prompt = request.prompt.strip()

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="Enter a video prompt.",
        )

    if not request.subject_media_ids:
        raise HTTPException(
            status_code=400,
            detail="Upload a subject image first.",
        )

    generation = VideoGeneration(
        subject_media_ids=(
            request.subject_media_ids
        ),
        audio_file_id=request.audio_file_id,
        prompt=prompt,
        duration=request.duration,
        aspect_ratio=normalize_aspect_ratio(
            request.aspect_ratio
        ),
    )

    await db.video_generations.insert_one(
        generation.model_dump()
    )

    asyncio.create_task(
        generate_video_background(
            generation.id
        )
    )

    return generation


@api_router.get(
    "/videos/{video_id}",
    response_model=VideoGeneration,
)
async def get_video_status(
    video_id: str,
) -> VideoGeneration:

    record = await db.video_generations.find_one(
        {"id": video_id},
        {"_id": 0},
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Video generation not found.",
        )

    return VideoGeneration(**record)


@api_router.get(
    "/videos/{video_id}/content"
)
async def get_video_content(
    video_id: str,
):

    record = await db.video_generations.find_one(
        {"id": video_id},
        {"_id": 0},
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Video generation not found.",
        )

    if (
        record.get("status") != "completed"
        or not record.get("video_path")
    ):
        raise HTTPException(
            status_code=409,
            detail="Video is not ready yet.",
        )

    return RedirectResponse(
        record["video_path"]
    )


# ============================================================
# App setup
# ============================================================

app.include_router(api_router)


cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "*",
    ).split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=(
        cors_origins != ["*"]
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)


static_dir = ROOT_DIR / "static"
static_dir.mkdir(exist_ok=True)

app.mount(
    "/",
    StaticFiles(
        directory=static_dir,
        html=True,
    ),
    name="static",
)


@app.on_event("shutdown")
async def shutdown_database() -> None:
    mongo_client.close()