from app.risk import UsageSignals, resale_risk_score


def test_residential_pattern_is_lower_risk_than_sustained_saturation():
    residential = UsageSignals(
        plan_mbps=100,
        average_mbps=8,
        active_hours=35,
        observed_hours=168,
        unique_destinations=350,
        flow_count=8_000,
    )
    sustained = UsageSignals(
        plan_mbps=100,
        average_mbps=94,
        active_hours=160,
        observed_hours=168,
        unique_destinations=8_000,
        flow_count=900_000,
    )
    assert resale_risk_score(residential) < 50
    assert resale_risk_score(sustained) >= 85


def test_score_stays_between_zero_and_one_hundred():
    empty = UsageSignals(100, 0, 0, 168, 0, 0)
    extreme = UsageSignals(100, 500, 500, 168, 1_000_000, 100_000_000)
    assert 0 <= resale_risk_score(empty) <= 100
    assert resale_risk_score(extreme) == 100
