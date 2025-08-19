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