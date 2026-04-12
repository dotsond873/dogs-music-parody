# PRD — Dancing Dave's Swamp Donkeys & Spundunnits

## Problem Statement
User wants a reusable app to generate dancing videos of any subject (dogs, humans, aliens, washing machines) with custom music, clothing/accessories descriptions, and dance style/action descriptions.

## Architecture
- **Frontend**: React + Tailwind (Neo-Brutalist design)
- **Backend**: FastAPI + MongoDB + Object Storage
- **Video AI**: Sora 2 (OpenAI) via Emergent integrations API
- **Audio**: yt-dlp for YouTube extraction, FFmpeg for audio merge
- **Storage**: Emergent object storage for uploads & generated videos

## What's Implemented (April 2026)
- [x] Subject image upload with thumbnail previews
- [x] Auto-resize images to 1280x720 for Sora 2 compatibility
- [x] YouTube audio extraction (including explicit content)
- [x] Audio file upload
- [x] Three-field prompt builder (Subject, Clothing/Jewelry/Grills, Dance Style/Actions)
- [x] Sora 2 video generation with image-to-video mode
- [x] FFmpeg audio merge (replaces Sora audio with user's song)
- [x] Video preview with status tracking (pending, generating, completed, failed)
- [x] Previous generations history
- [x] Friendly error messages for balance/budget issues

## Prioritized Backlog
### P0 (Critical)
- All core features implemented

### P1 (Important)
- Video download button
- Multiple image support (combine subjects)
- Longer video durations (chain multiple Sora generations)

### P2 (Nice to Have)
- Social media sharing
- Video templates/presets
- User accounts and saved preferences
- Video resolution options
