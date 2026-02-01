# Project Status Summary (Customer Visit System)

## Architecture & Services
- Monorepo layout: apps/api (FastAPI), apps/worker (Python), apps/web (React+TS), packages (shared), contracts, infra, docs, scripts.
- Worker-centric streaming/proxy architecture is implemented and documented.
  - Workers provide HTTP endpoints for camera control and MJPEG streaming.
  - API delegates camera start/stop/status/stream via camera proxy service and command system.
  - Worker registration, heartbeat, and command dispatch (ASSIGN/RELEASE/START/STOP) are in place.
  - Frontend consumes streams via API proxy; SSE/WebSocket used for status/monitoring.

## Staff Face Management (Enhanced)
- Multiple face images per staff with landmarks + embeddings.
- New StaffFaceImage table, migration 004_add_staff_face_images.
- FaceProcessingService handles face detection, landmarks, embeddings, MinIO storage.
- API endpoints: /staff/{id}/faces (GET/POST/DELETE), /staff/{id}/details, /staff/{id}/test-recognition, /faces/{image_id}/recalculate.
- Frontend components: StaffFaceGallery, FaceRecognitionTest, StaffDetailsModal; staff page updated.

## Reports & Dashboard Data
- Charts use real API data (no seed fallbacks). Dashboard and Reports pages fully implemented with API integrations.
- New /reports/demographics endpoint added; frontend API client added.

## Recent DevOps/CI Adjustments (2025-09-15)
- Web ESLint relaxed from error on warnings; added test overrides.
- Added ruff/black/isort config in pyproject.toml; fixed TOML parsing issue.
- Fixed API Dockerfile requirements path and web Dockerfile nginx user/group issue.

## Docs & Artifacts
- ARCHITECTURE_MIGRATION.md documents worker-centric migration.
- STAFF_FACE_MANAGEMENT_ENHANCEMENT.md documents staff face features.
- REPORT_PROGRESS.md confirms report/chart real-data integration complete.
- docs/openapi.json and postman_collection.json present.

## Known Focus/Blockers
- Background jobs (APScheduler), admin merge endpoints, audit logging, MinIO purge verification listed as remaining production blockers in QWEN.md context.
