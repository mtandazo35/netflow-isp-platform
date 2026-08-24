import hashlib
import ipaddress
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


FLOW_DIR = Path(os.getenv("FLOW_DIR", "/flows"))
STATE_FILE = Path(os.getenv("STATE_FILE", "/state/processed.json"))
API_URL = os.getenv("API_URL", "http://api:8080").rstrip("/")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "10"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))
CUSTOMER_MAP_FILE = Path(os.getenv("CUSTOMER_MAP_FILE", "/config/subscribers.json"))
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "replace-with-a-long-random-value")
CUSTOMER_NETWORKS = tuple(
    ipaddress.ip_network(item.strip())
    for item in os.getenv(
        "CUSTOMER_NETWORKS",
        "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10",
    ).split(",")
    if item.strip()
)


ALIASES = {
    "first": ("first", "event_time", "t_first", "first_seen", "first_seen_msec"),
    "last": ("last", "end_time", "t_last", "last_seen", "last_seen_msec"),
    "exporter": ("exporter_ip", "exporter", "exp_ip", "exporter_v4", "exporter_v6"),
    "src": ("source_ip", "srcip", "src_ip", "src4_addr", "src6_addr"),
    "dst": ("destination_ip", "dstip", "dst_ip", "dst4_addr", "dst6_addr"),
    "src_port": ("source_port", "srcport", "src_port"),
    "dst_port": ("destination_port", "dstport", "dst_port"),
    "proto": ("protocol", "proto"),
    "bytes": ("bytes", "in_bytes", "ibyt"),
    "packets": ("packets", "in_packets", "ipkt"),
}

PROTOCOLS = {"ICMP": 1, "TCP": 6, "UDP": 17, "GRE": 47, "ESP": 50, "ICMP6": 58}


def pick(record, field, default=None):
    for alias in ALIASES[field]:
        value = record.get(alias)
        if value not in (None, ""):
            return value
    return default


def timestamp(value):
    if isinstance(value, (int, float)):
        divisor = 1000 if value > 10_000_000_000 else 1
        return datetime.fromtimestamp(value / divisor, tz=timezone.utc).isoformat()
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def protocol_number(value):
    text = str(value).upper()
    return int(text) if text.isdigit() else PROTOCOLS.get(text, 0)


def is_customer_ip(value):
    address = ipaddress.ip_address(value)
    return any(address.version == network.version and address in network for network in CUSTOMER_NETWORKS)


def subscriber_key(value):
    address = ipaddress.ip_address(value)
    if address.version == 4:
        return int(address)
    return int.from_bytes(hashlib.blake2b(address.packed, digest_size=8).digest(), "big") or 1


def load_customer_map():
    try:
        payload = json.loads(CUSTOMER_MAP_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return payload.get("subscribers", [])


def customer_metadata(customer_ip, exporter_ip, customer_map):
    for item in customer_map:
        if item.get("ip") != customer_ip:
            continue
        expected_exporter = item.get("exporter_ip")
        if expected_exporter and expected_exporter != exporter_ip:
            continue
        return {
            "subscriber_id": int(item.get("id") or subscriber_key(customer_ip)),
            "subscriber_name": item.get("name") or customer_ip,
            "plan_mbps": max(0, int(item.get("plan_mbps", 0))),
            "access_type": item.get("access_type", "unknown"),
        }
    return {
        "subscriber_id": subscriber_key(customer_ip),
        "subscriber_name": customer_ip,
        "plan_mbps": 0,
        "access_type": "unknown",
    }


def normalize(record, customer_map=None):
    source_ip = str(pick(record, "src"))
    destination_ip = str(pick(record, "dst"))
    source_customer = is_customer_ip(source_ip)
    destination_customer = is_customer_ip(destination_ip)
    if source_customer and not destination_customer:
        customer_ip, direction = source_ip, "upload"
    elif destination_customer and not source_customer:
        customer_ip, direction = destination_ip, "download"
    elif source_customer:
        customer_ip, direction = source_ip, "unknown"
    else:
        customer_ip, direction = "", "unknown"

    first = pick(record, "first")
    last = pick(record, "last", first)
    if first is None:
        raise ValueError("flow has no timestamp")
    exporter_ip = str(pick(record, "exporter", "::"))
    identity = customer_metadata(customer_ip, exporter_ip, customer_map or []) if customer_ip else {
        "subscriber_id": 0, "subscriber_name": "", "plan_mbps": 0, "access_type": "unknown"
    }
    return {
        "event_time": timestamp(first),
        "end_time": timestamp(last),
        "exporter_ip": exporter_ip,
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "source_port": int(pick(record, "src_port", 0)),
        "destination_port": int(pick(record, "dst_port", 0)),
        "protocol": protocol_number(pick(record, "proto", 0)),
        "bytes": max(0, int(pick(record, "bytes", 0))),
        "packets": max(0, int(pick(record, "packets", 0))),
        "direction": direction,
        **identity,
        "domain": "",
        "application": "Unidentified",
        "attribution_confidence": "unknown",
        "asn": 0,
        "country": "",
    }


def decode_nfdump(path):
    result = subprocess.run(
        ["nfdump", "-r", str(path), "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    records = payload if isinstance(payload, list) else payload.get("flows", payload.get("records", []))
    customer_map = load_customer_map()
    for record in records:
        try:
            yield normalize(record, customer_map)
        except (TypeError, ValueError, ipaddress.AddressValueError) as exc:
            print(f"Skipping invalid flow in {path.name}: {exc}", flush=True)


def post_batch(flows):
    data = json.dumps({"flows": flows}).encode()
    request = urllib.request.Request(
        f"{API_URL}/api/v1/flows",
        data=data,
        headers={"Content-Type": "application/json", "X-API-Key": INGEST_API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())["accepted"]


def load_state():
    try:
        return set(json.loads(STATE_FILE.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_state(processed):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(processed)))
    temporary.replace(STATE_FILE)


def process_file(path):
    batch, accepted = [], 0
    for flow in decode_nfdump(path):
        batch.append(flow)
        if len(batch) >= BATCH_SIZE:
            accepted += post_batch(batch)
            batch.clear()
    if batch:
        accepted += post_batch(batch)
    return accepted


def main():
    processed = load_state()
    print(f"Watching {FLOW_DIR} and sending to {API_URL}", flush=True)
    while True:
        for path in sorted(FLOW_DIR.glob("nfcapd.*")):
            if "current" in path.name or path.name in processed:
                continue
            try:
                accepted = process_file(path)
                processed.add(path.name)
                save_state(processed)
                print(f"Processed {path.name}: {accepted} flows", flush=True)
            except Exception as exc:
                print(f"Failed {path.name}: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
