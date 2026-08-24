import json
from datetime import datetime, timezone
from typing import Any, Iterable


FIELD_ALIASES = {
    "event_time": ("event_time", "first", "t_first", "first_seen"),
    "end_time": ("end_time", "last", "t_last", "last_seen"),
    "exporter_ip": ("exporter_ip", "exporter", "exp_ip"),
    "source_ip": ("source_ip", "srcip", "src_ip"),
    "destination_ip": ("destination_ip", "dstip", "dst_ip"),
    "source_port": ("source_port", "srcport", "src_port"),
    "destination_port": ("destination_port", "dstport", "dst_port"),
    "protocol": ("protocol", "proto"),
    "bytes": ("bytes", "in_bytes", "ibyt"),
    "packets": ("packets", "in_packets", "ipkt"),
}

PROTOCOLS = {"icmp": 1, "tcp": 6, "udp": 17, "gre": 47, "esp": 50}


class NfdumpRecordError(ValueError):
    pass


def _pick(record: dict[str, Any], logical_name: str, default: Any = None):
    for field in FIELD_ALIASES[logical_name]:
        if field in record and record[field] not in (None, ""):
            return record[field]
    if default is not None:
        return default
    raise NfdumpRecordError(f"missing required field: {logical_name}")


def _timestamp(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise NfdumpRecordError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _protocol(value: Any) -> int:
    if isinstance(value, int) or str(value).isdigit():
        protocol = int(value)
    else:
        protocol = PROTOCOLS.get(str(value).lower(), -1)
    if not 0 <= protocol <= 255:
        raise NfdumpRecordError(f"invalid protocol: {value}")
    return protocol


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    event_time = _timestamp(_pick(record, "event_time"))
    end_time = _timestamp(_pick(record, "end_time"))
    if end_time < event_time:
        raise NfdumpRecordError("end_time is before event_time")

    return {
        "event_time": event_time,
        "end_time": end_time,
        "exporter_ip": str(_pick(record, "exporter_ip", "::")),
        "source_ip": str(_pick(record, "source_ip")),
        "destination_ip": str(_pick(record, "destination_ip")),
        "source_port": int(_pick(record, "source_port", 0)),
        "destination_port": int(_pick(record, "destination_port", 0)),
        "protocol": _protocol(_pick(record, "protocol")),
        "bytes": int(_pick(record, "bytes")),
        "packets": int(_pick(record, "packets", 0)),
    }


def iter_ndjson(lines: Iterable[str]) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            yield normalize_record(raw)
        except (json.JSONDecodeError, NfdumpRecordError, TypeError, ValueError) as exc:
            raise NfdumpRecordError(f"line {line_number}: {exc}") from exc
