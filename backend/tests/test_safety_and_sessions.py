from conftest import wait_for

HOME = (0.0, 1.047, 1.047, 0.0, 0.0, 0.0)
CURRENT = {"right": list(HOME), "left": list(HOME)}


def row(joints=HOME, gripper=0.5):
    return list(joints) + [gripper]


# --- Profile and inspection ---------------------------------------------------------------


def test_profile_is_the_yam_sim_profile(client):
    profile = client.get("/api/safety/profile").json()
    assert profile["name"] == "yam_sim"
    assert profile["forward_kinematics"] is True
    assert profile["config"]["joint_limits"]["right"][1] == [0.0, 3.66519]
    assert profile["config"]["require_workspace_check"] is True


def test_inspect_approves_a_safe_action(client):
    body = {"action": {"q_r_chunk": [row()], "q_l_chunk": [row()]}, "current_joints": CURRENT}
    report = client.post("/api/safety/inspect", json=body).json()
    assert report["decision"] == "APPROVE"
    assert report["findings"] == []


def test_inspect_explains_a_blocked_action(client):
    body = {"action": {"q_r_chunk": [row(gripper=1.5)], "q_l_chunk": [row()]},
            "current_joints": CURRENT}
    report = client.post("/api/safety/inspect", json=body).json()
    assert report["decision"] == "BLOCK"
    assert report["findings"][0]["check"] == "gripper"
    assert report["risk_score"] >= 70


def test_inspect_blocks_malformed_actions_instead_of_422(client):
    report = client.post("/api/safety/inspect", json={"action": "not an action"}).json()
    assert report["decision"] == "BLOCK"
    assert report["findings"][0]["check"] == "action_format"


def test_inspect_does_not_execute(client):
    body = {"action": {"q_r_chunk": [row()], "q_l_chunk": [row()]}, "current_joints": CURRENT}
    client.post("/api/safety/inspect", json=body)
    assert client.get("/api/runs/current").json()["rows_played"] == 0


# --- Sessions ----------------------------------------------------------------------------


def run_scripted(client, chunks=3, fault=None):
    body = {"source": "fake", "max_chunks": chunks}
    run_id = client.post("/api/runs", json=body).json()["run_id"]
    if fault:
        client.post(f"/api/runs/{run_id}/faults", json={"fault": fault})
    wait_for(lambda: client.get("/api/runs/current").json()["state"] == "completed")
    return run_id


def test_sessions_are_listed_with_summaries(client):
    run_id = run_scripted(client)
    sessions = client.get("/api/sessions").json()
    assert sessions[0]["session_id"] == run_id
    assert sessions[0]["summary"]["actions_evaluated"] == 3


def test_session_events_are_paged(client):
    run_id = run_scripted(client, chunks=4)
    page = client.get(f"/api/sessions/{run_id}", params={"offset": 1, "limit": 2}).json()
    assert page["total"] == 4
    assert [e["sequence"] for e in page["events"]] == [2, 3]
    assert page["events"][0]["report"]["decision"] == "APPROVE"
    assert page["summary"]["actions_evaluated"] == 4


def test_recorded_fault_keeps_its_metadata(client):
    run_id = run_scripted(client, chunks=3, fault="gripper")
    events = client.get(f"/api/sessions/{run_id}").json()["events"]
    faulted = [e for e in events if e["metadata"].get("injected_faults")]
    assert faulted
    assert faulted[0]["metadata"]["injected_faults"] == ["gripper"]
    assert faulted[0]["executed"] is False


def test_unknown_or_unsafe_session_ids(client):
    assert client.get("/api/sessions/missing-session").status_code == 404
    assert client.get("/api/sessions/bad.id").status_code == 400
    assert client.get("/api/sessions/..%2F..%2Fmain").status_code in (400, 404)


def test_session_list_is_empty_without_recordings(client):
    assert client.get("/api/sessions").json() == []
