from datetime import datetime, timedelta, timezone

from app.correlation import DNSAnswer, IPAssignment, SubscriberSession, correlate_domain, match_session


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def test_matches_subscriber_only_inside_session_window():
    session = SubscriberSession(101, "cliente101", 100, "10.10.2.44", NOW, NOW + timedelta(hours=2))
    assert match_session("10.10.2.44", NOW + timedelta(minutes=30), [session]) == session
    assert match_session("10.10.2.44", NOW + timedelta(hours=3), [session]) is None


def test_reused_ip_selects_session_valid_at_flow_time():
    first = SubscriberSession(101, "cliente101", 100, "10.10.2.44", NOW, NOW + timedelta(hours=1))
    second = SubscriberSession(202, "cliente202", 200, "10.10.2.44", NOW + timedelta(hours=2), None)
    assert match_session("10.10.2.44", NOW + timedelta(minutes=30), [first, second]) == first
    assert match_session("10.10.2.44", NOW + timedelta(hours=3), [first, second]) == second


def test_dns_correlation_uses_client_ip_destination_and_ttl():
    answer = DNSAnswer(NOW, "10.10.2.44", "YouTube.COM.", "142.250.78.14", 300)
    assert correlate_domain(
        "10.10.2.44", "142.250.78.14", NOW + timedelta(seconds=120), [answer]
    ) == ("youtube.com", "high")
    assert correlate_domain(
        "10.10.2.44", "142.250.78.14", NOW + timedelta(seconds=301), [answer]
    ) == ("", "unknown")
    assert correlate_domain(
        "10.10.2.99", "142.250.78.14", NOW + timedelta(seconds=120), [answer]
    ) == ("", "unknown")


def test_all_access_types_use_the_same_temporal_identity_layer():
    assignments = [
        IPAssignment(1, "pppoe01", 100, "10.10.0.1", NOW, assignment_type="pppoe"),
        IPAssignment(2, "dhcp01", 100, "10.10.0.2", NOW, assignment_type="dhcp", mac_address="02:00:00:00:00:02"),
        IPAssignment(3, "static01", 100, "10.10.0.3", NOW, assignment_type="static"),
    ]
    for assignment in assignments:
        resolved = match_session(assignment.assigned_ip, NOW + timedelta(hours=1), assignments)
        assert resolved == assignment


def test_exporter_disambiguates_repeated_private_ip_ranges():
    router_a = IPAssignment(
        10, "cliente-router-a", 100, "10.10.0.10", NOW,
        assignment_type="static", exporter_ip="10.8.0.2",
    )
    router_b = IPAssignment(
        20, "cliente-router-b", 100, "10.10.0.10", NOW,
        assignment_type="static", exporter_ip="10.8.0.3",
    )
    assert match_session(
        "10.10.0.10", NOW + timedelta(minutes=5), [router_a, router_b], "10.8.0.3"
    ) == router_b
