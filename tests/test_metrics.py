from dreamguard import SafetyGuard
from dreamguard.adapter import GuardedController
from dreamguard.events import EventBus
from dreamguard.metrics import summarize_events
from dreamguard.sources import FakeDreamClient

HOME = [0.0] * 6
SAFE = {"q_r_chunk": [HOME + [0.5]], "q_l_chunk": [HOME + [0.5]]}
UNSAFE = {"q_r_chunk": [HOME + [2.0]], "q_l_chunk": [HOME + [0.5]]}
CURRENT = {"right": HOME, "left": HOME}


class NullRobot:
    def play(self, action):
        pass


def record(submissions, source="fake"):
    bus = EventBus()
    events = []
    bus.subscribe(lambda e: events.append(e.as_dict()))
    controller = GuardedController(NullRobot(), SafetyGuard(), bus=bus, source=source,
                                   max_consecutive_blocks=99)
    for action, faults in submissions:
        controller.submit(action, current_joints=CURRENT,
                          metadata={"injected_faults": faults} if faults else None)
    return events


def test_metadata_is_attached_to_events():
    [event] = record([(UNSAFE, ["gripper"])])
    assert event["metadata"] == {"injected_faults": ["gripper"]}


def test_summary_counts_outcomes_and_false_rejections():
    events = record([(SAFE, None), (UNSAFE, ["gripper"]), (UNSAFE, None), (SAFE, ["nan"])])
    summary = summarize_events(events)
    assert summary["actions_evaluated"] == 4
    assert summary["approved"] == 2
    assert summary["blocked"] == 2
    assert summary["executed"] == 2
    assert summary["unsafe_injected"] == 2
    assert summary["unsafe_prevented"] == 1
    assert summary["unsafe_missed"] == 1  # the "nan" label on a safe action was executed
    assert summary["false_rejections"] == 1
    assert summary["violations_by_check"] == {"gripper": 2}
    assert summary["latency_ms"]["p50"] is not None
    assert summary["sources"] == ["fake"]


def test_false_rejections_only_counted_for_ground_truth_sources():
    summary = summarize_events(record([(UNSAFE, None)], source="replay"))
    assert summary["blocked"] == 1
    assert summary["false_rejections"] == 0


def test_empty_summary():
    summary = summarize_events([])
    assert summary["actions_evaluated"] == 0
    assert summary["latency_ms"] == {"p50": None, "p95": None, "max": None}


def test_fake_client_reports_faults_of_last_chunk():
    client = FakeDreamClient()
    client.policy({})
    client.set_observation({}, {"state.right_arm": [0.0, 1.047, 1.047, 0, 0, 0],
                                "state.left_arm": [0.0, 1.047, 1.047, 0, 0, 0]})
    client.inject("gripper")
    client.get_action()
    assert client.last_faults == ("gripper",)
    client.get_action()
    assert client.last_faults == ()


def test_fake_client_applies_queued_faults_one_per_chunk():
    client = FakeDreamClient()
    client.policy({})
    client.set_observation({}, {"state.right_arm": [0.0, 1.047, 1.047, 0, 0, 0],
                                "state.left_arm": [0.0, 1.047, 1.047, 0, 0, 0]})
    for fault in ("gripper", "nan", "workspace"):
        client.inject(fault)
    seen = []
    for _ in range(4):
        client.get_action()
        seen.append(client.last_faults)
    assert seen == [("gripper",), ("nan",), ("workspace",), ()]
