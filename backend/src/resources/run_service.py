"""
#############################################################################
### Run service file
###
### @file run_service.py
### @author Sebastian Russo
### @date 2026
#############################################################################

This module owns the simulator, the safety guard and the active run. A run
executes the Dream-1 control loop (observe -> get_action -> guarded play) on a
worker thread; every decision is recorded to a JSONL session file and
broadcast to WebSocket clients. Only one run is active at a time.

Paid Dream-1 inference is refused unless both config_file.json
(dream.allow_paid_calls) and the environment (DREAMGUARD_ALLOW_PAID=1) allow it.
"""

#Native imports
import os
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

#Third-party imports
from dreamguard import SafetyGuard, load_builtin_profile
from dreamguard.adapter import ControllerHaltedError, GuardedController
from dreamguard.events import EventBus, JsonlSessionRecorder, SafetyEvent, new_session_id
from dreamguard.metrics import summarize_events
from dreamguard.sim import SimKinematics, SimRobot, build_model
from dreamguard.sources import FAULTS, FakeDreamClient, ReplayDreamClient, ReplayExhaustedError
from dreamguard.sources.dream1 import Dream1Source, PaidCallBudgetExhausted, policy_config

#Other files imports
from src.core_specs.configuration.config_loader import config_loader, resolve_backend_path
from src.resources.camera_service import CameraService
from src.resources.event_broadcaster import broadcaster
from src.resources.service_errors import (
    ConflictError,
    NotAvailableError,
    NotFoundError,
    PaidCallsDisabledError,
    ServiceError,
)
from src.resources.session_service import session_path, sessions_dir
from src.utils.custom_logger import log_handler

"""VARIABLES-----------------------------------------------------------"""
ACTIVE_STATES = ("running", "halted")
SOURCES = ("fake", "replay", "dream1")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def paid_calls_allowed() -> bool:
    """Paid Dream-1 calls need both the config switch and the environment variable."""
    dream_cfg = config_loader["dream"]
    return bool(dream_cfg["allow_paid_calls"]) and (
        os.getenv(dream_cfg["allow_paid_calls_env"], "0").strip() == "1"
    )


"""CLASS-----------------------------------------------------------"""
class RunManager:  # pylint: disable=too-many-instance-attributes
    """Simulator, guard and the single active run."""

    def __init__(self) -> None:
        sim_cfg = config_loader["simulation"]
        safety_cfg = config_loader["safety"]
        self.profile_name = safety_cfg["profile"]
        self.profile = load_builtin_profile(self.profile_name)
        self.model = build_model()
        self.robot = SimRobot(
            self.model,
            action_hz=self.profile.action_hz,
            execution_horizon=sim_cfg["execution_horizon"],
            realtime=sim_cfg["realtime"],
        )
        self.guard = SafetyGuard(self.profile, forward_kinematics=SimKinematics(self.model))
        self.camera = CameraService(
            self.robot, sim_cfg["camera_fps"], sim_cfg["camera_jpeg_quality"]
        )
        self.max_chunks = sim_cfg["max_chunks_per_run"]
        self.max_consecutive_blocks = safety_cfg["max_consecutive_blocks"]

        self.bus = EventBus()
        self.recorder = JsonlSessionRecorder(sessions_dir())
        self.bus.subscribe(self.recorder)
        self.bus.subscribe(self._on_event)

        self._lock = threading.RLock()
        self._resume = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client: Any = None
        self._controller: Optional[GuardedController] = None
        self._events: list[dict[str, Any]] = []
        self._status: dict[str, Any] = self._idle_status()

    # --- Lifecycle -------------------------------------------------------------------------

    def startup(self) -> None:
        self.camera.start()

    def shutdown(self) -> None:
        run_id = self._status.get("run_id")
        if run_id and self._status["state"] in ACTIVE_STATES:
            self.stop_run(run_id)
        self.camera.stop()
        self.robot.close()

    # --- Status ----------------------------------------------------------------------------

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return {
            "run_id": None, "state": "idle", "source": None, "prompt": "",
            "chunks": 0, "rows_played": 0, "consecutive_blocks": 0, "paid_calls": 0,
            "started_at": None, "finished_at": None, "error": None,
            "replay_session_id": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            status = dict(self._status)
            status["rows_played"] = self.robot.rows_played if status["run_id"] else 0
            if self._controller is not None:
                status["consecutive_blocks"] = self._controller.consecutive_blocks
            return status

    def _update(self, **changes: Any) -> None:
        with self._lock:
            self._status.update(changes)
        broadcaster.publish({"type": "run", "run": self.status()})

    def _on_event(self, event: SafetyEvent) -> None:
        data = event.as_dict()
        with self._lock:
            if data["session_id"] == self._status.get("run_id"):
                self._events.append(data)
                self._status["chunks"] = len(self._events)
        broadcaster.publish({"type": "event", "event": data})
        broadcaster.publish({"type": "run", "run": self.status()})

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
            run_id = self._status.get("run_id")
        return {"run_id": run_id, "summary": summarize_events(events)}

    # --- Runs ------------------------------------------------------------------------------

    def _make_client(self, source: str, replay_session_id: Optional[str], run_id: str) -> Any:
        if source == "fake":
            client = FakeDreamClient(action_hz=self.profile.action_hz)
        elif source == "replay":
            if not replay_session_id:
                raise ServiceError("replay_session_id is required for the replay source")
            path = session_path(replay_session_id)
            if not path.is_file():
                raise NotFoundError(f"Session {replay_session_id} not found")
            try:
                client = ReplayDreamClient.from_file(path)
            except ValueError as exc:
                raise ServiceError(str(exc)) from exc
        elif source == "dream1":
            if not paid_calls_allowed():
                raise PaidCallsDisabledError(
                    "Paid Dream-1 calls are disabled. They require dream.allow_paid_calls=true in "
                    "config_file.json and DREAMGUARD_ALLOW_PAID=1 in .env, approved per run."
                )
            return self._make_dream1_client(run_id)
        else:
            raise ServiceError(f"Unknown source {source!r}; expected one of {', '.join(SOURCES)}")
        if source != "dream1":
            client.policy({"checkpoint": f"dreamguard-{source}"})
        return client

    def _make_dream1_client(self, run_id: str) -> Dream1Source:
        """Live Dream-1 client with a hard paid-call budget; replies are recorded under the run id.

        The policy is opened on the run thread (``_open_policy``): it can take tens of seconds.
        """
        dream_cfg = config_loader["dream"]
        budget = dream_cfg["max_paid_calls_per_run"]
        if not isinstance(budget, int) or budget < 1:
            raise PaidCallsDisabledError(
                "dream.max_paid_calls_per_run must be at least 1 to allow a paid run"
            )
        return Dream1Source(
            max_calls=budget,
            session_id=run_id,
            fixtures_dir=resolve_backend_path(dream_cfg["fixtures_dir"]),
            config=policy_config(
                checkpoint=dream_cfg["checkpoint"],
                timeout_ms=dream_cfg["timeout_ms"],
                action_hz=self.profile.action_hz,
                execution_horizon=self.robot.execution_horizon,
            ),
        )

    @staticmethod
    def _open_policy(client: Any) -> None:
        """Open a live policy: one GET /v1/models request (model listing), no inference."""
        if isinstance(client, Dream1Source):
            try:
                client.policy()
            except Exception as exc:
                raise ServiceError(f"Dream-1 policy could not be opened: {exc}") from exc

    def start_run(
        self,
        source: str,
        prompt: str = "",
        max_chunks: Optional[int] = None,
        replay_session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._status["state"] in ACTIVE_STATES:
                raise ConflictError(f"Run {self._status['run_id']} is still active; stop it first")
            run_id = new_session_id()
            client = self._make_client(source, replay_session_id, run_id)
            self.robot.reset()
            self._client = client
            self._controller = GuardedController(
                self.robot, self.guard, bus=self.bus, session_id=run_id, source=source,
                max_consecutive_blocks=self.max_consecutive_blocks,
            )
            self._events = []
            self._stop.clear()
            limit = min(max_chunks or self.max_chunks, self.max_chunks)
            self._status = {
                **self._idle_status(), "run_id": run_id, "state": "running", "source": source,
                "prompt": prompt, "started_at": _now(), "replay_session_id": replay_session_id,
            }
            self._thread = threading.Thread(
                target=self._run_loop, args=(run_id, client, prompt, limit),
                name=f"run-{run_id}", daemon=True,
            )
            self._thread.start()
        log_handler.info(f"Run {run_id} started (source={source})")
        broadcaster.publish({"type": "run", "run": self.status()})
        return self.status()

    def _run_loop(self, run_id: str, client: Any, prompt: str, limit: int) -> None:
        controller = self._controller
        #Offline sources ignore camera frames, so rendering is skipped for them
        needs_frames = not isinstance(client, (FakeDreamClient, ReplayDreamClient))
        final_state, error = "completed", None
        try:
            self._open_policy(client)
            for _ in range(limit):
                if self._stop.is_set():
                    final_state = "stopped"
                    break
                observation = self.robot.observation(prompt)
                client.set_observation(self.robot.frames() if needs_frames else {}, observation)
                try:
                    action = client.get_action()
                except (ReplayExhaustedError, PaidCallBudgetExhausted):
                    break
                finally:
                    if isinstance(client, Dream1Source):
                        self._update(paid_calls=client.calls)
                faults = list(getattr(client, "last_faults", ()))
                metadata = {"injected_faults": faults} if faults else None
                try:
                    controller.submit(action, observation=observation, metadata=metadata)
                except ControllerHaltedError:
                    pass
                if controller.halted and not self._wait_for_reset(run_id):
                    final_state = "stopped"
                    break
        except Exception as exc:  # pylint: disable=broad-exception-caught
            final_state, error = "error", f"{type(exc).__name__}: {exc}"
            log_handler.error(f"Run {run_id} failed: {error}")
        finally:
            self.robot.close_thread_renderer()
            client.close()
        self._update(state=final_state, finished_at=_now(), error=error)
        log_handler.info(f"Run {run_id} finished ({final_state})")

    def _wait_for_reset(self, run_id: str) -> bool:
        """Pause while halted; True when an operator reset, False when the run was stopped."""
        self._update(state="halted")
        log_handler.warning(f"Run {run_id} halted after repeated blocked actions")
        with self._resume:
            while self._controller is not None and self._controller.halted:
                if self._stop.is_set():
                    return False
                self._resume.wait(timeout=0.2)
        return not self._stop.is_set()

    def _require_run(self, run_id: str) -> None:
        if self._status.get("run_id") != run_id:
            raise NotFoundError(f"Run {run_id} is not the current run")

    def stop_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            self._require_run(run_id)
            thread = self._thread
            self._stop.set()
            self.robot.interrupt()
            self._resume.notify_all()
        if thread is not None:
            thread.join(timeout=15)
        self.robot.clear_interrupt()
        return self.status()

    def reset_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            self._require_run(run_id)
            if self._status["state"] != "halted" or self._controller is None:
                raise ConflictError(f"Run {run_id} is not halted")
            self._controller.reset()
            self._status["state"] = "running"
            self._resume.notify_all()
        broadcaster.publish({"type": "run", "run": self.status()})
        return self.status()

    def inject_fault(self, run_id: str, fault: str) -> dict[str, Any]:
        with self._lock:
            self._require_run(run_id)
            if self._status["state"] != "running":
                raise ConflictError(f"Run {run_id} is not running")
            if not isinstance(self._client, FakeDreamClient):
                raise ConflictError("Faults can only be injected into the scripted (fake) source")
            if fault not in FAULTS:
                raise ServiceError(f"Unknown fault {fault!r}; expected one of {', '.join(FAULTS)}")
            self._client.inject(fault)
        return {"run_id": run_id, "fault": fault, "description": FAULTS[fault]}

    # --- Safety ----------------------------------------------------------------------------

    def inspect(
        self, action: Any, current_joints: Optional[Mapping[str, Any]] = None
    ) -> dict[str, Any]:
        """Evaluate an action against the active profile without executing it."""
        return self.guard.inspect(action, current_joints=current_joints).as_dict()

    def profile_info(self) -> dict[str, Any]:
        config = asdict(self.profile)
        config["joint_limits"] = {arm: [list(p) for p in limits]
                                  for arm, limits in self.profile.joint_limits.items()}
        return {
            "name": self.profile_name,
            "forward_kinematics": True,
            "max_consecutive_blocks": self.max_consecutive_blocks,
            "config": config,
        }


"""VARIABLES-----------------------------------------------------------"""
_manager: Optional[RunManager] = None  # pylint: disable=invalid-name


"""METHODS-----------------------------------------------------------"""
def startup() -> RunManager:
    """Create and start the run manager (called from the application lifespan)."""
    global _manager  # pylint: disable=global-statement
    if _manager is None:
        _manager = RunManager()
        _manager.startup()
    return _manager


def shutdown() -> None:
    global _manager  # pylint: disable=global-statement
    if _manager is not None:
        _manager.shutdown()
        _manager = None


def get_manager() -> RunManager:
    if _manager is None:
        raise NotAvailableError("The simulator is not running")
    return _manager
