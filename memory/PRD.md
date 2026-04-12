# PRD — NAUGHTY DAWGZ: ANOTHER ODB PRODUCTION

## Problem Statement
Reusable AI video generator app. Make anything dance — dogs, humans, aliens, washing machines. Custom music from YouTube (including explicit songs), custom clothing/jewelry/grills descriptions, custom dance style/actions. Welcome page with Rocco the French Bulldog video.

## Architecture
- Frontend: React + Tailwind (dark theme, gold accents, iced-out aesthetic)
- Backend: FastAPI + MongoDB + Emergent Object Storage
- Video AI: Sora 2 via Emergent integrations API (with image resize to 1280x720)
- Audio: yt-dlp for YouTube, FFmpeg for audio merge
- Storage: Emergent object storage

## What's Implemented (April 2026)
- [x] Welcome page with iced-out NAUGHTY DAWGZ logo
- [x] Rocco welcome video upload
- [x] Subject image upload with previews
- [x] Auto-resize images to 1280x720 for Sora 2
- [x] YouTube audio extraction (explicit content enabled)
- [x] Audio file upload
- [x] Three-field prompt builder (Subject, Clothing/Grills, Dance/Actions)
- [x] Enhanced prompt prefix for better subject resemblance
- [x] Sora 2 image-to-video generation
- [x] FFmpeg audio merge
- [x] Video preview with status tracking
- [x] Previous generations history
- [x] FFmpeg auto-install on startup

## Fixes Applied
- Image resize to 1280x720 (was causing 400 errors)
- FFmpeg auto-install (was lost on container restart)
- Prompt prefix to preserve subject appearance
- YouTube age_limit=None for explicit content
- Timeout increased to 120s for uploads

## Backlog
- P1: Video download button
- P1: Multiple subject image compositing
- P2: Social media sharing
- P2: Video templates/presets
