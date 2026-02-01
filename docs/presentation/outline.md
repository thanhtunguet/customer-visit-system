# Face Recognition Platform — Executive Presentation Outline

## 1) Executive Summary
- Goal: On‑prem, multi‑tenant visitor analytics via face recognition
- Status: Core APIs, worker pipeline, web UI, infra, and tests present
- Differentiators: Strict tenant isolation (RLS), offline‑friendly mocks, enhanced worker HTTP proxy architecture

## 2) Problem & Outcomes
- Reduce manual logging; improve safety and insights
- Outcomes: Real‑time identification, visit history, actionable traffic analytics

## 3) Architecture Overview
- Services: FastAPI API (`apps/api`), Worker (OpenCV + embeddings, `apps/worker`), React+TS Web (`apps/web`)
- Data: PostgreSQL (RLS), Milvus (512‑D cosine, IVF), MinIO (raw/derived images)
- Communication: API↔Worker registry + command delegation; SSE/WebSocket to UI
- References: `apps/api/app/main.py`, `apps/worker/app/main.py`, `infra/compose/docker-compose.dev.yml`

## 4) Multi‑Tenancy & RLS
- Shared schema with RLS: policies enforce `tenant_id = current_setting('app.tenant_id')`
- Tenant context set per request from JWT/header in middleware
- References: `apps/api/db/migrations/001_init.sql`, `apps/api/app/core/middleware.py`, `apps/api/app/core/database.py`

## 5) Data Model & Contracts
- Core tables: tenants, sites, cameras, staff, customers, visits, api_keys
- Enhanced: `staff_face_images` with landmarks and embeddings
- JSON Schemas: `contracts/Event.FaceDetected.v1.json`, `contracts/VisitRecord.v1.json`, `contracts/CustomerProfile.v1.json`
- Shared types: Pydantic/TS in `packages/python/common`, `packages/ts/common`
- References: `apps/api/app/models/database.py`, `packages/python/common/common/models.py`

## 6) Face Recognition Pipeline
- Detect: YuNet default; RetinaFace optional; 5‑point alignment
- Embed: ArcFace 512‑D, L2‑norm, cosine similarity
- Search: Milvus collection w/ IVF index; per‑tenant filtering
- Storage: MinIO `faces-raw` (30‑day lifecycle), `faces-derived`
- References: `apps/api/app/core/milvus_client.py`, `apps/api/app/core/minio_client.py`, `apps/api/app/services/face_processing_service.py`

## 7) API Surface (v1)
- Auth: `POST /v1/auth/token` (password or API key → RS256 JWT)
- CRUD: `/v1/tenants`, `/v1/sites`, `/v1/cameras`, `/v1/staff`, `/v1/customers`
- Staff faces: `GET/POST/DELETE /v1/staff/{id}/faces`, recognition test
- Events ingest: `POST /v1/events/face` (multipart image + event payload)
- Analytics: visits listing and distribution/time‑bucketed reports
- Worker proxy: consolidated worker endpoints
- References: `apps/api/app/routers/*.py`, `docs/openapi.json`, `apps/api/openapi.json`

## 8) Worker — Enhanced Architecture
- Pipeline: OpenCV capture → detection → landmarks → embeddings → pre‑match staff
- Enhanced mode: HTTP server, registration/heartbeat, command delegation; MOCK mode for offline
- Demo path: synthetic image upload to `/v1/events/face`
- References: `apps/worker/app/main.py`, `apps/worker/app/detectors.py`, `apps/worker/app/embedder.py`, `apps/worker/app/worker_client.py`

## 9) Web Application
- Auth + role‑aware routes; Tenant context switching
- Pages: Sites, Cameras, Staff, Customers, Visits, Reports, Workers
- Enhanced Staff Mgmt: Face gallery, drag‑drop uploads, recognition test
- Realtime: SSE/WebSocket for camera/worker status; secure media patterns
- References: `apps/web/src/pages/*`, `apps/web/src/components/*`, `apps/web/src/contexts/TenantContext.tsx`

## 10) Security & Privacy
- RS256 JWT; roles: system_admin, tenant_admin, site_manager, worker
- Strict tenant context in DB; per‑request session setting
- MinIO lifecycle: raw retention 30 days (lifecycle rule applied)
- Rate‑limit and audit logging roadmap
- References: `apps/api/app/core/security.py`, `apps/api/app/core/minio_client.py`

## 11) Reliability & Performance
- Offline‑friendly mocks for Milvus/MinIO; resilient startup/shutdown (lifespan)
- Background jobs (scaffolded): purge verification, staff cache refresh, aggregates
- Thresholded search/top‑K controls; IVF parameters
- References: `apps/api/app/main.py`, `apps/api/app/services/background_jobs.py`

## 12) DevOps & Infrastructure
- Dockerfiles (multi‑stage); CI buildx multi‑arch; healthchecks
- Compose dev stack: Postgres, Milvus, MinIO, API, Worker, Web
- Kubernetes manifests: base + prod overlays (Deployments, Ingress, HPA, PVC, NetworkPolicies)
- Systemd for on‑prem services; runbooks and guides
- References: `infra/compose/docker-compose.dev.yml`, `infra/k8s/*`, `infra/systemd/*`, `.github/workflows/*`, `docs/RUNBOOK-systemd.md`, `DEPLOYMENT_GUIDE.md`

## 13) Testing & Quality
- Unit: API services, worker pipeline (mocked detectors/embedders)
- Contract: JSONSchema + shared models; OpenAPI published
- E2E demo: `scripts/e2e_demo.sh`, `scripts/simple_e2e_test.sh`
- Make targets: `fmt`, `test`, `e2e`, `openapi`
- References: `apps/api/tests/*`, `apps/worker/tests/*`, `Makefile`

## 14) Demo Flow (10 minutes)
- Login → verify tenant context
- Upload staff faces → verify embeddings and gallery
- Trigger worker simulated event → API ingestion → visit created
- Show Visits and Reports updating; optional CSV export

## 15) Non‑Functional & Ops
- 12‑factor env config; structured JSON logs; Prometheus hooks
- Health probes; graceful shutdown
- References: `docs/QUICKSTART.md`, `README.md`

## 16) Current Status vs WBS
- Present: core APIs, enhanced worker, web MVP, RLS, MinIO lifecycle
- In progress: APScheduler jobs, admin merge/audit flows, purge verification tests
- Blockers: finalize background jobs and audit logging for prod sign‑off

## 17) Risks & Mitigations
- Model runtime on arm64 → ONNXRuntime/PyTorch fallback; MOCK mode
- Milvus schema evolution → plan metadata additions, safe migrations
- On‑prem network variability → local queue + exponential backoff

## 18) Roadmap (Next 4–6 Weeks)
- Finalize background jobs + audit logging
- Harden rate limiting and security posture
- E2E Playwright UI and Locust perf scenarios
- Production packaging (Kustomize/Helm) and cluster runbooks

## 19) Deployment Options
- Local dev: Make targets; Compose for integrated testing
- Production: Kubernetes overlays; Secrets for RS256 keys; systemd for edge workers

## 20) Appendix (References)
- Contracts: `contracts/*.json`
- API: `apps/api/app/*`; OpenAPI at `/v1/openapi.json`
- Worker: `apps/worker/app/*`
- Web: `apps/web/*`
- Infra: `infra/compose/*`, `infra/k8s/*`; CI/CD in `.github/workflows/*`
- Postman: `docs/postman_collection.json`

