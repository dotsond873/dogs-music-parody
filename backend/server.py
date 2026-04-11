from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query, Header
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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
from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Storage configuration
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "dancing-video-generator"
storage_key = None

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Storage functions
def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        logger.info("Storage initialized successfully")
        return storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        raise

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str) -> tuple:
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# Models
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

# Startup event
@app.on_event("startup")
async def startup():
    try:
        init_storage()
        logger.info("Application started, storage initialized")
    except Exception as e:
        logger.error(f"Startup failed: {e}")

# Routes
@api_router.get("/")
async def root():
    return {"message": "Dancing Dave's Swamp Donkeys and Spundunnits API"}

@api_router.post("/upload-media", response_model=MediaUpload)
async def upload_media(file: UploadFile = File(...), media_type: str = Query(...)):
    try:
        ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        file_id = str(uuid.uuid4())
        path = f"{APP_NAME}/uploads/{file_id}.{ext}"
        
        data = await file.read()
        result = put_object(path, data, file.content_type or "application/octet-stream")
        
        media_upload = MediaUpload(
            id=file_id,
            storage_path=result["path"],
            original_filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size=result["size"],
            media_type=media_type
        )
        
        doc = media_upload.model_dump()
        await db.media_uploads.insert_one(doc)
        
        return media_upload
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/files/{file_id}")
async def get_file(file_id: str):
    try:
        record = await db.media_uploads.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
        if not record:
            raise HTTPException(status_code=404, detail="File not found")
        
        data, content_type = get_object(record["storage_path"])
        return Response(content=data, media_type=record.get("content_type", content_type))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/youtube-audio", response_model=MediaUpload)
async def extract_youtube_audio(request: YouTubeAudioRequest):
    try:
        youtube_url = request.youtube_url
        file_id = str(uuid.uuid4())
        
        # Create temp directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            output_template = f"{temp_dir}/audio.%(ext)s"
            
            # yt-dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            
            # Download and extract audio
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                video_title = info.get('title', 'youtube_audio')
            
            # Find the downloaded audio file
            audio_path = f"{temp_dir}/audio.mp3"
            if not os.path.exists(audio_path):
                # Try to find any audio file in the directory
                files = os.listdir(temp_dir)
                for f in files:
                    if f.endswith('.mp3'):
                        audio_path = os.path.join(temp_dir, f)
                        break
            
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            # Upload to object storage
            storage_path = f"{APP_NAME}/uploads/{file_id}.mp3"
            result = put_object(storage_path, audio_data, "audio/mpeg")
            
            # Save to database
            media_upload = MediaUpload(
                id=file_id,
                storage_path=result["path"],
                original_filename=f"{video_title[:50]}.mp3",
                content_type="audio/mpeg",
                size=result["size"],
                media_type="audio"
            )
            
            doc = media_upload.model_dump()
            await db.media_uploads.insert_one(doc)
            
            logger.info(f"Successfully extracted audio from YouTube: {video_title}")
            return media_upload
            
    except Exception as e:
        logger.error(f"YouTube audio extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract audio from YouTube: {str(e)}")


def get_sora_duration(requested_duration: int) -> int:
    """Convert requested duration to valid Sora duration (4, 8, or 12)"""
    if requested_duration <= 4:
        return 4
    elif requested_duration <= 8:
        return 8
    else:
        return 12

def create_user_friendly_error(error_str: str) -> str:
    """Convert technical errors to user-friendly messages"""
    error_lower = error_str.lower()
    
    if "insufficient_balance" in error_lower or "insufficient balance" in error_lower:
        return "⚠️ Insufficient balance in Universal Key. Go to Profile → Universal Key → Add Balance to continue generating videos."
    
    if "budget_exceeded" in error_lower or "budget has been exceeded" in error_lower:
        return "⚠️ Budget limit reached! Add more balance to your Universal Key in Profile → Universal Key → Add Balance."
    
    if "400" in error_str and "bad request" in error_lower:
        return f"⚠️ API Error: {error_str}. This might be a balance issue - check your Universal Key balance."
    
    return error_str

async def update_video_status(video_id: str, status: str, **kwargs):
    """Update video generation status in database"""
    update_data = {"status": status, **kwargs}
    await db.video_generations.update_one(
        {"id": video_id},
        {"$set": update_data}
    )

async def generate_video_with_sora(prompt: str, duration: int, subject_media_ids: List[str]) -> bytes:
    """Generate video using Sora 2 with optional image input"""
    sora_duration = get_sora_duration(duration)
    
    # If subject images are provided, save the first one to a temp file
    temp_image_path = None
    if subject_media_ids and len(subject_media_ids) > 0:
        try:
            # Get the first uploaded image
            media_record = await db.media_uploads.find_one(
                {"id": subject_media_ids[0], "is_deleted": False}, 
                {"_id": 0}
            )
            if media_record and media_record.get("media_type") == "image":
                image_data, _ = get_object(media_record["storage_path"])
                
                # Save to temp file for the library
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                temp_file.write(image_data)
                temp_file.close()
                temp_image_path = temp_file.name
                
                logger.info(f"Using uploaded image as input: {media_record['original_filename']}")
        except Exception as e:
            logger.warning(f"Failed to load image for input: {e}")
    
    try:
        # Generate video using library (supports both text-to-video and image-to-video)
        video_gen = OpenAIVideoGeneration(api_key=os.environ['EMERGENT_LLM_KEY'])
        
        video_bytes = video_gen.text_to_video(
            prompt=prompt,
            model="sora-2",
            size="1280x720",
            duration=sora_duration,
            max_wait_time=900,
            image_path=temp_image_path,
            mime_type="image/jpeg"
        )
        
        return video_bytes
    finally:
        # Clean up temp file
        if temp_image_path and os.path.exists(temp_image_path):
            os.unlink(temp_image_path)

async def save_generated_video(video_id: str, video_bytes: bytes) -> str:
    """Save generated video to storage and return path"""
    video_path = f"{APP_NAME}/videos/{video_id}.mp4"
    result = put_object(video_path, video_bytes, "video/mp4")
    return result["path"]

async def combine_video_with_audio(video_bytes: bytes, audio_file_id: Optional[str]) -> bytes:
    """Combine generated video with user's audio using FFmpeg"""
    if not audio_file_id:
        return video_bytes
    
    try:
        # Get audio file from storage
        audio_record = await db.media_uploads.find_one({"id": audio_file_id, "is_deleted": False}, {"_id": 0})
        if not audio_record:
            logger.warning(f"Audio file {audio_file_id} not found, returning video without audio")
            return video_bytes
        
        audio_data, _ = get_object(audio_record["storage_path"])
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save video and audio to temp files
            video_path = f"{temp_dir}/video.mp4"
            audio_path = f"{temp_dir}/audio.mp3"
            output_path = f"{temp_dir}/output.mp4"
            
            with open(video_path, 'wb') as f:
                f.write(video_bytes)
            with open(audio_path, 'wb') as f:
                f.write(audio_data)
            
            # Use FFmpeg to combine video with audio
            import subprocess
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                '-y',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    return f.read()
            else:
                logger.error(f"FFmpeg failed: {result.stderr.decode()}")
                return video_bytes
                
    except Exception as e:
        logger.error(f"Failed to combine video with audio: {e}")
        return video_bytes

async def generate_video_background(video_id: str, prompt: str, duration: int, audio_file_id: Optional[str] = None, subject_media_ids: Optional[List[str]] = None):
    try:
        await update_video_status(video_id, "generating")
        
        video_bytes = await generate_video_with_sora(prompt, duration, subject_media_ids or [])
        
        if video_bytes:
            # Combine with user's audio if provided
            if audio_file_id:
                video_bytes = await combine_video_with_audio(video_bytes, audio_file_id)
            
            video_path = await save_generated_video(video_id, video_bytes)
            
            await update_video_status(
                video_id, 
                "completed",
                video_path=video_path,
                completed_at=datetime.now(timezone.utc).isoformat()
            )
            logger.info(f"Video {video_id} generated successfully")
        else:
            error_msg = "Video generation returned no data"
            await update_video_status(video_id, "failed", error_message=error_msg)
            logger.error(f"Video {video_id} failed: {error_msg}")
            
    except Exception as e:
        error_str = str(e)
        logger.error(f"Video generation failed for {video_id}: {error_str}")
        
        user_friendly_error = create_user_friendly_error(error_str)
        await update_video_status(video_id, "failed", error_message=user_friendly_error)

@api_router.post("/generate-video", response_model=VideoGeneration)
async def generate_video(request: GenerateVideoRequest):
    try:
        video_gen = VideoGeneration(
            subject_media_ids=request.subject_media_ids,
            audio_file_id=request.audio_file_id,
            prompt=request.prompt,
            duration=request.duration,
            status="pending"
        )
        
        doc = video_gen.model_dump()
        await db.video_generations.insert_one(doc)
        
        asyncio.create_task(generate_video_background(
            video_gen.id, 
            request.prompt, 
            request.duration,
            request.audio_file_id,
            request.subject_media_ids
        ))
        
        return video_gen
    except Exception as e:
        logger.error(f"Generate video request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/videos", response_model=List[VideoGeneration])
async def get_videos():
    videos = await db.video_generations.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return videos

@api_router.get("/videos/{video_id}", response_model=VideoGeneration)
async def get_video(video_id: str):
    video = await db.video_generations.find_one({"id": video_id}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@api_router.get("/video-file/{video_id}")
async def get_video_file(video_id: str):
    try:
        record = await db.video_generations.find_one({"id": video_id}, {"_id": 0})
        if not record or not record.get("video_path"):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        data, content_type = get_object(record["video_path"])
        return Response(content=data, media_type="video/mp4")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video file retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()