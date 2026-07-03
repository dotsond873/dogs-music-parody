from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
logger = logging.getLogger(__name__)
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import requests
import asyncio
import yt_dlp
import tempfile
import subprocess
from io import BytesIO
from PIL import Image
import cloudinary
import cloudinary.uploader

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


APP_NAME = "dogs-music-parody"

app = FastAPI(title=APP_NAME)
api_router = APIRouter(prefix="/api")

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True
)

def put_object(path: str, data: bytes, content_type: str) -> dict:
    public_id = os.path.splitext(path)[0]

    result = cloudinary.uploader.upload(
        BytesIO(data),
        public_id=public_id,
        resource_type="auto",
        overwrite=True
    )

    return {"storage_path": result["secure_url"]}

def get_object(path: str) -> tuple:
    resp = requests.get(path, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get(
        "Content-Type",
        "application/octet-stream"
    )

# ─── Models ────────────────────────────────────────────────────────────

class MediaUpload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    storage_path: str
    original_filename: str
    content_type: str
    size: int
    media_type: str
    is_deleted: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class VideoGeneration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_media_ids: List[str]
    audio_file_id: Optional[str] = None
    prompt: str
    duration: int = 30
    status: str = "pending"
    video_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

class GenerateVideoRequest(BaseModel):
    subject_media_ids: List[str]
    audio_file_id: Optional[str] = None
    prompt: str
    duration: int = 30

class YouTubeAudioRequest(BaseModel):
    youtube_url: str

# ─── Image resize ──────────────────────────────────────────────────────

def resize_image_to_1280x720(image_bytes: bytes) -> bytes:
    """Resize any image to exactly 1280x720 (required by Sora 2)"""
    img = Image.open(BytesIO(image_bytes))
    img = img.convert("RGB")
    img = img.resize((1280, 720), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    logger.info(f"Resized image to 1280x720 ({len(buf.getvalue())} bytes)")
    return buf.getvalue()

# ─── Sora 2 video generation ──────────────────────────────────────────

def get_sora_duration(d: int) -> int:
    if d <= 4: return 4
    if d <= 8: return 8
    return 12

def friendly_error(e: str) -> str:
    el = e.lower()
    if "insufficient_balance" in el or "insufficient balance" in el:
        return "Insufficient balance. Go to Profile > Universal Key > Add Balance."
    if "budget_exceeded" in el or "budget has been exceeded" in el:
        return "Budget limit reached! Add more balance in Profile > Universal Key > Add Balance."
    if "inpaint image must match" in el:
        return "Image size mismatch (auto-resize should fix this). Try again."
    return e

async def update_video_status(vid: str, status: str, **kw):
    await db.video_generations.update_one({"id": vid}, {"$set": {"status": status, **kw}})

async def generate_video_with_sora(prompt: str, duration: int, subject_media_ids: List[str]) -> bytes:
    """Generate video using Sora 2 — resizes image to 1280x720 first"""
    sora_dur = get_sora_duration(duration)
    api_key = os.environ['EMERGENT_LLM_KEY']
    url = "https://integrations.emergentagent.com/llm/openai/v1/videos"

    form_data = {"model": "sora-2", "size": "1280x720", "seconds": str(sora_dur)}
    files = None
    has_image = False

    # Load + resize the first uploaded image
    if subject_media_ids:
        try:
            rec = await db.media_uploads.find_one({"id": subject_media_ids[0], "is_deleted": False}, {"_id": 0})
            if rec and rec.get("media_type") == "image":
                raw, _ = get_object(rec["storage_path"])
                resized = resize_image_to_1280x720(raw)
                files = {"input_reference": ("subject.jpg", resized, "image/jpeg")}
                has_image = True
                logger.info(f"Prepared resized image for Sora 2")
        except Exception as exc:
            logger.warning(f"Image prep failed, falling back to text-only: {exc}")

    # When using input_reference, prefix prompt to tell Sora to keep the subject
    if has_image:
        form_data["prompt"] = f"Animate the exact subject shown in the reference image. Keep their appearance, features, and body exactly as shown. {prompt}"
    else:
        form_data["prompt"] = prompt

    headers = {"Authorization": f"Bearer {api_key}"}

    # Initiate generation
    logger.info(f"Sending to Sora 2: prompt={prompt[:60]}... dur={sora_dur} image={'yes' if files else 'no'}")
    resp = requests.post(url, headers=headers, data=form_data, files=files, timeout=120)

    if resp.status_code != 200:
        logger.error(f"Sora 2 init failed [{resp.status_code}]: {resp.text}")
        resp.raise_for_status()

    video_id = resp.json().get("id")
    if not video_id:
        raise Exception(f"No video ID returned: {resp.text}")

    logger.info(f"Sora 2 job started: {video_id}")

    # Poll until done
    for elapsed in range(10, 910, 10):
        await asyncio.sleep(10)
        sr = requests.get(f"{url}/{video_id}", headers=headers, timeout=30)
        sr.raise_for_status()
        sd = sr.json()
        st = sd.get("status", "unknown")
        logger.info(f"  [{elapsed}s] status={st}")

        if st == "completed":
            dl = requests.get(f"{url}/{video_id}/content", headers=headers, timeout=120)
            dl.raise_for_status()
            logger.info(f"Downloaded video: {len(dl.content)} bytes")
            return dl.content
        if st == "failed":
            raise Exception(f"Sora 2 failed: {sd.get('error', sd)}")

    raise Exception("Sora 2 timed out after 15 minutes")

async def merge_audio(video_bytes: bytes, audio_file_id: Optional[str]) -> bytes:
    """Replace video audio with user's song using FFmpeg"""
    if not audio_file_id:
        return video_bytes
    try:
        rec = await db.media_uploads.find_one({"id": audio_file_id, "is_deleted": False}, {"_id": 0})
        if not rec:
            return video_bytes
        audio_data, _ = get_object(rec["storage_path"])
        with tempfile.TemporaryDirectory() as td:
            vp, ap, op = f"{td}/v.mp4", f"{td}/a.mp3", f"{td}/out.mp4"
            with open(vp, 'wb') as f: f.write(video_bytes)
            with open(ap, 'wb') as f: f.write(audio_data)
            r = subprocess.run([
                'ffmpeg', '-i', vp, '-i', ap,
                '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy', '-c:a', 'aac', '-shortest', '-y', op
            ], capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(op):
                with open(op, 'rb') as f:
                    logger.info("Audio merged successfully")
                    return f.read()
            logger.error(f"FFmpeg error: {r.stderr.decode()[:300]}")
    except Exception as exc:
        logger.error(f"Audio merge failed: {exc}")
    return video_bytes

async def generate_video_background(vid: str, prompt: str, duration: int, audio_file_id: Optional[str], subject_media_ids: Optional[List[str]]):
    try:
        await update_video_status(vid, "generating")
        vb = await generate_video_with_sora(prompt, duration, subject_media_ids or [])
        if not vb:
            await update_video_status(vid, "failed", error_message="Video generation returned no data")
            return
        if audio_file_id:
            vb = await merge_audio(vb, audio_file_id)
        path = f"{APP_NAME}/videos/{vid}.mp4"
        result = put_object(path, vb, "video/mp4")
        await update_video_status(vid, "completed", video_path=result["path"], completed_at=datetime.now(timezone.utc).isoformat())
        logger.info(f"Video {vid} completed!")
    except Exception as exc:
        logger.error(f"Video {vid} failed: {exc}")
        await update_video_status(vid, "failed", error_message=friendly_error(str(exc)))

# ─── Routes ────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    try:
        # Ensure ffmpeg is available
        import shutil
        if not shutil.which('ffmpeg'):
            subprocess.run(['apt-get', 'update', '-qq'], capture_output=True)
            subprocess.run(['apt-get', 'install', '-y', 'ffmpeg', '-qq'], capture_output=True)
            logger.info("FFmpeg installed")
        
        logger.info("App started, storage ready")
    except Exception as e:
        logger.error(f"Startup failed: {e}")

@api_router.get("/")
async def root():
    return {"message": "NAUGHTY DAWGZ - ANOTHER ODB PRODUCTION API"}

@api_router.get("/welcome-video")
async def get_welcome_video():
    """Get the welcome video for the landing page"""
    rec = await db.media_uploads.find_one({"media_type": "welcome_video", "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "No welcome video uploaded yet")
    
    data, _ = get_object(rec["storage_path"])
    content_length = len(data)
    
    async def video_stream():
        chunk_size = 1024 * 1024  # 1MB chunks
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
            await asyncio.sleep(0)  # Allow other tasks to run
    
    headers = {"Content-Length": str(content_length)}
    return StreamingResponse(video_stream(), media_type="video/mp4", headers=headers)

@api_router.post("/youtube-audio", response_model=MediaUpload)
async def extract_youtube_audio(request: YouTubeAudioRequest):
    fid = str(uuid.uuid4())

    with tempfile.TemporaryDirectory() as td:
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": f"{td}/audio.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }],
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request.youtube_url, download=True)
                title = info.get("title", "audio")
        except Exception as yt_err:
            raise HTTPException(500, f"YouTube extraction failed: {str(yt_err)[:200]}")

        ap = None
        for fn in os.listdir(td):
            if fn.endswith(".mp3"):
                ap = os.path.join(td, fn)
                break

        if not ap:
            raise HTTPException(500, "Could not extract audio from YouTube")

        with open(ap, "rb") as f:
            audio_data = f.read()

        result = put_object(
            f"{APP_NAME}/uploads/{fid}.mp3",
            audio_data,
            "audio/mpeg"
        )

        mu = MediaUpload(
            id=fid,
            
           storage_path=result.get("url"), original_filename=f"{title[:50]}.mp3",
            content_type="audio/mpeg",
            size=len(audio_data),
            media_type="audio"
        )

        await db.media_uploads.insert_one(mu.model_dump())
        logger.info(f"YouTube audio extracted: {title}")
        return mu

@api_router.post("/upload-media", response_model=MediaUpload)
async def upload_media(file: UploadFile = File(...), media_type: str = Query(...)):
    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    fid = str(uuid.uuid4())
    data = await file.read()
    result = put_object(f"{APP_NAME}/uploads/{fid}.{ext}", data, file.content_type or "application/octet-stream")
        mu = MediaUpload(
        id=fid,
        storage_path=result.get("url"),
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        size=len(data),
        media_type=media_type
    )
 await db.media_uploads.insert_one(mu.model_dump()) 
return mu
@api_router.get("/files/{file_id}")
async def get_file(file_id: str):
    rec = await db.media_uploads.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "File not found")
    
    data, ct = get_object(rec["storage_path"])
    content_length = len(data)
    
    async def file_stream():
        chunk_size = 1024 * 1024  # 1MB chunks
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
            await asyncio.sleep(0)  # Allow other tasks to run
    
    headers = {"Content-Length": str(content_length)}
    return StreamingResponse(file_stream(), media_type=rec.get("content_type", "application/octet-stream"), headers=headers)

@api_router.post("/youtube-audio", response_model=MediaUpload)
async def extract_youtube_audio(request: YouTubeAudioRequest):
    return await upload_media_from_url(request.youtube_url, "audio")


@api_router.post("/upload-media", response_model=MediaUpload)
async def upload_media(file: UploadFile = File(...), media_type: str = Query(...)):
    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    fid = str(uuid.uuid4())
    data = await file.read()
    result = put_object(
        f"{APP_NAME}/uploads/{fid}.{ext}",
        data,
        file.content_type or "application/octet-stream"
    )
   result = put_object(
    f"{APP_NAME}/uploads/{fid}.{ext}",
    data,
    file.content_type or "application/octet-stream"
)

mu = MediaUpload(
    id=fid,
    storage_path=result.get("url"),
    original_filename=file.filename,
    content_type=file.content_type or "application/octet-stream",
    size=len(data),
    media_type=media_type
)


)

await db.media_uploads.insert_one(mu.model_dump())
return mu
@api_router.get("/videos", response_model=List[VideoGeneration])
async def get_videos():
    return await db.video_generations.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.get("/videos/{video_id}", response_model=VideoGeneration)
async def get_video(video_id: str):
    v = await db.video_generations.find_one({"id": video_id}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Video not found")
    return v

@api_router.get("/video-file/{video_id}")
async def get_video_file(video_id: str):
    rec = await db.video_generations.find_one({"id": video_id}, {"_id": 0})
    if not rec or not rec.get("video_path"):
        raise HTTPException(404, "Video file not found")
    
    data, _ = get_object(rec["video_path"])
    content_length = len(data)
    
    async def video_stream():
        chunk_size = 1024 * 1024  # 1MB chunks
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
            await asyncio.sleep(0)  # Allow other tasks to run
    
    headers = {"Content-Length": str(content_length)}
    return StreamingResponse(video_stream(), media_type="video/mp4", headers=headers)

# ─── App config ────────────────────────────────────────────────────────

app.include_router(api_router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
app.add_middleware(CORSMiddleware, allow_credentials=True,
                   allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
