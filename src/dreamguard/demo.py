from .guard import SafetyConfig, SafetyGuard, SafetyReport, UnsafeActionError


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


def format_report(index: int, title: str, report: SafetyReport, max_findings: int = 5) -> str:
    timing = f"risk {report.risk_score}, {report.latency_ms:.2f} ms, {report.checked_rows} rows"
    lines = [f"Action {index}: {title}", f"Decision: {report.decision.value} ({timing})"]
    if not report.findings:
        lines.append("Findings: No safety violations")
    else:
        lines.append("Findings:")
        shown = report.findings[:max_findings]
        lines += [f"- [{f.severity.value}] {f.message}" for f in shown]
        if len(report.findings) > len(shown):
            lines.append(f"- ... and {len(report.findings) - len(shown)} more findings")
    return "\n".join(lines)


def main() -> None:
    guard = SafetyGuard(SafetyConfig(max_joint_step_rad=0.35))
    unsafe_action = sample_action()
    unsafe_action["q_r_chunk"][1][0] = 2.0  # 1.9 rad jump from previous row

    print("DreamGuard Safety Supervisor\n")
    scenarios = (("safe synthetic action", sample_action()), ("joint jump", unsafe_action))
    for index, (title, action) in enumerate(scenarios, start=1):
        report = guard.inspect(action, current_joints=CURRENT_JOINTS)
        print(format_report(index, title, report) + "\n")

    try:
        guard.approve(unsafe_action, current_joints=CURRENT_JOINTS)
    except UnsafeActionError as exc:
        print("Controller never received action 2:", exc)

    print("\nDemo complete. These are synthetic test values, not robot commands.")


if __name__ == "__main__":
    main()
