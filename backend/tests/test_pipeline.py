from datetime import datetime, timedelta, timezone

from app.correlation import DNSAnswer, IPAssignment, SubscriberSession
from app.pipeline import classify_application, enrich_flow


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def base_flow(source_ip, destination_ip):
    return {
        "event_time": NOW + timedelta(seconds=60),
        "end_time": NOW + timedelta(seconds=90),
        "exporter_ip": "10.8.0.2",
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "source_port": 52144,
        "destination_port": 443,
        "protocol": 6,
        "bytes": 12_500_000,
        "packets": 9_000,
    }


def test_enriches_upload_with_subscriber_and_domain():
    sessions = [SubscriberSession(101, "cliente101", 100, "10.10.2.44", NOW)]
    answers = [DNSAnswer(NOW, "10.10.2.44", "r3---sn.googlevideo.com", "142.250.78.14", 300)]
    enriched = enrich_flow(base_flow("10.10.2.44", "142.250.78.14"), sessions, answers)
    assert enriched["subscriber_id"] == 101
    assert enriched["direction"] == "upload"
    assert enriched["domain"] == "r3---sn.googlevideo.com"
    assert enriched["application"] == "YouTube"
    assert enriched["attribution_confidence"] == "high"


def test_enriches_download_using_remote_source_ip():
    sessions = [SubscriberSession(101, "cliente101", 100, "10.10.2.44", NOW)]
    answers = [DNSAnswer(NOW, "10.10.2.44", "video.nflxvideo.net", "198.38.120.10", 300)]
    enriched = enrich_flow(base_flow("198.38.120.10", "10.10.2.44"), sessions, answers)
    assert enriched["direction"] == "download"
    assert enriched["application"] == "Netflix"


def test_flow_without_session_is_not_attributed():
    enriched = enrich_flow(base_flow("192.0.2.10", "198.51.100.20"), [], [])
    assert enriched["subscriber_id"] == 0
    assert enriched["direction"] == "unknown"
    assert enriched["application"] == "Unidentified"


def test_application_classifier_requires_domain_boundary():
    assert classify_application("youtube.com") == "YouTube"
    assert classify_application("cdn.youtube.com") == "YouTube"
    assert classify_application("notyoutube.com") == "Other"


def test_pipeline_preserves_access_type_for_dhcp_and_static_clients():
    dns = [DNSAnswer(NOW, "10.10.2.50", "youtube.com", "142.250.78.14", 300)]
    dhcp = IPAssignment(
        202, "dhcp202", 100, "10.10.2.50", NOW,
        assignment_type="dhcp", mac_address="02:00:00:00:02:02",
    )
    enriched = enrich_flow(base_flow("10.10.2.50", "142.250.78.14"), [dhcp], dns)
    assert enriched["access_type"] == "dhcp"
    assert enriched["subscriber_id"] == 202

    static = IPAssignment(303, "static303", 200, "10.10.2.60", NOW, assignment_type="static")
    enriched = enrich_flow(base_flow("10.10.2.60", "1.1.1.1"), [static], [])
    assert enriched["access_type"] == "static"
    assert enriched["subscriber_id"] == 303
