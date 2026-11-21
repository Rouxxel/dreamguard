# DreamGuard

A first-stage, fail-closed safety middleware for Dream-1 action chunks.

## What this starter checks

For each `q_r_chunk` and `q_l_chunk` action returned by Dream-1, it checks:

- required action chunks exist;
- each chunk is a non-empty sequence of rows;
- each row contains six joint targets plus one gripper target;
- all values are finite numbers;
- configured joint position limits are respected;
- configured per-row joint step limits are respected;
- gripper targets remain in `[0, 1]`;
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

Use the adapter after `get_action()` and before any simulator/controller `play()` call:

```python
from dreamguard.adapter import guarded_get_action
from dreamguard.guard import SafetyConfig, SafetyGuard

guard = SafetyGuard(SafetyConfig())

# In your simulator's control loop, after the first set_observation:
action = guarded_get_action(client, guard)
robot.play(action)  # only the approved action reaches the controller
```

Do not call `robot.play(client.get_action())` directly once DreamGuard is in the loop.

The exact camera, observation and simulator objects depend on the Playground robot configuration. Do not guess these fields: copy the actual observation mapping and robot loop from the Playground's current integration example. The `integrations/dream_client_loop_skeleton.py` file shows where the guard belongs without inventing camera or robot APIs.

## Configure real limits before connecting a simulator

Edit `SafetyConfig` in `src/dreamguard/guard.py` using the simulator's documented joint ranges and measured action rate. The default joint limits of `[-pi, pi]` are placeholders and may not match your robot.

For workspace / separation checks, supply a tested forward-kinematics function returning each end-effector position in metres. Set `require_workspace_check=True` if the workspace must be enforced; the guard then fails closed if no FK callback is supplied.

## Team workflow

Suggested branches:
- `feature/safety-core`: guard + tests
- `feature/dream-client`: DreamClient observation/inference loop
- `feature/dashboard`: UI and event stream

Keep API keys in local environment variables / secret storage, never in Git.
