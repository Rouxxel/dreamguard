"""
Integration skeleton only.

Fill `frames` and `observation` from the current Dream-1 Playground example.
The simulator's robot object/API is intentionally not guessed here.
"""
import dream
from dotenv import load_dotenv

load_dotenv()

from dreamguard.adapter import guarded_get_action
from dreamguard.guard import SafetyConfig, SafetyGuard

POLICY_CONFIG = {
    "timeout_ms": 15000,
    "strict": True,
    "checkpoint": "dreamlabs/dream-1-beta",
    "ik": {"arm": "yam", "head": "joint"},
    "embodiment": {
        "state": {
            "right_arm": [0, 6],
            "right_gripper": [6, 7],
            "left_arm": [7, 13],
            "left_gripper": [13, 14],
        },
        "action": {
            "right_arm": [0, 6],
            "right_gripper": [6, 7],
            "left_arm": [7, 13],
            "left_gripper": [13, 14],
        },
        "video": {
            role: f"observation.images.{role}"
            for role in ("overhead", "wrist_l", "wrist_r")
        },
    },
}


def run_one_policy_step(frames: dict, observation: dict) -> dict:
    guard = SafetyGuard(SafetyConfig())
    with dream.DreamClient() as client:
        client.policy(POLICY_CONFIG)
        client.set_observation(frames, observation)
        # The returned dict must be the ONLY action passed to the simulator.
        current_joints = {
            "right": observation["state.right_arm"],
            "left": observation["state.left_arm"],
        }
        return guarded_get_action(client, guard, current_joints=current_joints)


if __name__ == "__main__":
    raise SystemExit(
        "Import run_one_policy_step() and supply real frames/observation "
        "from the Playground integration example."
    )
