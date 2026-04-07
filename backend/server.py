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
    return {"message": "Dancing Video Generator API"}

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

async def generate_video_background(video_id: str, prompt: str, duration: int):
    try:
        await db.video_generations.update_one(
            {"id": video_id},
            {"$set": {"status": "generating"}}
        )
        
        video_gen = OpenAIVideoGeneration(api_key=os.environ['EMERGENT_LLM_KEY'])
        
        sora_duration = 4
        if duration <= 4:
            sora_duration = 4
        elif duration <= 8:
            sora_duration = 8
        else:
            sora_duration = 12
        
        video_bytes = video_gen.text_to_video(
            prompt=prompt,
            model="sora-2",
            size="1280x720",
            duration=sora_duration,
            max_wait_time=900
        )
        
        if video_bytes:
            video_path = f"{APP_NAME}/videos/{video_id}.mp4"
            result = put_object(video_path, video_bytes, "video/mp4")
            
            await db.video_generations.update_one(
                {"id": video_id},
                {"$set": {
                    "status": "completed",
                    "video_path": result["path"],
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"Video {video_id} generated successfully")
        else:
            await db.video_generations.update_one(
                {"id": video_id},
                {"$set": {
                    "status": "failed",
                    "error_message": "Video generation returned no data"
                }}
            )
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        await db.video_generations.update_one(
            {"id": video_id},
            {"$set": {
                "status": "failed",
                "error_message": str(e)
            }}
        )

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
        
        asyncio.create_task(generate_video_background(video_gen.id, request.prompt, request.duration))
        
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