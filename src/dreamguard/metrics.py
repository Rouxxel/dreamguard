"""Session metrics (PRD section 13) computed from recorded events (`SafetyEvent.as_dict`)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from math import ceil
from typing import Any

# Sources whose chunks are known to be safe unless a fault was injected, so a blocked chunk without
# an injected fault is a false rejection. Replayed or live model chunks have no such ground truth.
GROUND_TRUTH_SOURCES = frozenset({"fake"})


def _percentile(sorted_values: list[float], percent: float) -> float | None:
    if not sorted_values:
        return None
    rank = max(1, ceil(percent / 100 * len(sorted_values)))
    return round(sorted_values[rank - 1], 3)


def summarize_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts, unsafe-action outcomes, latency percentiles and violations per check."""
    actions = approved = executed = halts = 0
    unsafe_injected = unsafe_prevented = unsafe_missed = false_rejections = 0
    latencies: list[float] = []
    violations: Counter[str] = Counter()
    warnings = 0
    first = last = None
    sources: set[str] = set()

    for event in events:
        report = event.get("report") or {}
        actions += 1
        is_approved = bool(report.get("approved"))
        approved += is_approved
        executed += bool(event.get("executed"))
        halts += bool(event.get("halted"))
        if isinstance(report.get("latency_ms"), (int, float)):
            latencies.append(float(report["latency_ms"]))
        for finding in report.get("findings") or []:
            if finding.get("severity") == "violation":
                violations[finding.get("check", "unknown")] += 1
            else:
                warnings += 1

        injected = (event.get("metadata") or {}).get("injected_faults") or []
        source = event.get("source") or ""
        sources.add(source)
        if injected:
            unsafe_injected += 1
            if event.get("executed"):
                unsafe_missed += 1
            else:
                unsafe_prevented += 1
        elif not is_approved and source in GROUND_TRUTH_SOURCES:
            false_rejections += 1

        timestamp = event.get("timestamp")
        first = first or timestamp
        last = timestamp or last

    latencies.sort()
    return {
        "actions_evaluated": actions,
        "approved": approved,
        "blocked": actions - approved,
        "executed": executed,
        "halts": halts,
        "unsafe_injected": unsafe_injected,
        "unsafe_prevented": unsafe_prevented,
        "unsafe_missed": unsafe_missed,
        "false_rejections": false_rejections,
        "warnings": warnings,
        "violations_by_check": dict(sorted(violations.items())),
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "max": round(latencies[-1], 3) if latencies else None,
        },
        "sources": sorted(s for s in sources if s),
        "first_timestamp": first,
        "last_timestamp": last,
    }
