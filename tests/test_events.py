import json

import numpy as np
import pytest

from dreamguard import SafetyGuard
from dreamguard.adapter import GuardedController
from dreamguard.events import (
    EventBus,
    JsonlSessionRecorder,
    SafetyEvent,
    list_sessions,
    new_session_id,
    read_session,
    validate_session_id,
)

HOME = [0.0] * 6


class NullRobot:
    def play(self, action):
        pass


def numpy_action(gripper=0.5):
    chunk = np.zeros((2, 7), dtype=np.float32)
    chunk[:, 6] = gripper
    return {"q_r_chunk": chunk, "q_l_chunk": chunk.copy(), "per_key": {"ignored": True}}


def test_new_session_ids_are_valid_and_unique():
    first, second = new_session_id(), new_session_id()
    assert validate_session_id(first) == first
    assert first != second


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "a\\b", "x" * 65, "name.jsonl", None])
def test_unsafe_session_ids_are_rejected(bad):
    with pytest.raises(ValueError):
        validate_session_id(bad)


def test_event_as_dict_is_json_with_numpy_inputs():
    report = SafetyGuard().inspect(numpy_action(), current_joints={"right": HOME, "left": HOME})
    event = SafetyEvent(
        session_id="s1",
        sequence=1,
        report=report,
        executed=True,
        action=numpy_action(),
        current_joints={"right": np.zeros(6, dtype=np.float32), "left": HOME},
    )
    data = json.loads(json.dumps(event.as_dict()))
    assert data["report"]["decision"] == "APPROVE"
    assert data["action"]["q_r_chunk"][0][6] == 0.5
    assert "per_key" not in data["action"]
    assert data["current_joints"]["right"] == [0.0] * 6


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []
    unsubscribe = bus.subscribe(received.append)
    unsubscribe()
    unsubscribe()  # idempotent
    report = SafetyGuard().inspect(numpy_action(), current_joints={"right": HOME, "left": HOME})
    bus.publish(SafetyEvent("s1", 1, report, executed=True))
    assert received == []


def test_controller_session_is_recorded_to_jsonl_and_read_back(tmp_path):
    bus = EventBus()
    recorder = JsonlSessionRecorder(tmp_path / "sessions")
    bus.subscribe(recorder)
    controller = GuardedController(NullRobot(), SafetyGuard(), bus=bus, session_id="run-1")
    current = {"right": HOME, "left": HOME}
    controller.submit(numpy_action(), current_joints=current)
    controller.submit(numpy_action(gripper=2.0), current_joints=current)

    events = read_session(recorder.path_for("run-1"))
    assert [e["sequence"] for e in events] == [1, 2]
    assert [e["report"]["decision"] for e in events] == ["APPROVE", "BLOCK"]
    assert events[1]["report"]["findings"][0]["check"] == "gripper"
    assert list_sessions(tmp_path / "sessions") == ["run-1"]


def test_recorder_rejects_unsafe_session_id(tmp_path):
    with pytest.raises(ValueError):
        JsonlSessionRecorder(tmp_path).path_for("../outside")


def test_read_session_reports_malformed_line(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"sequence": 1}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match=":2:"):
        read_session(path)


def test_list_sessions_of_missing_directory_is_empty(tmp_path):
    assert list_sessions(tmp_path / "missing") == []
