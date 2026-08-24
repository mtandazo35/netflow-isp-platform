from dataclasses import dataclass
from math import log10


@dataclass(frozen=True)
class UsageSignals:
    plan_mbps: float
    average_mbps: float
    active_hours: float
    observed_hours: float
    unique_destinations: int
    flow_count: int


def resale_risk_score(signals: UsageSignals) -> float:
    """Return a 0-100 operational indicator; it is not proof of resale."""
    capacity = 0.0
    if signals.plan_mbps > 0:
        capacity = min(40.0, signals.average_mbps / signals.plan_mbps * 40.0)

    expected_active_window = max(1.0, signals.observed_hours * 0.8)
    persistence = min(25.0, signals.active_hours / expected_active_window * 25.0)
    diversity = min(20.0, log10(max(0, signals.unique_destinations) + 1) * 5.0)
    concurrency_proxy = min(15.0, log10(max(0, signals.flow_count) + 1) * 3.0)
    return round(min(100.0, capacity + persistence + diversity + concurrency_proxy), 2)
