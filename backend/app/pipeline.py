from datetime import datetime
from typing import Any

from .correlation import DNSAnswer, IPAssignment, correlate_domain, match_session


APPLICATION_SUFFIXES = {
    "YouTube": ("youtube.com", "googlevideo.com", "ytimg.com", "youtubei.googleapis.com"),
    "Netflix": ("netflix.com", "nflxvideo.net", "nflximg.net", "nflxso.net"),
    "TikTok": ("tiktok.com", "tiktokcdn.com", "tiktokv.com", "byteoversea.com"),
    "Meta": ("facebook.com", "fbcdn.net", "instagram.com", "cdninstagram.com", "whatsapp.net"),
}


def classify_application(domain: str) -> str:
    normalized = domain.rstrip(".").lower()
    for application, suffixes in APPLICATION_SUFFIXES.items():
        if any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in suffixes):
            return application
    return "Other" if normalized else "Unidentified"


def enrich_flow(
    flow: dict[str, Any],
    sessions: list[IPAssignment],
    dns_answers: list[DNSAnswer],
) -> dict[str, Any]:
    event_time = flow["event_time"]
    if not isinstance(event_time, datetime):
        raise TypeError("event_time must be a datetime")

    exporter_ip = flow.get("exporter_ip")
    source_session = match_session(flow["source_ip"], event_time, sessions, exporter_ip)
    destination_session = match_session(flow["destination_ip"], event_time, sessions, exporter_ip)

    if source_session:
        session = source_session
        client_ip = flow["source_ip"]
        remote_ip = flow["destination_ip"]
        direction = "upload"
    elif destination_session:
        session = destination_session
        client_ip = flow["destination_ip"]
        remote_ip = flow["source_ip"]
        direction = "download"
    else:
        session = None
        client_ip = ""
        remote_ip = ""
        direction = "unknown"

    domain, confidence = ("", "unknown")
    if session:
        domain, confidence = correlate_domain(client_ip, remote_ip, event_time, dns_answers)

    return {
        **flow,
        "direction": direction,
        "subscriber_id": session.subscriber_id if session else 0,
        "subscriber_name": session.subscriber_name if session else "",
        "plan_mbps": session.plan_mbps if session else 0,
        "access_type": session.assignment_type if session else "unknown",
        "domain": domain,
        "application": classify_application(domain),
        "attribution_confidence": confidence,
        "asn": flow.get("asn", 0),
        "country": flow.get("country", ""),
    }
