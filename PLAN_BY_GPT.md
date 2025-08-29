Plan for Claude Code: Analyze & Enhance Camera–Worker Delegation

1) Inputs Claude should ask for (or autodetect)
	•	Codebase layout (backend FastAPI, worker service, shared protos/schemas).
	•	DB flavor (Postgres assumed) and migration tool (Alembic?).
	•	Current WebSocket protocol (messages, auth, heartbeat, errors).
	•	Current models/tables: tenants, sites, workers, cameras.
	•	Where RTSP/webcam handling lives (worker; FFmpeg/GStreamer wrappers?).
	•	CI pipeline & test strategy (pytest, mypy, ruff).
	•	Config/secrets management (env vars, Vault/KMS).

⸻

1) Quick repo audit & bug triage (“connected but not starting”)

1.1 Trace the startup path (backend & worker)
	•	Backend:
	•	Where do we assign a camera on worker connect?
	•	Is assignment persisted, or only in memory?
	•	What message instructs worker to start camera?
	•	Are there race conditions around site matching or camera availability?
	•	Worker:
	•	On WebSocket OPEN: do we send REGISTER? Do we await START(camera_id)?
	•	Do we handle START payload errors (e.g., missing RTSP creds)?
	•	Is there a debounce/backoff that delays start forever?

1.2 Add temporary instrumentation to isolate failure
	•	Backend: log (INFO) for on_connect, assignment_decision, send_start, ack_start, with correlation IDs.
	•	Worker: log (INFO) for on_assign, pipeline_boot, pipeline_ready, pipeline_error, heartbeat_renew.
	•	Verify that START is actually sent and ACKed; if not, identify where it drops (serialization, auth, filters).

1.3 Common root causes to check programmatically
	•	Site mismatch (worker site_id null / incorrect).
	•	Camera status not “AVAILABLE” due to stale flags.
	•	Assignment is “sticky” to an offline worker (no reclaim).
	•	Worker ignoring START due to FSM being in wrong state (e.g., RECONNECTING).
	•	RTSP probe failing; pipeline errors swallowed; worker never transitions to RUNNING.

Claude action: generate a “delegation_debug.md” checklist in the repo and wire temporary logs with structured JSON.

⸻

2) Data model & migrations (introduce leases)

Create/alter tables (Postgres + Alembic):

-- camera_sessions: one row per camera; re-written per (camera_id, generation)
CREATE TABLE camera_sessions (
  camera_id         UUID PRIMARY KEY,
  tenant_id         UUID NOT NULL,
  site_id           UUID NOT NULL,
  worker_id         UUID,
  generation        BIGINT NOT NULL DEFAULT 0,
  state             TEXT NOT NULL DEFAULT 'PENDING', -- PENDING|ACTIVE|PAUSED|ORPHANED|TERMINATED
  lease_expires_at  TIMESTAMPTZ,
  reason            TEXT,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- workers: add health & capacity
ALTER TABLE workers
  ADD COLUMN status TEXT NOT NULL DEFAULT 'REGISTERED',
  ADD COLUMN capacity JSONB NOT NULL DEFAULT '{"slots":1,"cpu":0,"gpu":0,"mem":0}',
  ADD COLUMN last_seen_at TIMESTAMPTZ;

-- cameras: add capabilities & last probe
ALTER TABLE cameras
  ADD COLUMN caps JSONB,           -- e.g., {"codec":"h264","res":"1920x1080","fps":25}
  ADD COLUMN last_probe_at TIMESTAMPTZ,
  ADD COLUMN last_state_change_at TIMESTAMPTZ;

Claude action: write Alembic migration with forward/backward steps and seed caps by probing known RTSP URLs (optional script).

⸻

3) Control plane protocol (backend ↔ worker)

3.1 Message types (JSON over WebSocket; later: gRPC bidi if desired)
	•	Worker → Server:
	•	REGISTER {worker_id, site_id, version, labels?, capacity?}
	•	HEARTBEAT {worker_id, metrics, renew: [{camera_id, generation}]}  // renew leases
	•	ACK {intent_id, status, details?}
	•	EVENT {camera_id, generation, seq, type, ts, payload}  // e.g., pipeline_ready, rtsp_error
	•	Server → Worker:
	•	START {intent_id, camera_id, generation, source: {type: "rtsp"|"webcam", url_enc?|device?}, model_ver, params}
	•	STOP {intent_id, camera_id, generation, reason}
	•	RELOAD {intent_id}
	•	DRAIN {intent_id}

3.2 Idempotency keys
	•	Every server intent carries (camera_id, generation, intent_id).
	•	Worker emits ACK and subsequent EVENTs tagged with the same (camera_id, generation) and seq.

Claude action: generate shared Python dataclasses / Pydantic models for these messages and enforce validation.

⸻

4) Assignment algorithm (lease-based & capacity-aware)

4.1 API endpoints (FastAPI)
	•	POST /workers/{id}/register (or via WebSocket REGISTER).
	•	POST /assign (internal): picks a camera for worker_id.
	•	Site-aware filter, tenant quota, camera status = AVAILABLE/ORPHANED.
	•	Capacity-aware (least slots used).
	•	Optimistic concurrency:

UPDATE camera_sessions
  SET worker_id=:wid, lease_expires_at=now()+:ttl, state='ACTIVE', generation=generation+1, updated_at=now()
  WHERE camera_id=:cid AND (worker_id IS NULL OR lease_expires_at < now()) AND generation=:expected_gen;

If rowcount=0 → retry with next candidate.

	•	POST /leases/renew: extend lease_expires_at for the tuple(s) included in heartbeat.
	•	POST /leases/reclaim: cron/scheduler to mark ORPHANED when expired; HARD reclaim after 10 min.

4.2 Timers
	•	lease_ttl: 90s (renew every 10s with heartbeat).
	•	soft_reclaim_window: assign only if capacity constrained when expired < 10m.
	•	hard_reclaim: >10m → reassign immediately.

Claude action: implement AssignmentService with site & capacity filters + retries; unit tests for race conditions.

⸻

5) Worker Finite State Machine (FSM)

States: INIT → REGISTERED → IDLE → RUNNING(camera_id) → RECONNECTING → DRAINING → STOPPED

Transitions:
	•	On START: IDLE → RUNNING (setup pipeline, emit pipeline_ready).
	•	On transient net error: RUNNING → RECONNECTING (keep buffers), then back.
	•	On STOP/DRAIN: gracefully stop, flush events, release lease.
	•	On unrecoverable RTSP error K times: emit pipeline_error, remain RUNNING but paused, or move to IDLE per policy.

Claude action: add a small FSM class (pure Python, tested) and integrate in worker main loop.

⸻

6) Media pipeline hardening (worker)
	•	Decode via VideoToolbox (Mac mini M4) using ffmpeg or avfoundation for webcams.
	•	Stall detection: if no frames for N sec → restart pipeline with jittered backoff (1, 2, 4, … 60s).
	•	Dynamic throttling: allow config detect_every_n_frames, downscale to 640p for detection; keep tracking internally.
	•	Edge ring buffer: store last 10–30s of compressed frames to /tmp/worker/{camera_id}/.
	•	Model hot-swap: periodically check signed bundle version; atomic reload.

Claude action: wrap pipeline in a Supervisor that produces structured EVENTs and exposes health to the main loop.

⸻

7) Observability (logs, metrics, tracing)

7.1 Metrics (OTLP)
	•	Worker: decode_fps, detect_fps, latency_ms_p50/p95, dropped_frames, ringbuf_seconds, lease_renew_rtt, state.
	•	Backend: assign_attempts, assign_success, reclaims_soft/hard, leases_active, heartbeats_missing.

7.2 Structured logs
	•	JSON logs with tenant_id, site_id, worker_id, camera_id, generation, intent_id, trace_id.

7.3 Health rules
	•	Camera DOWN if no frames > X sec and K consecutive restart failures.
	•	Worker UNHEALTHY if missed heartbeats > M.

Claude action: instrument with OpenTelemetry (fastapi + worker), export to your collector.

⸻

8) Security & privacy touch-ups
	•	Enforce mTLS (short-lived certs) between worker and server.
	•	Store RTSP creds encrypted (KMS), deliver only on START and never log.
	•	RBAC per tenant on all endpoints; audit log on manual overrides.
	•	Configurable retention for frames vs embeddings; “do not process” flags bypass pipeline.

Claude action: add pydantic Settings, secret loaders, and scrubbers for logs.

⸻

9) Test plan (unit + integration + chaos)

9.1 Unit tests
	•	Assignment with optimistic concurrency & retries.
	•	FSM transitions (happy path, errors, drains).
	•	Lease renew & reclaim edge cases (time travel via freezegun).

9.2 Integration tests
	•	Spin backend + in-memory worker with simulated camera (file or generator).
	•	Validate REGISTER → START → pipeline_ready → HEARTBEAT renew → STOP → lease release.

9.3 Chaos tests
	•	Drop WebSocket mid-stream; verify lease not immediately reassigned (soft window).
	•	Fake RTSP auth failure; confirm backoff and error event.

Claude action: create tests/integration/test_end_to_end.py and docker-compose for local run.

⸻

10) Rollout plan
	1.	Phase 1 (dark launch): add camera_sessions table; write records but keep old behavior; compare assignment decisions in logs.
	2.	Phase 2: switch a small site to lease-based control; enable new worker FSM behind a feature flag.
	3.	Phase 3: enable across tenants; set SLOs (≥99% camera availability during business hours).
	4.	Phase 4: deprecate legacy assignment paths; remove temp logs.

Claude action: add feature flags (env or DB) and a rollout.md.

⸻

11) Concrete deliverables & file map (what Claude should generate)
	•	Backend
	•	app/models/camera_sessions.py (SQLAlchemy)
	•	app/services/assignment.py (site/capacity/lease logic)
	•	app/api/ws_protocol.py (Pydantic schemas for WS messages)
	•	app/api/ws_handler.py (handlers, intents, ACK tracking)
	•	app/cron/reclaim_leases.py
	•	alembic/versions/<timestamp>_camera_sessions.py
	•	app/observability/otlp.py
	•	Worker
	•	worker/fsm.py
	•	worker/protocol.py (schemas; shared if possible)
	•	worker/supervisor.py (pipeline wrapper, ring buffer, backoff)
	•	worker/main.py (WS loop: register → heartbeat → handle intents)
	•	worker/observability/metrics.py
	•	Tests
	•	tests/unit/test_assignment.py
	•	tests/unit/test_fsm.py
	•	tests/integration/test_e2e.py
	•	Docs
	•	docs/protocol.md
	•	docs/delegation_debug.md
	•	docs/rollout.md

⸻

12) Pseudocode snippets Claude can expand

12.1 Assign camera (optimistic concurrency)

async def assign_camera(worker_id: UUID, site_id: UUID) -> Optional[CameraSession]:
    candidates = await repo.list_available_cameras(site_id=site_id)
    for cam in sorted(candidates, key=score_by_capacity):
        # read current generation
        sess = await repo.get_or_create_session(cam.id)
        updated = await repo.try_take_lease(
            camera_id=cam.id,
            worker_id=worker_id,
            expect_generation=sess.generation,
            ttl=timedelta(seconds=90),
        )
        if updated: 
            await control.send_start(worker_id, cam, generation=sess.generation+1)
            return updated
    return None

12.2 Heartbeat & renew

# worker
while True:
    await ws.send_json({
        "type":"HEARTBEAT",
        "worker_id": wid,
        "metrics": collect_metrics(),
        "renew": [{"camera_id": cid, "generation": gen} for cid, gen in active_sessions()],
    })
    await asyncio.sleep(10)

12.3 FSM sketch

class WorkerFSM:
    state = "IDLE"
    def on_start(self, camera):
        assert self.state in {"IDLE","RECONNECTING"}
        self.state = "RUNNING"
        self.supervisor.start(camera)
    def on_stop(self):
        if self.state == "RUNNING":
            self.supervisor.stop()
        self.state = "IDLE"


⸻

13) Acceptance criteria (definition of done)
	•	Worker connects; within ≤3s receives START when an eligible camera exists.
	•	Pipeline emits pipeline_ready within ≤10s, backend marks camera ACTIVE.
	•	Lease renews every 10s; if worker disconnects:
	•	<90s: lease remains; no reassignment.
	•	90s–10m: soft reclaim (no reassignment unless capacity pressure).
	•	10m: hard reclaim; different worker starts camera within ≤20s.
	•	Observability: dashboard shows per-camera state, lease TTL, worker health.
	•	No plaintext RTSP creds in logs. All intents/event logs include correlation IDs.
	•	Test suite passes locally and in CI; integration test covers the above flows.

⸻

14) Immediate fix for “connected but does not start”

Claude should:
	1.	Add structured logs around REGISTER, assignment, send START, ACK START.
	2.	Assert that site_id is present on workers and used in filters.
	3.	Verify backend actually persists an assignment (or new camera_sessions) and sends START.
	4.	On worker, ensure START handler calls the pipeline supervisor and emits pipeline_ready/pipeline_error.
	5.	Add a timeout guard: if START sent but no pipeline_ready within 15s, backend marks session PAUSED with reason and optionally retries elsewhere (respecting soft window).
