# DreamGuard — Implementation Plan

Companion to [PRD.md](PRD.md). This document is the working checklist for the MVP.
Each phase ends with a review: work on the next phase starts only after explicit approval.

**Status legend:** `[x]` finished · `[ ]` pending

---

## 1. Current state (baseline review)

| Area | State at baseline |
|---|---|
| Core library (`src/dreamguard`) | `guard.py` with `SafetyConfig`, `SafetyReport`, `UnsafeActionError`, single `inspect()` method; `adapter.py` wraps `client.get_action()`; `demo.py` with 2 scenarios |
| Tests | 7 passing tests (`tests/test_guard.py`) |
| Backend | FastAPI scaffold imported as `python_rest_api_template/` (not yet integrated) |
| Frontend | None |
| Simulator | None |
| Dream SDK | `dreamlabs-client` 1.1.7 (Python 3.10–3.12) |

### Confirmed safety defects (reproduced)

| # | Input | Result | Issue |
|---|---|---|---|
| D1 | NaN in `current_joints` | APPROVED | `abs(nan) > limit` is False — fails open |
| D2 | 3 rad jump on row 0, no `current_joints` | APPROVED | Step check skipped when state is absent |
| D3 | Rows of `np.float32` | BLOCKED | False rejection (`np.float32` is not a `float`) |
| D4 | Right chunk 50 rows, left 3 rows | APPROVED | Chunk length / arm consistency never checked |

### PRD gap summary

| Requirement | Baseline |
|---|---|
| FR-01 Interception | Only `get_action` wrapped; `robot.play()` reachable directly |
| FR-02 Input validation | Partial (D3, D4, current state unvalidated) |
| FR-03 Joint limits | Placeholder ±π limits |
| FR-04 Movement limits | Partial (D1, D2); no velocity limit tied to `action_hz` |
| FR-05 Workspace | FK hook only; no YAM FK; no coordinate frame defined |
| FR-06 Separation | Untested |
| FR-07 Risk score | `60 + 10 × findings` |
| FR-08 Decisions | Boolean only; no `Decision` enum |
| FR-09 Logging | Missing |
| FR-10 Replay | Missing |

### External findings

- **Dream SDK action format:** `q_r_chunk` / `q_l_chunk` are `[H, 7]` (6 joints + gripper), default
  `action_hz=20`, `execution_horizon=30`. State arrays are float32. The client smooths chunks before returning them.
- **No programmatic simulator:** the Dream Labs Sim Playground is browser-only. DreamGuard provides its own
  robot API through a local MuJoCo simulation.
- **YAM model:** MuJoCo Menagerie `i2rt_yam` (MIT). Real joint limits (rad):

  | Joint | 1 | 2 | 3 | 4 | 5 | 6 |
  |---|---|---|---|---|---|---|
  | Range | −2.618…3.054 | 0…3.665 | 0…3.665 | ±1.571 | ±1.571 | ±2.094 |

  Gripper: finger slide 0…0.041 m. FK target: `grasp_site`.
  **Risk:** Dream-1 joint zero conventions may differ from the MuJoCo model; verify with the first real chunk.

---

## 2. Decisions

| Topic | Decision |
|---|---|
| Robot API | Local MuJoCo bimanual YAM simulator |
| Dashboard | React + Vite + TypeScript |
| Backend | Imported FastAPI scaffold, integrated as `backend/` following its conventions |
| Scope | MVP. APPROVE / BLOCK only; MODIFY reserved for later |
| RSA utilities | Kept (`en_de_crypt.py`, `keys_generator.py`, `keys_generator_dtrmnstc.py`) |
| Removed from scaffold | `validators.py`, Redis cache, `pycache_n_logs_deleter.py`, placeholder router/model/service; deps `phonenumbers`, `redis`, `requests`, `pyyaml` |
| `.env.example` | Kept (standard name) |
| Author headers | Kept (Sebastian Russo) |
| Wording | No "template" / "example" naming in the integrated backend |
| Configuration format | JSON, matching the backend's `config_file.json` convention |

---

## 3. Paid-call policy

Dream credits are scarce. **No paid call is made without explicit approval for that specific run.**

| SDK action | Cost |
|---|---|
| `DreamClient()` / `close()` | Free (local) |
| `policy(config)` | Free (sends nothing) |
| `set_observation(...)` | Free (local validation against the embodiment) |
| **`get_action()`** | **Paid — inference** |
| `python -m dream.check`, `get_models()` | Treated as paid; not run |

Enforcement:
- Paid calls require `dream.allow_paid_calls: true` in `config_file.json` **and** `DREAMGUARD_ALLOW_PAID=1` in `.env`.
- Hard cap per run: `max_paid_calls_per_run`. The dashboard confirms before a paid run.
- Free **preflight**: `policy()` + `set_observation()` with simulator frames/state, stopping before `get_action()`.
- Every paid reply is recorded to `fixtures/dream1/*.json` and reusable through the `replay` source.
- Budget: 3 attempts, only after all free work is complete (schema capture → short run → final demo).

---

## 4. Target repository layout

```text
dreamguard/
├── src/dreamguard/              # core library (no web dependencies)
│   ├── guard.py checks.py report.py config.py adapter.py events.py
│   ├── profiles/   yam_sim.json (safety profile, shipped as package data)
│   ├── sim/        scene_bimanual.xml, vendored i2rt_yam (MIT), robot.py, kinematics.py
│   └── sources/    fake.py, replay.py, dream1.py (paid-call guarded)
├── backend/                     # FastAPI service
│   ├── main.py  requirements.txt  DOCKERFILE  docker-compose.yml  start.bat  start.sh
│   ├── tests/
│   └── src/
│       ├── api_endpoints/root_endpoint.py
│       ├── api_endpoints/routers/{runs,sessions,safety,stream}/   # one endpoint per file
│       ├── core_specs/configuration/  config_file.json  config_loader.py
│       ├── core_specs/data/           general_data.json  data_loader.py
│       ├── models/  resources/  utils/
├── frontend/                    # React + Vite + TS
├── fixtures/dream1/             # recorded paid replies
├── integrations/                # Dream-1 loop integration (was examples/)
├── tests/                       # core library tests
└── documentation/  PRD.md  IMPLEMENTATION_PLAN.md
```

### `config_file.json` sections

- `defaults` — data, profile, sessions and frontend build paths
- `logging` — level, directory, `log_file_name: "dreamguard_backend"`
- `network` — host `127.0.0.1`, port, `workers: 1`, `cors_origins`
- `dream` — `allow_paid_calls: false`, `max_paid_calls_per_run`, `checkpoint`, `timeout_ms`, `action_hz`
- `simulation` — scene, camera 320×176, JPEG quality 85, physics rate
- `endpoints` — one entry per route (`request_limit`, `unit_of_time_for_limit`, `endpoint_prefix`, `endpoint_tag`, `endpoint_route`)

`general_data.json` holds the fault catalog, scenarios, joint names and project metadata.

---

## 5. Phases

### Phase 0 — Environment and backend integration (free) — **FINISHED**

- [x] Create `.venv` (Python 3.12) and install the core library with dev dependencies
- [x] Move `python_rest_api_template/` to `backend/` (`git mv`); delete its empty `.env`
- [x] Remove unused scaffold pieces and dependencies (keep RSA utilities)
- [x] Remove "template" / "example" wording; rename config, logger, Docker and start scripts to DreamGuard
- [x] Fix scaffold defects:
  - [x] T1 `requirements.txt` UTF-16 without BOM → UTF-8
  - [x] T2 `.gitignore` ignored `test_*.py` / `*_test.py`
  - [x] T3 `.dockerignore` allowed `.env` into images
  - [x] T4 `log_handler(...)` called as a function in `main.py`
  - [x] T5 config/data loaders used CWD-relative paths (`resolve_backend_path`)
  - [x] T6 inconsistent `.env` / `.env.local` loading; load repo-root `.env`
  - [x] T7 `en_de_crypt.py` fails at import without keys (kept; not imported by the app; documented)
  - [x] T8 no CORS configuration (`network.cors_origins`)
  - [x] T9 `workers` pinned to 1; WebSocket rate-limit exception documented
  - [x] T10 Docker cleanup (stage casing, obsolete `version:`, Redis service, container names)
- [x] Merge `.gitignore` files; update root `.env.example`
- [x] `pyproject.toml`: `requires-python = ">=3.11,<3.13"`, `numpy` dependency
- [x] Backend health test, `AGENTS.md`, CI workflow (ruff + core tests + backend tests)
- [x] Verify: core tests, backend tests, backend boots and `/` responds

**Phase 0 notes**
- Removed: `validators.py`, Redis cache (`resources/cache/`), `pycache_n_logs_deleter.py`, placeholder
  routers/model/service, empty `resources/db/` and `resources/mock_db_jsons/` placeholders; dependencies
  `phonenumbers`, `redis`, `requests`, `pyyaml`.
- `backend/.env.example` and `backend/.gitignore` merged into the repository-level files (single `.env`).
- `examples/` renamed to `integrations/`; PRD path references are updated in Phase 8.
- Ruff lints the core library (backend excluded); the backend is linted with `backend/.pylintrc`
  (CI gate `--fail-under=9.5`, current score 9.74). Section-marker strings and the `load_dotenv`
  import order are backend conventions and are disabled in `.pylintrc`.
- `scripts/check_dream_sdk.py` passes (SDK 1.1.7, key loaded, no inference request).
- `docker compose config` validates; the Docker image was not built.
- Results: 11 tests passing (7 core + 4 backend), ruff clean, backend serves `/` and `/docs`.

### Phase 1 — Safety defect fixes (free) — **FINISHED**

- [x] D1 validate `current_joints` (length, numeric, finite) → BLOCK on failure
- [x] D2 `require_current_state = True` (fail closed); row 0 always checked against current state
- [x] D3 accept numpy scalars / `numbers.Real`, reject `bool`
- [x] D4 configurable `min_rows` / `max_rows`; both arms must share H
- [x] Missing tests: workspace out of bounds, required FK missing, FK raises, separation violated, FK non-finite
- [x] Fix demo literal `\n` output

**Phase 1 notes**
- New `SafetyConfig` fields: `require_current_state=True`, `min_rows=1`, `max_rows=200`.
  Calling `inspect()` / `approve()` without `current_joints` now blocks unless
  `require_current_state=False` is set explicitly. README integration snippet updated accordingly.
- Shared helpers `_as_number` / `_as_vector` validate action rows and the measured state identically
  (`numbers.Real` accepts Python and NumPy scalars; `bool` and `np.bool_` are rejected).
- Additional demo defect found and fixed: both arms shared the same row lists, so modifying the right
  arm also changed the left arm (the demo reported a left-arm violation that did not exist).
- Tests: 36 core guard/demo tests (was 7) + 4 backend = 40 passing; ruff clean.
  The original D1–D4 reproductions now behave correctly (D1, D2, D4 blocked; D3 approved).

### Phase 2 — Safety engine restructure (free) — **FINISHED**

- [x] `report.py`: `Decision` enum, structured `Finding`, `SafetyReport` with latency
- [x] `checks.py`: one pure function per rule
- [x] `config.py`: `SafetyConfig` + JSON profile loader; `profiles/yam_sim.json` with real YAM limits
- [x] Velocity limit (`max_joint_velocity_rad_s × 1/action_hz`)
- [x] Severity-weighted risk score + near-limit warnings
- [x] Public API (`SafetyGuard.inspect` / `approve`) unchanged

**Phase 2 notes**
- Modules: `report.py` (`Decision`, `Severity`, `Finding`, `SafetyReport`, `compute_risk`,
  `UnsafeActionError`), `config.py` (`SafetyConfig`, `load_profile`, `load_builtin_profile`),
  `checks.py` (parsing + one function per rule), `guard.py` (orchestrator). Existing imports from
  `dreamguard.guard` keep working.
- One intended API change: `SafetyReport.findings` holds `Finding` objects instead of strings
  (`report.messages` gives the strings). `as_dict()` now includes `decision`, structured findings
  and `latency_ms`. `approved` is kept as a property.
- `SafetyConfig` validates itself on construction (fail closed): non-finite values, inverted
  ranges, wrong lengths, invalid row bounds or booleans raise `ValueError`. Profiles reject unknown
  keys (typo protection); `name` / `description` / `source` / `notes` are allowed metadata.
- New fields: `gripper_range`, `max_joint_velocity_rad_s` (per joint, `None` = off), `action_hz`,
  `near_limit_margin_rad` (`0` = off). Defaults keep previous behaviour.
- The profile lives at `src/dreamguard/profiles/yam_sim.json` (package data, verified in the built
  wheel) instead of a top-level `profiles/` folder, so it ships with the library.
- `yam_sim`: Menagerie YAM joint ranges, `action_hz` 20, step 0.35 rad, velocity 3.0 rad/s per joint,
  near-limit margin 0.05 rad. Step/velocity values are development guardrails to tune in Phase 7;
  workspace/separation stay off until simulator FK exists (Phase 4).
- Velocity is checked between consecutive rows only; row 0 vs the measured state is covered by the
  step check (it includes network latency, not a commanded velocity).
- Risk score: violations score their check weight (70–100) + 2 per extra violation (cap 100);
  approved actions score their strongest near-limit warning (0–50).
- Demo prints the PRD §11 format (decision, risk, latency, findings).
- Tests: 92 core + 4 backend = 96 passing; ruff clean.
- Local note: the sandbox blocks pytest's default temp dir, so local runs used
  `--basetemp=.pytest_cache/tmp`; CI is unaffected.

### Phase 3 — Enforced interception and events (free) — **FINISHED**

- [x] `GuardedController`: sole path to `robot.play`; holds pose on BLOCK; stops after N consecutive blocks
- [x] `guarded_get_action` derives `current_joints` from the observation
- [x] `events.py`: event bus → JSONL session files + live subscribers
- [x] Spy-robot test: blocked actions never reach `play()`

**Phase 3 notes**
- `GuardedController(robot, guard, bus=, session_id=, source=, max_consecutive_blocks=3, on_block=)`
  with `submit(action, current_joints=| observation=)` and `reset()`. The robot is held privately;
  APPROVE plays a copy of the validated action (later caller mutations cannot alter it), BLOCK plays
  nothing (position-controlled robots keep their last approved targets) and runs `on_block`.
  After N consecutive blocks the controller halts and raises `ControllerHaltedError` until `reset()`.
  Submissions are serialized with a lock.
- Validation runs once per action: `guard.approved_copy()` is shared by `approve()` and the controller.
- `events.py`: `SafetyEvent` (session, sequence, timestamp, source, decision report, action chunks,
  measured state, executed / halted / error), thread-safe `EventBus` (failing subscribers are logged
  and isolated), `JsonlSessionRecorder` (one JSON line per decision, `allow_nan=False`),
  `read_session`, `list_sessions`. Session ids are restricted to `[A-Za-z0-9_-]{1,64}` because they
  become file names (path traversal rejected).
- A robot `play()` failure is recorded in the event (`executed=False`, `error`) and re-raised.
- `guarded_get_action(client, guard, observation)` reads `state.right_arm` / `state.left_arm`;
  explicit `current_joints=` still works.
- Mutation check: forcing the controller to play every action makes 12 interception tests fail.
- Integration skeleton uses the `yam_sim` profile and the observation helper, and is marked as a
  paid call. README integration section rewritten around `GuardedController` and session recording.
- Tests: 130 core + 4 backend = 134 passing; ruff clean; backend pylint 9.74.

### Phase 4 — MuJoCo bimanual simulator (free) — **FINISHED**

- [x] Vendor `i2rt_yam` (MIT) and build `scene_bimanual.xml` (2 arms, overhead + 2 wrist cameras, table, objects)
- [x] `SimRobot`: `joints()`, `gripper()`, `jpeg(camera)` (320×176, q85), `play(chunk)` at `action_hz`
- [x] Gripper mapping 0…1 → 0…0.041 m
- [x] `mujoco_fk`: `grasp_site` in world frame (workspace + separation checks)
- [x] `FakeDreamClient` (scripted chunks + fault injection) and replay source

**Phase 4 notes**
- Dependencies (optional extra `sim`): `mujoco` 4.0.1 (released 2026-11-11) and `pillow` 13.0.0
  (2026-10-16). Nothing else to download and no extra key; rendering uses the machine's OpenGL
  (verified offscreen on this Windows machine; CI installs EGL and sets `MUJOCO_GL=egl` on Linux).
- Vendored Menagerie `i2rt_yam` unmodified at commit `b0655057` (5.3 MB: `yam.xml`, 17 STL meshes,
  MIT `LICENSE`) in `src/dreamguard/sim/assets/i2rt_yam/` with `SOURCE.md`; shipped as package data
  (verified in the built wheel).
- The scene is built programmatically with `MjSpec` (`sim/scene.py`) instead of a hand-written
  `scene_bimanual.xml`: the model is attached twice (`right_` / `left_`, bases at y = ∓0.30 m on a
  0.75 m table), plus a table, three free objects, an overhead camera behind/above the arms and a
  wrist camera on each `link_6` (roles `overhead`, `wrist_l`, `wrist_r`). Camera views were checked
  visually.
- `SimRobot` (`sim/robot.py`): Dream-1 `observation(prompt)` (`state.*` float32) and `frames()`
  (`video.*` base64 JPEG); `play()` executes the first `execution_horizon` (30) rows at
  `action_hz` (20 Hz, 25 physics substeps of 2 ms), optional real-time pacing, `interrupt()`,
  `hold()`. Physics/rendering are lock-protected; renderers are per thread. Starts at the
  Menagerie home pose (0, 1.047, 1.047, 0, 0, 0) with grippers open.
- Gripper: command 0..1 → finger actuator 0..0.041 m; reading is the finger position over its
  0.0375 m travel, clipped to 0..1.
- `SimKinematics` (`sim/kinematics.py`): `grasp_site` world position with its own `MjData`
  (never disturbs a running simulation).
- `yam_sim` profile now enforces the workspace (table area, x −0.15..0.85 m, y −0.75..0.75 m,
  z 0.76..1.6 m, i.e. 1 cm above the table) and 0.10 m gripper separation, with
  `require_workspace_check: true` (blocks everything without forward kinematics, fail closed).
- `sources/fake.py`: `FakeDreamClient` mirrors the SDK inference surface, generates 50-row chunks
  from the measured state toward scripted waypoints at 1 rad/s, and injects 9 one-shot faults.
  `sources/replay.py`: `ReplayDreamClient` replays session/fixture JSONL files.
  `sim/loop.py`: `run_loop()`; `sim/demo.py`: `python -m dreamguard.sim.demo`.
- Verified: scripted runs are approved with zero false rejections; each of the 9 faults is blocked
  by exactly its intended check and never reaches the robot.
- Defect found and fixed in Phase 3 code: the JSONL recorder dropped events whose actions contained
  NaN/Infinity (strict JSON), so the NaN fault was blocked but not logged. Non-finite values are
  now recorded as `"NaN"` / `"Infinity"` / `"-Infinity"` (regression test added).
- Demo output caps findings at 5 per action (long violations produce one finding per row).
- `MUJOCO_LOG.TXT` (MuJoCo warning log) added to `.gitignore`.
- Tests: 161 core/sim + 4 backend = 165 passing; ruff clean; backend pylint 9.74.

### Phase 5 — Backend API (free)

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Health: simulator, SDK, paid-call status |
| POST | `/api/runs` | Start run (`fake` / `replay` / `dream1`, scenario, prompt) |
| POST | `/api/runs/{id}/stop` | Stop run |
| POST | `/api/runs/{id}/faults` | Inject a catalogued fault |
| GET | `/api/runs/current` | Status and counters |
| GET | `/api/sessions`, `/api/sessions/{id}` | Session list / replay data (path-confined) |
| GET | `/api/safety/profile` | Active limits |
| POST | `/api/safety/inspect` | Validate any posted action |
| GET | `/api/safety/metrics` | PRD §13 metrics |
| WS | `/ws/events` | Live safety decisions |
| GET | `/api/stream/camera/{name}` | MJPEG camera stream |

- [ ] Each route follows the backend conventions (config-driven, rate-limited, model split, service layer)
- [ ] Backend tests with FastAPI TestClient

### Phase 6 — Dashboard (free)

- [ ] Vite + React + TypeScript scaffold in `frontend/`
- [ ] Types generated from the backend OpenAPI schema
- [ ] TanStack Query, typed WebSocket hook, Recharts, Tailwind (versions ≥ 7 days old)
- [ ] Live page: camera, run controls, fault buttons, decision feed, risk chart, joint-limit bars, metrics
- [ ] Sessions page: list + step-through replay
- [ ] Profile page: read-only limits
- [ ] Vite dev proxy; production build served by FastAPI
- [ ] Vitest component tests

### Phase 7 — Real Dream-1 runs (PAID — each attempt requires approval)

- [ ] Free preflight (`policy` + `set_observation`, no `get_action`)
- [ ] Attempt 1: single `get_action`, recorded; verify joint conventions, adjust profile
- [ ] Attempt 2: short run (~10 chunks), recorded; measure false rejections, tune limits
- [ ] Attempt 3: final demo recording
- Fallback if credits are unavailable: demo on `fake` + `replay` sources

### Phase 8 — Documentation and submission

- [ ] README (core, backend, frontend, safety limitations)
- [ ] Architecture diagram
- [ ] Update PRD setup section (clone instead of ZIP)
- [ ] Demo video / screenshots
