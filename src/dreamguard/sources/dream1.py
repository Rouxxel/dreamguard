"""Live Dream-1 source: ``dream.DreamClient`` behind a hard budget of paid calls.

Network use of the SDK (verified by blocking sockets, dreamlabs-client 1.1.7):

- ``DreamClient()`` and ``set_observation()`` are local.
- ``policy()`` makes one ``GET /v1/models`` request (the account's model listing, not inference)
  because the YAM config needs ``ik``; the embodiment is passed explicitly, so no other lookup runs.
- ``get_action()`` is the paid inference call.
- ``_record: False`` is always set: by default the SDK streams every camera tick (state and JPEG
  frames) to Dream Labs' live service; these episodes are simulated, as in the SDK's own MuJoCo
  example, so nothing is recorded.

Every reply is appended to a JSON-lines fixture file (action, measured state, timing), so each
paid call can be replayed for free with ``ReplayDreamClient.from_file``.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from ..events import json_safe, new_session_id, validate_session_id

CHECKPOINT = "dreamlabs/dream-1-beta"
_YAM_SPANS = {
    "right_arm": [0, 6], "right_gripper": [6, 7], "left_arm": [7, 13], "left_gripper": [13, 14]
}
YAM_EMBODIMENT = {
    "state": dict(_YAM_SPANS),
    "action": dict(_YAM_SPANS),
    "video": {role: f"observation.images.{role}" for role in ("overhead", "wrist_l", "wrist_r")},
}


class PaidCallBudgetExhausted(RuntimeError):
    """The run already made every paid call it was allowed; nothing was sent."""


def policy_config(
    *,
    checkpoint: str = CHECKPOINT,
    timeout_ms: int = 15000,
    action_hz: float = 20.0,
    execution_horizon: int = 30,
) -> dict[str, Any]:
    """The YAM station config for ``dreamlabs/dream-1-beta``, with recording off."""
    return {
        "checkpoint": checkpoint,
        "timeout_ms": timeout_ms,
        "strict": True,
        "ik": {"arm": "yam", "head": "joint"},
        "embodiment": json.loads(json.dumps(YAM_EMBODIMENT)),
        "action_hz": action_hz,
        "execution_horizon": execution_horizon,
        "_record": False,
    }


def _default_client_factory() -> Any:
    import dream  # optional dependency: only imported when a live source is created

    return dream.DreamClient(api_key=os.getenv("DREAM_API_KEY") or None)


# Module-level so tests can replace the SDK client with a fake (never the network).
CLIENT_FACTORY: Callable[[], Any] = _default_client_factory


class Dream1Source:
    """Dream-1 client interface (``policy``, ``set_observation``, ``get_action``, ``close``).

    ``max_calls`` is a hard cap: once that many ``get_action()`` calls were attempted (sent,
    refused or failed), further calls raise ``PaidCallBudgetExhausted`` without contacting
    Dream Labs.
    """

    def __init__(
        self,
        *,
        max_calls: int,
        fixtures_dir: str | Path | None = None,
        session_id: str | None = None,
        config: Mapping[str, Any] | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls < 1:
            raise ValueError("max_calls must be an integer >= 1")
        self.max_calls = max_calls
        self.calls = 0
        self.config = dict(config or policy_config())
        if self.config.get("_record") is not False or "embodiment" not in self.config:
            raise ValueError("Live configs must set _record=False and carry the embodiment")
        self.session_id = validate_session_id(session_id or new_session_id())
        self.fixture_path = (
            Path(fixtures_dir) / f"{self.session_id}.jsonl" if fixtures_dir is not None else None
        )
        self._client_factory = client_factory or (lambda: CLIENT_FACTORY())
        self._client: Any = None
        self._observation: Mapping[str, Any] | None = None
        self._lock = threading.Lock()

    @property
    def remaining_calls(self) -> int:
        return self.max_calls - self.calls

    # --- Free: local SDK calls ---------------------------------------------------------------

    def policy(self, config: Mapping[str, Any] | None = None) -> None:
        """Open the policy. The argument is ignored: the safe, local config is always used."""
        if self._client is None:
            self._client = self._client_factory()
        self._client.policy(dict(self.config))

    def set_observation(
        self, frames: Mapping[str, str], observation: Mapping[str, Any], *, timestamp=None
    ) -> None:
        if self._client is None:
            raise RuntimeError("policy() must be called before set_observation()")
        self._client.set_observation(frames, observation, timestamp=timestamp)
        self._observation = observation

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- Paid ---------------------------------------------------------------------------

    def get_action(self, *, commanded: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """One paid inference call, counted against the budget before it is sent."""
        with self._lock:
            if self._client is None:
                raise RuntimeError("policy() must be called before get_action()")
            if self.calls >= self.max_calls:
                raise PaidCallBudgetExhausted(
                    f"Paid call budget of {self.max_calls} reached; no request was sent"
                )
            self.calls += 1
            sequence = self.calls
        error: str | None = None
        action: dict[str, Any] | None = None
        try:
            action = self._client.get_action(commanded=commanded)
            return action
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._record_reply(sequence, action, error)

    def _record_reply(self, sequence: int, action: Any, error: str | None) -> None:
        if self.fixture_path is None:
            return
        observation = self._observation or {}
        state = {key: value for key, value in observation.items() if key.startswith("state.")}
        line = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "session_id": self.session_id,
            "sequence": sequence,
            "checkpoint": self.config.get("checkpoint"),
            "prompt": (self._observation or {}).get("prompt"),
            "observation_state": json_safe(state),
            "timing": json_safe(getattr(self._client, "last_timing", None)),
            "error": error,
            "action": json_safe(action) if action is not None else None,
        }
        self.fixture_path.parent.mkdir(parents=True, exist_ok=True)
        with self.fixture_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(line, allow_nan=False) + "\n")


def check_inputs(robot: Any, prompt: str = "") -> dict[str, Any]:
    """Offline check of what a live run would send: frames, observation and config.

    Nothing touches the network or the SDK.
    """
    import base64
    import io

    import numpy as np
    from PIL import Image

    frames = robot.frames()
    observation = robot.observation(prompt)
    config = policy_config()
    problems: list[str] = []
    expected_frames = {f"video.{role}" for role in YAM_EMBODIMENT["video"]}
    if set(frames) != expected_frames:
        problems.append(f"frame keys {sorted(frames)} != {sorted(expected_frames)}")
    frame_info = {}
    for key, value in frames.items():
        image = Image.open(io.BytesIO(base64.b64decode(value)))
        frame_info[key] = {"format": image.format, "width": image.width, "height": image.height}
        if image.format != "JPEG" or image.size != (320, 176):
            problems.append(f"{key} is {image.format} {image.size}, expected JPEG (320, 176)")
    state_info = {}
    for part, (start_index, end_index) in YAM_EMBODIMENT["state"].items():
        value = observation.get(f"state.{part}")
        shape = list(np.shape(value)) if value is not None else None
        dtype = str(getattr(value, "dtype", type(value).__name__))
        state_info[f"state.{part}"] = {"shape": shape, "dtype": dtype}
        if shape != [end_index - start_index] or dtype != "float32":
            expected = end_index - start_index
            problems.append(f"state.{part} is {dtype} {shape}, expected float32 [{expected}]")
    if config["_record"] is not False:
        problems.append("recording to Dream Labs is not disabled")
    return {
        "ok": not problems,
        "problems": problems,
        "checkpoint": config["checkpoint"],
        "recording_to_dream_labs": config["_record"],
        "frames": frame_info,
        "state": state_info,
        "prompt": observation.get("prompt"),
    }


def preflight(
    robot: Any,
    *,
    prompt: str = "",
    allow_model_lookup: bool = False,
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Check the live loop without inference.

    Level 1 (default): ``check_inputs`` only, fully offline.
    Level 2 (``allow_model_lookup=True``): also opens the SDK policy, which sends one
    ``GET /v1/models`` request (confirms the key and that the checkpoint is available to the
    account), and hands the SDK one real camera tick. ``get_action()`` is never called.
    """
    result = check_inputs(robot, prompt)
    result["model_lookup"] = "skipped"
    if not allow_model_lookup or not result["ok"]:
        return result
    source = Dream1Source(max_calls=1, client_factory=client_factory)
    try:
        source.policy()
        source.set_observation(robot.frames(), robot.observation(prompt))
        result["model_lookup"] = "ok: checkpoint available to this key"
    finally:
        source.close()
    result["paid_calls_made"] = source.calls
    return result
