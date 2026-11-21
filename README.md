# DreamGuard

A first-stage, fail-closed safety middleware for Dream-1 action chunks.

## What this starter checks

For each `q_r_chunk` and `q_l_chunk` action returned by Dream-1, it checks:

- required action chunks exist;
- each chunk is a non-empty sequence of rows;
- each row contains six joint targets plus one gripper target;
- both arm chunks have the same number of rows, within the configured `min_rows` / `max_rows`;
- the measured joint state is present and valid, and the first row is step-checked against it;
- all values are finite numbers;
- configured joint position limits are respected;
- configured per-row joint step limits are respected;
- optional per-joint velocity limits (rad/s at the configured `action_hz`) are respected;
- gripper targets remain in the configured range (default `[0, 1]`);
- targets close to a joint limit raise a non-blocking near-limit warning;
- optional forward-kinematics workspace and end-effector separation checks are applied when you provide robot-specific kinematics.

**Important limitations:** the starter does not know your simulator's calibrated joint limits, link geometry, collision meshes, or emergency-stop interface. Defaults are development guardrails, not certified safety limits. The optional distance check only compares end-effector points, not full robot links. Do not connect this starter directly to physical hardware.

## Windows setup (PowerShell)

Install Python 3.11 or 3.12 and Git. Then:

```powershell
git clone https://github.com/YOUR-TEAM/dreamguard.git
cd dreamguard

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Copy-Item .env.example .env
notepad .env
```

Put your Dream Labs key in `.env` locally. Do not commit it. The code below reads `DREAM_API_KEY` from the process environment; to load `.env` automatically, install `python-dotenv` or set the variable in PowerShell:

```powershell
$env:DREAM_API_KEY = "dl_live_your_real_key"
```

The official Dream Labs Python client package is `dreamlabs-client`, imported as `dream`. It is deliberately installed separately from the full `dreamlabs` station package: the client is enough for a custom control loop, while the full station package brings hardware-oriented dependencies.

## Run the local middleware demo first

```powershell
python -m dreamguard.demo
pytest -q
```

Expected result: the safe sample is approved and the deliberately unsafe sample is blocked.

## Check the SDK installation and credentials

```powershell
python scripts/check_dream_sdk.py
```

This only imports the SDK, checks that the key is present, constructs the client, and closes it. It does not send an inference request or move a robot.

## Dream-1 integration pattern

Dream Labs documents the custom-loop sequence as `DreamClient.policy(config)`, `set_observation(frames, observation)` on camera ticks, then `get_action()` to receive an action chunk. Dream-1 YAM chunks use `q_r_chunk` and `q_l_chunk`, with six arm joints and a gripper value in each row.

Hand every action to a `GuardedController`. It is the only object that calls `robot.play()`:

```python
from dreamguard import SafetyGuard, load_builtin_profile
from dreamguard.adapter import GuardedController
from dreamguard.events import EventBus, JsonlSessionRecorder

bus = EventBus()
bus.subscribe(JsonlSessionRecorder("logs/sessions"))  # one JSON line per decision
controller = GuardedController(robot, SafetyGuard(load_builtin_profile("yam_sim")), bus=bus)

# In your control loop, after the first set_observation:
report = controller.submit(client.get_action(), observation=observation)
```

- **APPROVE**: a copy of the validated action is played.
- **BLOCK**: nothing is played, so the robot keeps its last approved targets; the optional
  `on_block` hook runs. After `max_consecutive_blocks` (default 3) blocks in a row the controller
  halts and raises `ControllerHaltedError` until `reset()` is called.
- Every decision is published as a `SafetyEvent` (decision, findings, risk, latency, action,
  measured state, executed/halted flags). Subscribers that fail never affect supervision.
- `read_session(path)` and `list_sessions(directory)` read recorded sessions back.

The measured joint state is taken from `observation["state.right_arm"]` /
`observation["state.left_arm"]` (or pass `current_joints=` explicitly). It is mandatory by
default (`SafetyConfig.require_current_state=True`): the first row of every chunk is step-checked
against it, and the action is blocked when it is missing or invalid.

For a single chunk without a controller, `guarded_get_action(client, guard, observation)` returns
the approved action or raises `UnsafeActionError`.

Do not call `robot.play(client.get_action())` directly once DreamGuard is in the loop.

The exact camera, observation and simulator objects depend on the Playground robot configuration. Do not guess these fields: copy the actual observation mapping and robot loop from the Playground's current integration example. The `integrations/dream_client_loop_skeleton.py` file shows where the guard belongs without inventing camera or robot APIs.

## Offline MuJoCo simulator

DreamGuard ships a local bimanual YAM simulator (two MuJoCo Menagerie i2rt YAM arms on a table,
overhead + two wrist cameras) so the whole loop runs without a robot, a network connection or Dream
credits:

```powershell
python -m pip install -e ".[sim]"
python -m dreamguard.sim.demo     # scripted motion, then every fault; all decisions logged
```

| Component | Purpose |
|---|---|
| `dreamguard.sim.SimRobot` | Robot API: `joints(arm)`, `gripper(arm)`, `observation(prompt)`, `frames()` (base64 JPEG, 320x176, quality 85), `play(action)` at `action_hz` (first `execution_horizon` rows), `interrupt()` |
| `dreamguard.sim.SimKinematics` | Forward kinematics of each `grasp_site` in the world frame, for workspace and separation checks |
| `dreamguard.sources.FakeDreamClient` | Offline stand-in for `dream.DreamClient` with scripted chunks and `inject(fault)` |
| `dreamguard.sources.ReplayDreamClient` | Replays a recorded session or fixture file through the same interface |
| `dreamguard.sim.run_loop` | Observe -> `get_action()` -> `GuardedController.submit()` loop |

Injectable faults (each blocked by exactly one check): `joint_limit`, `big_step`, `velocity`,
`nan`, `gripper`, `missing_arm`, `mismatched_lengths`, `workspace`, `separation`.

The `yam_sim` profile requires forward kinematics (workspace and separation checks); construct the
guard with `SafetyGuard(load_builtin_profile("yam_sim"), forward_kinematics=SimKinematics())`.

## Backend API

`backend/` is a FastAPI service that runs the simulator with DreamGuard in the loop and serves the
dashboard: runs (scripted, replay; live Dream-1 only when paid calls are explicitly enabled), fault
injection, recorded sessions, the safety profile, action inspection, metrics, a live event
WebSocket and MJPEG camera streams. See [backend/README.md](backend/README.md).

```powershell
python -m pip install -e ".[sim]" -r backend/requirements.txt
cd backend
python main.py        # http://127.0.0.1:8000/docs
```

## Dashboard

`frontend/` is a React + Vite + TypeScript dashboard: live cameras, run controls, fault injection,
metrics, risk chart, decision feed with explanations, joint targets vs limits, session replay and
the safety profile. See [frontend/README.md](frontend/README.md).

```powershell
cd frontend
npm install
npm run dev     # http://localhost:5173 with the backend running
npm run build   # then open http://127.0.0.1:8000/dashboard/ (served by the backend)
```

## Configure real limits before connecting a simulator

Safety limits are a `SafetyConfig`. The defaults (joint limits of `[-pi, pi]`) are placeholders.
Use a JSON safety profile instead:

```python
from dreamguard import SafetyGuard, load_builtin_profile, load_profile

guard = SafetyGuard(load_builtin_profile("yam_sim"))   # src/dreamguard/profiles/yam_sim.json
guard = SafetyGuard(load_profile("my_robot.json"))     # your own profile
```

`yam_sim` carries the joint ranges of the i2rt YAM model from MuJoCo Menagerie. Its step and
velocity limits are development guardrails to be tuned against recorded Dream-1 chunks. Profile
keys are the `SafetyConfig` field names (plus optional `name`, `description`, `source`, `notes`);
unknown keys and invalid values (non-finite, inverted ranges, wrong lengths) are rejected when the
configuration is built, so a guard never runs with an unusable configuration.

For workspace / separation checks, supply a tested forward-kinematics function returning each
end-effector position in metres. Set `require_workspace_check=True` if the workspace must be
enforced; the guard then fails closed if no FK callback is supplied.

## Safety reports

`SafetyGuard.inspect()` returns a `SafetyReport`:

- `decision`: `Decision.APPROVE` or `Decision.BLOCK` (`MODIFY` is reserved; corrections are not
  enabled yet);
- `findings`: structured `Finding` objects (`check`, `severity`, `message`, `arm`, `row`, `joint`,
  `value`, `limit`). `violation` findings block; `warning` findings (near-limit) do not;
- `risk_score`: a developer-facing heuristic in `[0, 100]`, not a probability of harm. Blocked
  actions score the weight of their most serious check plus 2 per extra violation (at least 70);
  approved actions score their strongest near-limit warning (at most 50);
- `latency_ms`: validation time; `as_dict()` gives a JSON-serializable form.

`SafetyGuard.approve()` returns the validated action or raises `UnsafeActionError`.

## Team workflow

Suggested branches:
- `feature/safety-core`: guard + tests
- `feature/dream-client`: DreamClient observation/inference loop
- `feature/dashboard`: UI and event stream

Keep API keys in local environment variables / secret storage, never in Git.
