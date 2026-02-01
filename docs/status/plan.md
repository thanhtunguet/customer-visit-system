# Plan and Status

Plan for Claude Code: Analyze & Enhance Camera–Worker Delegation

# 🚨 IMPLEMENTATION STATUS UPDATE (2025-08-29)

## ✅ COMPLETED ITEMS

### 1. Deadlock Prevention & Backend Stability (CRITICAL - RESOLVED)
- ✅ **Fixed Backend Unresponsiveness**: Resolved async/sync database mixing causing deadlocks
- ✅ **Task Manager**: Implemented centralized task management with connection pool awareness
- ✅ **Background Task Management**: Fixed 11 locations of unhandled `asyncio.create_task()` calls
- ✅ **Database Connection Pool**: Added proper limits and timeouts (10+20 async, 5+10 sync connections)
- ✅ **Worker Monitor Service**: Fixed sync database usage in async contexts
- ✅ **API Server**: Now starts successfully and handles concurrent requests

### 2. Enhanced Worker Architecture (IMPLEMENTED)
- ✅ **HTTP Endpoints**: Workers now expose RESTful API for camera control
- ✅ **Camera Streaming Service**: Full OpenCV integration with device management
- ✅ **Multi-Camera Support**: Handle multiple streams with conflict resolution
- ✅ **API Delegation**: Backend proxies camera operations to workers via HTTP
- ✅ **Worker Registry**: Enhanced registration, heartbeat, and status tracking

### 3. Database & Models (PARTIALLY IMPLEMENTED)
- ✅ **Enhanced Tables**: staff_face_images with multiple faces per staff
- ✅ **RLS Implementation**: Tenant isolation with Row Level Security
- ✅ **Face Processing**: Detection, landmarks, embeddings, recognition testing
- ❌ **camera_sessions Table**: NOT YET IMPLEMENTED (lease-based assignment missing)
- ❌ **Worker Capacity Fields**: Basic status tracking exists but not full capacity model

## 🔄 CHANGED FROM ORIGINAL PLAN

### Architecture Changes:
1. **Proxy Pattern**: Instead of direct WebSocket, API delegates to worker HTTP endpoints
2. **Task Manager**: Added centralized async task management (not in original plan)
3. **Multi-Face Staff**: Enhanced staff management beyond original scope
4. **Real-time Communication**: SSE + WebSocket instead of pure WebSocket protocol

### Technology Choices:
1. **OpenCV Streaming**: Direct camera access vs RTSP-only approach
2. **HTTP + REST**: Worker endpoints vs pure WebSocket communication
3. **SQLAlchemy Async**: Mixed async/sync pattern vs pure async

## ⚠️ REMAINING SYNC ISSUES & TECHNICAL DEBT

### Critical Remaining Issues:
1. **workers.py Router**: Still has sync database calls in async endpoints
   - `register_worker()` uses `db: Session = Depends(get_db)` with `db.commit()`
   - Multiple other endpoints mixing sync/async patterns
   - **Impact**: Potential deadlocks under heavy worker registration load

2. **Assignment Algorithm**: Using basic camera assignment vs lease-based system
   - No `camera_sessions` table implemented
   - No optimistic concurrency control
   - No soft/hard reclaim logic
   - **Impact**: Race conditions in multi-worker scenarios

3. **Worker FSM**: Basic state tracking vs formal finite state machine
   - States exist but no proper FSM implementation
   - No graceful state transitions
   - **Impact**: Unpredictable behavior during failures

## 📋 IMMEDIATE PRIORITY FIXES NEEDED

### High Priority (Stability):
1. **Fix workers.py sync database calls** - Convert to async to prevent deadlocks
2. **Implement camera_sessions table** - Enable proper lease-based assignment
3. **Add worker FSM** - Proper state machine for reliability

### Medium Priority (Features):
1. **Structured logging** - Add correlation IDs and debug instrumentation
2. **Observability** - OTLP metrics and tracing
3. **Security hardening** - mTLS, encrypted RTSP credentials

### Low Priority (Optimization):
1. **Capacity-aware assignment** - Worker slot management
2. **Ring buffer** - Edge storage for replay
3. **Model hot-swap** - Dynamic model updates

---


---

Work Breakdown Structure (WBS)

Scope note: Single engineer + 4 AI coding agents. Stack: FastAPI + Postgres + Milvus + MinIO; React+TS+Vite+AntD+Tailwind; Workers on Mac Mini; Docker/Compose (local), Kubernetes (prod). Multi-tenant, on-prem, raw images retention 30 days, embeddings long-term.

⸻

0. Project Setup

0.1 Repo bootstrap
	•	Deliverable: Monorepo with apps/ (api, worker, web), infra/ (compose, k8s), packages/ (shared libs), docs/, scripts/.
	•	DoD (Definition of Done): make dev-up starts minimal hello-world API/Web; CI runs lint+tests; pre-commit hooks active.

0.2 Coding standards & automation
	•	Deliverable: Black/ruff/mypy for Python; ESLint/Prettier/TSConfig for web; Conventional Commits; PR template.
	•	DoD: CI fails on style/type errors; sample PR shows checks.

⸻

1. Architecture & ADRs

1.1 ADRs (Architecture Decision Records)
	•	Deliverable: ADRs for multi-tenant model (shared-schema+RLS), Milvus partitioning per tenant, retention strategy, auth/JWT, worker-to-API contract.
	•	DoD: docs/adr/*.md approved; links from README.

1.2 System diagrams (ASCII)
	•	Deliverable: Context + container + data-flow diagrams in docs/.
	•	DoD: Diagrams reflect repo components & interfaces below.

⸻

2. Architecture Migration & Enhancements

2.1 Camera Processing Migration (API → Worker)
	•	**✅ COMPLETE**: Migrated camera streaming and face recognition from API to Workers
	•	**New Architecture**: Frontend → API (proxy) → Worker → Camera Streaming
	•	**New Components**: 
		- Enhanced Worker with HTTP endpoints (apps/worker/app/enhanced_worker_with_streaming.py)
		- Camera Streaming Service (apps/worker/app/camera_streaming_service.py)
		- Camera Proxy Service (apps/api/app/services/camera_proxy_service.py)
		- Worker Registry and Command Services for delegation
	•	**Worker Communication**: 
		- Command System: ASSIGN_CAMERA, RELEASE_CAMERA, START_PROCESSING, STOP_PROCESSING
		- Registration & Heartbeat: 30s cycle with status/capability reporting
		- Persistent Worker IDs with tenant/site context
		- HTTP + WebSocket bidirectional communication
	•	**Multi-Camera Support**: Workers can handle multiple cameras simultaneously
	•	**Benefits**: Scalability, reliability, performance, distributed processing
	•	**Config**: USE_ENHANCED_WORKER=true enables new architecture
	•	DoD: Proxy streaming works; worker delegation functional; face events flow correctly.

2.2 Staff Face Management Enhancement  
	•	**✅ COMPLETE**: Multiple face images per staff member with landmarks and embeddings
	•	**New Database**: staff_face_images table with face processing pipeline
	•	**New Services**: FaceProcessingService for detection, landmarks, embeddings
	•	**New APIs**: Staff face CRUD, recognition testing, recalculation endpoints
	•	**New UI**: StaffFaceGallery, FaceRecognitionTest, StaffDetailsModal components
	•	**Features**: Drag-drop upload, similarity testing, primary image designation
	•	DoD: Multiple faces per staff; recognition testing works; UI integrated.

⸻

3. Service Communication & Protocols

3.1 Worker-API Communication
	•	**✅ COMPLETE**: Multi-channel communication system implemented
	•	**Registration Protocol**: POST /v1/registry/workers/register with persistent IDs
	•	**Heartbeat System**: 30-second cycle with status, capabilities, and streaming info
	•	**Command System**: Asynchronous command queue with acknowledgment/completion
	•	**Commands Available**: ASSIGN_CAMERA, RELEASE_CAMERA, START_PROCESSING, STOP_PROCESSING
	•	**Status Types**: IDLE, PROCESSING, ONLINE, OFFLINE, ERROR, MAINTENANCE
	•	**Capabilities Reporting**: Active streams, device status, processing stats
	•	DoD: Workers register, maintain heartbeat, execute commands reliably.

3.2 Frontend-API Communication
	•	**✅ COMPLETE**: Multiple communication channels for real-time updates
	•	**REST APIs**: Standard CRUD operations with JWT authentication
	•	**Server-Sent Events**: Real-time camera status updates via /status-stream
	•	**WebSocket**: Worker monitoring and live status updates
	•	**Authenticated Media**: Blob URL creation for protected image resources
	•	**Multi-tenant Context**: Tenant switching and context management
	•	DoD: Real-time updates work; authentication secure; tenant isolation maintained.

3.3 API-Worker HTTP Proxy
	•	**✅ COMPLETE**: Direct HTTP communication for camera control
	•	**Worker Endpoints**: Camera streaming control on port 8090
	•	**Stream Proxying**: MJPEG stream relay from worker to frontend
	•	**Command Delegation**: HTTP calls for immediate camera operations
	•	**Fallback Logic**: Command system backup when HTTP calls fail
	•	DoD: Camera streams proxy correctly; control commands work; fallback reliable.

⸻

4. Data & Schemas

4.1 PostgreSQL schema & RLS
	•	Deliverable: SQL migrations for tenants, sites, cameras, staff, customers, visits, api_keys. RLS on tenant-scoped tables.
	•	**✅ ENHANCED**: Added staff_face_images table for multiple face images per staff
	•	**New**: StaffFaceImage model with face_landmarks, face_embedding, is_primary fields
	•	**New**: Foreign key constraints with cascade deletion for data integrity
	•	DoD: make migrate applies; RLS test proves cross-tenant leak impossible.

4.2 Milvus collection & indexes
	•	Deliverable: face_embeddings (dim=512, metric=cosine), partitions per tenant_id; IVF index config (nlist/nprobe).
	•	DoD: Insert/search e2e test <100ms p95 on sample data (≥100k vectors).

4.3 MinIO buckets & lifecycle
	•	Deliverable: Buckets faces-raw, faces-derived; 30-day lifecycle on raw; presigned URL helper.
	•	DoD: Object older than 30 days is auto-deleted in sandbox; presigned URL works.

4.4 JSON contracts
	•	Deliverable: Versioned JSON Schemas in contracts/:
	•	Event.FaceDetected.v1
	•	VisitRecord.v1
	•	CustomerProfile.v1
	•	DoD: Schemas validated at runtime with Pydantic/ajv; contract tests pass.

⸻

4. API Backend (FastAPI)

4.1 AuthN/Z & multi-tenant guard
	•	Deliverable: JWT (HS/RS), roles: system_admin / tenant_admin / site_manager / worker; dependency injects tenant_ctx.
	•	DoD: Protected endpoints return 401/403 as expected; RLS enforced.

4.2 Core endpoints (v1)
	•	Deliverable:
	•	Tenants/Sites/Cameras CRUD
	•	Staff CRUD (enrollment stores embeddings tagged is_staff)
	•	**✅ ENHANCED**: Staff Face Management - Multiple face images per staff member
	•	**New**: GET /v1/staff/{staff_id}/faces - List all face images for staff
	•	**New**: POST /v1/staff/{staff_id}/faces - Upload face images with landmarks & embeddings
	•	**New**: DELETE /v1/staff/{staff_id}/faces/{image_id} - Delete face images
	•	**New**: POST /v1/staff/{staff_id}/test-recognition - Test recognition accuracy
	•	Events intake: POST /v1/events/face (embedding+meta)
	•	Matching: server queries Milvus, returns person_id|new
	•	Visits query: paginated, filter by time/site
	•	Reports: visitor counts (hour/day/week/month), new vs repeat, gender, DOW
	•	DoD: OpenAPI docs; Postman collection; integration tests green.

4.3 Background jobs
	•	Deliverable: Scheduler (APScheduler/Celery) for: raw image purge verify, report materialization, staff cache refresh.
	•	DoD: Jobs visible in logs; idempotent; unit tests.

4.4 Performance controls
	•	Deliverable: Batch insert, DB indexes, Milvus search params (nprobe) via env.
	•	DoD: Load test: sustain ≥50 events/s aggregate with p95 API <300ms on dev hardware.

⸻

5. Edge Worker (Mac Mini) - **UPDATED: Now Enhanced Worker with HTTP Endpoints**

5.1 Capture & decode
	•	Deliverable: RTSP/USB capture via OpenCV/FFmpeg, frame throttling (e.g., 5 FPS), motion gate (optional).
	•	**✅ COMPLETE**: Enhanced Worker with full camera streaming service and device management
	•	**New**: HTTP endpoints for camera control and streaming proxy support
	•	DoD: Works with RTSP test source; configurable fps/skip.

5.2 Detection & alignment
	•	Deliverable: YuNet (fast) and RetinaFace (accurate) selectable; 5-point alignment.
	•	**✅ COMPLETE**: Enhanced detector pipeline with multiple face processing models
	•	DoD: Detector unit test on sample images: ≥95% recall on provided set.

5.3 Embeddings
	•	Deliverable: InsightFace ArcFace (512-D) via ONNX/PyTorch (M-series friendly); L2-norm; cosine similarity.
	•	**✅ COMPLETE**: Production-ready embedding generation with graceful fallbacks
	•	DoD: Embedding consistency test (same face >0.6 cosine; different <0.4 on sample set).

5.4 Staff pre-filter
	•	Deliverable: In-memory staff gallery per site; local match before upload.
	•	**✅ COMPLETE**: Enhanced staff pre-filtering with multiple face images per staff
	•	DoD: Staff not sent as customer events; unit tests.

5.5 Event upload & resilience
	•	Deliverable: Signed requests to API with backoff; local disk queue for outages; snapshot JPEG optional.
	•	**✅ COMPLETE**: Full resilience with enhanced worker HTTP server
	•	DoD: Network cut test: events buffered and replayed; no loss.

5.6 Packaging & ops
	•	Deliverable: Docker (arm64) & native runner; scripts/mac/setup.zsh; env-based config.
	•	**✅ COMPLETE**: Enhanced worker with HTTP server option (USE_ENHANCED_WORKER=true)
	•	**New**: Worker HTTP endpoints for camera streaming and status monitoring
	•	DoD: ./run-worker.sh starts service on Mac; logs to file/syslog.

⸻

6. Matching & Identity

6.1 Server-side search & thresholding
	•	Deliverable: Top-K (k=5) search, calibrated threshold; create-or-link customer; multi-embedding per person; optional centroid.
	•	DoD: Confusion matrix on validation set; target FAR <1% @ TAR ≥95% (sample data).

6.2 Cross-tenant policy
	•	Deliverable: Default: search within tenant partition; config flag for global search (admin only).
	•	DoD: Unit tests assert partition scoping.

6.3 Merge & dedupe tools
	•	Deliverable: Admin endpoint to merge person_ids; cascades visits; removes old vectors.
	•	DoD: Post-merge integrity tests pass.

⸻

7. Analytics & Reporting

7.1 Materialized views
	•	Deliverable: Daily/hourly aggregates per (tenant, site), repeat vs new, gender, DOW.
	•	DoD: Query time <200ms for 1y window on sample volume.

7.2 Export
	•	Deliverable: CSV export endpoints; time/site filters.
	•	DoD: Downloaded CSV matches API totals.

⸻

8. Security & Privacy

8.1 Retention enforcement
	•	Deliverable: S3 lifecycle + audit job verifying deletions; nullify image_path after purge.
	•	DoD: After 30d in test clock, images gone, DB pointers cleaned.

8.2 Secrets & policies
	•	Deliverable: K8s Secrets; NetworkPolicies; least-privilege DB roles; API rate limiting.
	•	DoD: Pod-to-DB restricted; load test shows 429 when exceeding limits.

8.3 Audit logs
	•	Deliverable: Admin actions & data exports logged with tenant/user context.
	•	DoD: Logs searchable; tamper-evident (append-only index).

⸻

9. Frontend (React + Vite + AntD + Tailwind)

9.1 Shell & auth
	•	Deliverable: Login, role-aware routing, layout (sidebar/topbar).
	•	DoD: Unauthorized paths redirect; token refresh works.

9.2 Entity management
	•	Deliverable: CRUD pages: sites, cameras, staff, customers; table filters/sort; forms with validation.
	•	**✅ ENHANCED**: Staff Face Management UI with multiple face images
	•	**New**: StaffFaceGallery component - Upload, view, delete face images
	•	**New**: FaceRecognitionTest component - Test recognition accuracy  
	•	**New**: StaffDetailsModal - Tabbed interface for staff details, faces, testing
	•	DoD: E2E tests (Playwright) cover create/edit/delete happy paths.

9.3 Live monitor
	•	Deliverable: Recent events list via WebSocket/SSE; snapshot refresh; status badges.
	•	**✅ ENHANCED**: Server-Sent Events for real-time camera status updates
	•	**New**: WebSocket connections for worker monitoring and status
	•	**New**: Real-time streaming status broadcasts across services
	•	DoD: New visit appears in UI <2s from API event (dev env).

9.4 Reports
	•	Deliverable: Charts (Recharts): time series, DOW heatmap, new vs repeat, gender; export CSV.
	•	DoD: Visuals match API data; download correct.

⸻

10. DevOps

10.1 Docker & Compose
	•	Deliverable: Multi-arch Dockerfiles; docker-compose.dev.yml (api, web, worker-sim, postgres, milvus, minio).
	•	DoD: make dev-up runs full stack; sample flow works.

10.2 Kubernetes (prod-like)
	•	Deliverable: Manifests: Deployment/Service/Ingress/HPA/PVC for api, web, postgres, milvus, minio; NetworkPolicies; PodSecurity.
	•	DoD: kustomize build valid; kubectl apply boots cluster locally (kind/microk8s) with health checks.

10.3 CI/CD
	•	Deliverable: GitHub Actions: build/test; buildx multi-arch images; push to registry; deploy job (manual gate).
	•	DoD: Badge green; tagged release produces images & manifests.

10.4 Observability
	•	Deliverable: Prometheus metrics (api/worker), Grafana dashboards; request/latency panels; alerting rules.
	•	DoD: Dashboards render; test alert fires on synthetic SLO breach.

⸻

11. Testing & QA

11.1 Unit tests
	•	Deliverable: ≥80% coverage on api core & worker core.
	•	DoD: Coverage gate enforced in CI.

11.2 Contract tests
	•	Deliverable: Schemas validated both sides; Pact (or JSONSchema) tests.
	•	DoD: Breaking changes caught in CI.

11.3 E2E scenario
	•	Deliverable: Synthetic RTSP stream → worker → api → milvus → reports → UI.
	•	DoD: Single script scripts/e2e_demo.sh proves flow; artifacts stored.

⸻

12. Rollout & Ops

12.1 Mac Mini provisioning
	•	Deliverable: scripts/mac/setup.zsh (install Docker, pull image, launch agent, logrotate).
	•	DoD: Fresh Mac runs worker in <10 min.

12.2 Runbooks & SRE docs
	•	Deliverable: Oncall cheatsheet: restart, scale, diagnose, rotate keys.
	•	DoD: Peer dry-run passes.

⸻

13. Optional backlog (post-MVP)
	•	Age/gender classifier; loyalty scoring; POS/CRM webhooks; WebRTC live stream; watchlist alerts.

⸻

Minimal APIs & Contracts (for reference)

Worker → API: POST /v1/events/face

{
  "tenant_id": "t_123",
  "site_id": "s_456",
  "camera_id": "c_789",
  "ts": "2025-08-19T05:00:00Z",
  "embedding": [0.001, ...], 
  "det_bbox": [x, y, w, h],
  "is_staff_local": false,
  "snapshot_presigned_url": "s3://... or https://..."
}

API Response

{
  "match": "known|new",
  "person_id": "p_abc123",
  "similarity": 0.73,
  "visit_id": "v_xyz789"
}


⸻

System Prompt for Claude Code (Token-Efficient, Unambiguous)

ROLE: Senior Platform Engineer & Codegen.
GOAL: Generate a production-ready MVP implementing the WBS above with minimal tokens, maximizing reuse and tests.
CONSTRAINTS: On-prem; Python 3.11; FastAPI; PostgreSQL; Milvus; MinIO; React+TS+Vite+AntD+Tailwind; Docker/Compose; K8s manifests; arm64-compatible worker. Multi-tenant (shared schema + RLS). Retain raw images 30 days; embeddings long-term.

1) Repository Layout

Create a monorepo:

/apps/api
/apps/worker
/apps/web
/packages/python/common   # shared pydantic models, utils
/packages/ts/common       # shared types
/contracts                # JSON Schemas
/infra/compose
/infra/k8s/base|overlays
/scripts
/docs

2) Implement APIs & Models
	•	Contracts: Add JSON Schemas for Event.FaceDetected.v1, VisitRecord.v1, CustomerProfile.v1. Generate Pydantic/TS types from schemas.
	•	DB: Alembic migrations for tables: tenants, sites, cameras, staff, customers, visits, api_keys. Add RLS: every SELECT/UPDATE/DELETE on tenant-scoped tables requires current_setting('app.tenant_id'). Set in middleware per request.
	•	Milvus: One collection face_embeddings (dim=512, metric=IP/cosine), partitions per tenant_id; create IVF index; config via env.
	•	MinIO: Buckets faces-raw, faces-derived; lifecycle rule 30 days on faces-raw.
	•	Auth: JWT (RS256). Roles: system_admin, tenant_admin, site_manager, worker. Worker uses API key → JWT minting endpoint.
	•	Endpoints (FastAPI /v1):
	•	POST /auth/token (password or API key for worker)
	•	CRUD: /tenants, /sites, /cameras, /staff, /customers
	•	POST /events/face (ingest): validate schema, staff filter, Milvus search (topK=5), threshold, create customer if new, insert visit, return match.
	•	GET /visits (filters: tenant/site/time/person)
	•	GET /reports/visitors (granularity=hour|day|week|month, site filter)
	•	GET /reports/distribution (new_vs_repeat, gender, dow)
	•	Background jobs: APScheduler: verify MinIO purge (nullify image_path), refresh staff cache, precompute aggregates into materialized views.

3) Worker (Mac Mini)
	•	Capture: OpenCV capture from RTSP/USB; config via env; frame-skip (WORKER_FPS=5).
	•	Detect: YuNet default; RetinaFace optional. 5-point alignment.
	•	Embed: InsightFace ArcFace 512-D; L2-norm; cosine sim. Use ONNXRuntime (arm64) or PyTorch+MPS when available.
	•	Staff pre-match: Load staff embeddings for site at startup; mark is_staff_local=true to skip customer flow.
	•	Upload: POST to /v1/events/face; include presigned snapshot URL or upload snapshot via MinIO client first; exponential backoff; local disk queue on failure.

4) Web (React+TS+Vite+AntD+Tailwind)
	•	Auth & Layout: Login; role-aware routes; sidebar nav.
	•	Pages: Sites, Cameras, Staff, Customers (CRUD); Live Monitor (SSE/WebSocket events list + refreshing snapshot); Reports (Recharts).
	•	UX: Filters by date/site; CSV export. Use shared TS types from /packages/ts/common.

5) DevOps
	•	Docker: Multi-stage Dockerfiles; multi-arch buildx targets (amd64, arm64). Healthchecks.
	•	Compose: infra/compose/docker-compose.dev.yml wiring api, worker-sim, postgres, milvus, minio, web.
	•	K8s: Manifests for api, web, postgres (StatefulSet), milvus, minio; Ingress; HPA; PVCs; NetworkPolicies; Secrets.
	•	CI/CD: GitHub Actions: lint, type-check, tests, buildx images, push to registry; render kustomize manifest artifact.

6) Security & Privacy
	•	Enforce RLS; tenant context set from JWT.
	•	MinIO lifecycle 30 days; purge audit job verifies deletion.
	•	API rate-limit middleware.
	•	Audit log: admin exports & merges.

7) Tests (must generate and make them pass)
	•	Unit: api services, RLS guard, Milvus client wrapper, worker detector/embedding (mocked).
	•	Contract: JSONSchema validation on both sides.
	•	E2E (compose): synthetic RTSP (FFmpeg testsrc + overlaid face images), worker → api → milvus → visit + report; Playwright checks UI shows new visit.
	•	Performance: Simple locust script hitting /events/face at 50 rps; assert p95 <300ms with mocked Milvus.

8) Non-functional
	•	Config via env with sane defaults; 12-factor.
	•	Structured logs (JSON) in api/worker; Prometheus metrics (req/sec, p95).
	•	Makefile targets: dev-up, dev-down, fmt, lint, test, e2e, buildx.

9) Acceptance Criteria (automate)
	•	make e2e runs full flow and exits 0.
	•	Coverage ≥80% for api & worker core.
	•	RLS test proves cross-tenant access blocked.
	•	MinIO purge test passes with simulated 31-day clock.
	•	Reports return correct aggregates on seeded data.

10) Deliverables to produce
	•	Code in repo structure above.
	•	OpenAPI JSON; Postman collection.
	•	docs/ with quickstart, ADRs, runbooks.
	•	K8s manifests under infra/k8s/overlays/prod.
	•	Scripts: scripts/mac/setup.zsh, scripts/e2e_demo.sh.

Style: Keep code and prompts concise; prefer small, composable modules; rigorous typing; short, descriptive commit messages (Conventional Commits).
Assume: No internet access at runtime; provide mock data and test assets.

Now generate:
	1.	All scaffolding and configs.
	2.	Core API, worker, and web MVP with tests.
	3.	Compose & K8s infra.
	4.	E2E demo pipeline and docs.