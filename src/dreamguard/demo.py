from .guard import SafetyConfig, SafetyGuard, UnsafeActionError


def sample_action(step: float = 0.04) -> dict:
    row = [0.10, -0.20, 0.30, -0.10, 0.20, 0.00, 0.50]
    next_row = [v + step if i < 6 else v for i, v in enumerate(row)]
    return {
        "q_r_chunk": [row, next_row],
        "q_l_chunk": [list(row), list(next_row)],
        "demo_metadata": {"checkpoint": "synthetic-demo-only"},
    }


CURRENT_JOINTS = {
    "right": [0.10, -0.20, 0.30, -0.10, 0.20, 0.00],
    "left": [0.10, -0.20, 0.30, -0.10, 0.20, 0.00],
}


def main() -> None:
    guard = SafetyGuard(SafetyConfig(max_joint_step_rad=0.35))

    print("\n--- SAFE SYNTHETIC ACTION ---")
    safe = guard.inspect(sample_action(), current_joints=CURRENT_JOINTS)
    print(safe.as_dict())

    print("\n--- UNSAFE SYNTHETIC ACTION ---")
    unsafe_action = sample_action()
    unsafe_action["q_r_chunk"][1][0] = 2.0  # 1.9 rad jump from previous row
    try:
        guard.approve(unsafe_action, current_joints=CURRENT_JOINTS)
    except UnsafeActionError as exc:
        print(exc.report.as_dict())
        print("BLOCKED:", exc)

    print("\nDemo complete. These are synthetic test values, not robot commands.")


if __name__ == "__main__":
    main()
