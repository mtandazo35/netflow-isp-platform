from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address


@dataclass(frozen=True)
class IPAssignment:
    subscriber_id: int
    subscriber_name: str
    plan_mbps: int
    assigned_ip: str
    started_at: datetime
    ended_at: datetime | None = None
    assignment_type: str = "unknown"
    router_id: int | None = None
    exporter_ip: str | None = None
    mac_address: str | None = None

    def __post_init__(self):
        if self.assignment_type not in {"unknown", "pppoe", "dhcp", "static"}:
            raise ValueError(f"unsupported assignment_type: {self.assignment_type}")

    def contains(self, client_ip: str, event_time: datetime, exporter_ip: str | None = None) -> bool:
        exporter_matches = (
            not self.exporter_ip
            or not exporter_ip
            or ip_address(self.exporter_ip) == ip_address(exporter_ip)
        )
        return (
            ip_address(self.assigned_ip) == ip_address(client_ip)
            and exporter_matches
            and self.started_at <= event_time
            and (self.ended_at is None or event_time <= self.ended_at)
        )


@dataclass(frozen=True)
class DNSAnswer:
    event_time: datetime
    client_ip: str
    domain: str
    answer_ip: str
    ttl: int

    @property
    def expires_at(self) -> datetime:
        return self.event_time + timedelta(seconds=max(0, self.ttl))

    def matches(self, client_ip: str, destination_ip: str, event_time: datetime) -> bool:
        return (
            ip_address(self.client_ip) == ip_address(client_ip)
            and ip_address(self.answer_ip) == ip_address(destination_ip)
            and self.event_time <= event_time <= self.expires_at
        )


def match_session(
    client_ip: str,
    event_time: datetime,
    sessions: list[IPAssignment],
    exporter_ip: str | None = None,
) -> IPAssignment | None:
    matches = [
        session for session in sessions
        if session.contains(client_ip, event_time, exporter_ip)
    ]
    if not matches:
        return None
    return max(matches, key=lambda session: session.started_at)


# Backward-compatible name while the rest of the MVP migrates to generic identity.
SubscriberSession = IPAssignment


def correlate_domain(
    client_ip: str,
    destination_ip: str,
    event_time: datetime,
    answers: list[DNSAnswer],
) -> tuple[str, str]:
    matches = [
        answer
        for answer in answers
        if answer.matches(client_ip, destination_ip, event_time)
    ]
    if not matches:
        return "", "unknown"
    answer = max(matches, key=lambda item: item.event_time)
    return answer.domain.rstrip(".").lower(), "high"
