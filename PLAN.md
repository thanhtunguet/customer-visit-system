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

2. Data & Schemas

2.1 PostgreSQL schema & RLS
	•	Deliverable: SQL migrations for tenants, sites, cameras, staff, customers, visits, api_keys. RLS on tenant-scoped tables.
	•	DoD: make migrate applies; RLS test proves cross-tenant leak impossible.

2.2 Milvus collection & indexes
	•	Deliverable: face_embeddings (dim=512, metric=cosine), partitions per tenant_id; IVF index config (nlist/nprobe).
	•	DoD: Insert/search e2e test <100ms p95 on sample data (≥100k vectors).

2.3 MinIO buckets & lifecycle
	•	Deliverable: Buckets faces-raw, faces-derived; 30-day lifecycle on raw; presigned URL helper.
	•	DoD: Object older than 30 days is auto-deleted in sandbox; presigned URL works.

2.4 JSON contracts
	•	Deliverable: Versioned JSON Schemas in contracts/:
	•	Event.FaceDetected.v1
	•	VisitRecord.v1
	•	CustomerProfile.v1
	•	DoD: Schemas validated at runtime with Pydantic/ajv; contract tests pass.

⸻

3. API Backend (FastAPI)

3.1 AuthN/Z & multi-tenant guard
	•	Deliverable: JWT (HS/RS), roles: system_admin / tenant_admin / site_manager / worker; dependency injects tenant_ctx.
	•	DoD: Protected endpoints return 401/403 as expected; RLS enforced.

3.2 Core endpoints (v1)
	•	Deliverable:
	•	Tenants/Sites/Cameras CRUD
	•	Staff CRUD (enrollment stores embeddings tagged is_staff)
	•	Events intake: POST /v1/events/face (embedding+meta)
	•	Matching: server queries Milvus, returns person_id|new
	•	Visits query: paginated, filter by time/site
	•	Reports: visitor counts (hour/day/week/month), new vs repeat, gender, DOW
	•	DoD: OpenAPI docs; Postman collection; integration tests green.

3.3 Background jobs
	•	Deliverable: Scheduler (APScheduler/Celery) for: raw image purge verify, report materialization, staff cache refresh.
	•	DoD: Jobs visible in logs; idempotent; unit tests.

3.4 Performance controls
	•	Deliverable: Batch insert, DB indexes, Milvus search params (nprobe) via env.
	•	DoD: Load test: sustain ≥50 events/s aggregate with p95 API <300ms on dev hardware.

⸻

4. Edge Worker (Mac Mini)

4.1 Capture & decode
	•	Deliverable: RTSP/USB capture via OpenCV/FFmpeg, frame throttling (e.g., 5 FPS), motion gate (optional).
	•	DoD: Works with RTSP test source; configurable fps/skip.

4.2 Detection & alignment
	•	Deliverable: YuNet (fast) and RetinaFace (accurate) selectable; 5-point alignment.
	•	DoD: Detector unit test on sample images: ≥95% recall on provided set.

4.3 Embeddings
	•	Deliverable: InsightFace ArcFace (512-D) via ONNX/PyTorch (M-series friendly); L2-norm; cosine similarity.
	•	DoD: Embedding consistency test (same face >0.6 cosine; different <0.4 on sample set).

4.4 Staff pre-filter
	•	Deliverable: In-memory staff gallery per site; local match before upload.
	•	DoD: Staff not sent as customer events; unit tests.

4.5 Event upload & resilience
	•	Deliverable: Signed requests to API with backoff; local disk queue for outages; snapshot JPEG optional.
	•	DoD: Network cut test: events buffered and replayed; no loss.

4.6 Packaging & ops
	•	Deliverable: Docker (arm64) & native runner; scripts/mac/setup.zsh; env-based config.
	•	DoD: ./run-worker.sh starts service on Mac; logs to file/syslog.

⸻

5. Matching & Identity

5.1 Server-side search & thresholding
	•	Deliverable: Top-K (k=5) search, calibrated threshold; create-or-link customer; multi-embedding per person; optional centroid.
	•	DoD: Confusion matrix on validation set; target FAR <1% @ TAR ≥95% (sample data).

5.2 Cross-tenant policy
	•	Deliverable: Default: search within tenant partition; config flag for global search (admin only).
	•	DoD: Unit tests assert partition scoping.

5.3 Merge & dedupe tools
	•	Deliverable: Admin endpoint to merge person_ids; cascades visits; removes old vectors.
	•	DoD: Post-merge integrity tests pass.

⸻

6. Analytics & Reporting

6.1 Materialized views
	•	Deliverable: Daily/hourly aggregates per (tenant, site), repeat vs new, gender, DOW.
	•	DoD: Query time <200ms for 1y window on sample volume.

6.2 Export
	•	Deliverable: CSV export endpoints; time/site filters.
	•	DoD: Downloaded CSV matches API totals.

⸻

7. Security & Privacy

7.1 Retention enforcement
	•	Deliverable: S3 lifecycle + audit job verifying deletions; nullify image_path after purge.
	•	DoD: After 30d in test clock, images gone, DB pointers cleaned.

7.2 Secrets & policies
	•	Deliverable: K8s Secrets; NetworkPolicies; least-privilege DB roles; API rate limiting.
	•	DoD: Pod-to-DB restricted; load test shows 429 when exceeding limits.

7.3 Audit logs
	•	Deliverable: Admin actions & data exports logged with tenant/user context.
	•	DoD: Logs searchable; tamper-evident (append-only index).

⸻

8. Frontend (React + Vite + AntD + Tailwind)

8.1 Shell & auth
	•	Deliverable: Login, role-aware routing, layout (sidebar/topbar).
	•	DoD: Unauthorized paths redirect; token refresh works.

8.2 Entity management
	•	Deliverable: CRUD pages: sites, cameras, staff, customers; table filters/sort; forms with validation.
	•	DoD: E2E tests (Playwright) cover create/edit/delete happy paths.

8.3 Live monitor
	•	Deliverable: Recent events list via WebSocket/SSE; snapshot refresh; status badges.
	•	DoD: New visit appears in UI <2s from API event (dev env).

8.4 Reports
	•	Deliverable: Charts (Recharts): time series, DOW heatmap, new vs repeat, gender; export CSV.
	•	DoD: Visuals match API data; download correct.

⸻

9. DevOps

9.1 Docker & Compose
	•	Deliverable: Multi-arch Dockerfiles; docker-compose.dev.yml (api, web, worker-sim, postgres, milvus, minio).
	•	DoD: make dev-up runs full stack; sample flow works.

9.2 Kubernetes (prod-like)
	•	Deliverable: Manifests: Deployment/Service/Ingress/HPA/PVC for api, web, postgres, milvus, minio; NetworkPolicies; PodSecurity.
	•	DoD: kustomize build valid; kubectl apply boots cluster locally (kind/microk8s) with health checks.

9.3 CI/CD
	•	Deliverable: GitHub Actions: build/test; buildx multi-arch images; push to registry; deploy job (manual gate).
	•	DoD: Badge green; tagged release produces images & manifests.

9.4 Observability
	•	Deliverable: Prometheus metrics (api/worker), Grafana dashboards; request/latency panels; alerting rules.
	•	DoD: Dashboards render; test alert fires on synthetic SLO breach.

⸻

10. Testing & QA

10.1 Unit tests
	•	Deliverable: ≥80% coverage on api core & worker core.
	•	DoD: Coverage gate enforced in CI.

10.2 Contract tests
	•	Deliverable: Schemas validated both sides; Pact (or JSONSchema) tests.
	•	DoD: Breaking changes caught in CI.

10.3 E2E scenario
	•	Deliverable: Synthetic RTSP stream → worker → api → milvus → reports → UI.
	•	DoD: Single script scripts/e2e_demo.sh proves flow; artifacts stored.

⸻

11. Rollout & Ops

11.1 Mac Mini provisioning
	•	Deliverable: scripts/mac/setup.zsh (install Docker, pull image, launch agent, logrotate).
	•	DoD: Fresh Mac runs worker in <10 min.

11.2 Runbooks & SRE docs
	•	Deliverable: Oncall cheatsheet: restart, scale, diagnose, rotate keys.
	•	DoD: Peer dry-run passes.

⸻

12. Optional backlog (post-MVP)
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