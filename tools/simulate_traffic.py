#!/usr/bin/env python3
import argparse
import json
import random
import urllib.request
from datetime import datetime, timedelta, timezone


PROFILES = [
    {"id": 101, "name": "hogar-normal", "plan": 100, "load": 0.08, "flows": 80},
    {"id": 202, "name": "streaming-intenso", "plan": 100, "load": 0.35, "flows": 220},
    {"id": 303, "name": "saturacion-sostenida", "plan": 100, "load": 0.94, "flows": 500},
]

DESTINATIONS = [
    ("142.250.78.14", 443, "youtube.com", "YouTube"),
    ("198.38.120.10", 443, "video.nflxvideo.net", "Netflix"),
    ("31.13.94.35", 443, "facebook.com", "Meta"),
    ("1.1.1.1", 443, "", "Unidentified"),
]


def build_flows(hours: int, seed: int) -> list[dict]:
    random.seed(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    flows = []
    for profile_index, profile in enumerate(PROFILES, start=1):
        client_ip = f"10.10.0.{10 + profile_index}"
        total_flows = max(1, profile["flows"] * hours)
        for _ in range(total_flows):
            offset = random.randint(0, max(1, hours * 3600 - 60))
            duration = random.randint(5, 60)
            start = now - timedelta(hours=hours) + timedelta(seconds=offset)
            destination_ip, destination_port, domain, application = random.choice(DESTINATIONS)
            target_mbps = profile["plan"] * profile["load"] * random.uniform(0.65, 1.0)
            byte_count = int(target_mbps * 1_000_000 / 8 * duration)
            flows.append({
                "event_time": start.isoformat(),
                "end_time": (start + timedelta(seconds=duration)).isoformat(),
                "exporter_ip": "10.8.0.2",
                "source_ip": client_ip,
                "destination_ip": destination_ip,
                "source_port": random.randint(1024, 65535),
                "destination_port": destination_port,
                "protocol": 6,
                "bytes": byte_count,
                "packets": max(1, byte_count // 1200),
                "direction": "download",
                "subscriber_id": profile["id"],
                "subscriber_name": profile["name"],
                "plan_mbps": profile["plan"],
                "access_type": ("pppoe", "dhcp", "static")[profile_index - 1],
                "domain": domain,
                "application": application,
                "attribution_confidence": "high" if domain else "unknown",
                "asn": 0,
                "country": "",
            })
    return flows


def post_batches(api_url: str, flows: list[dict], api_key: str, batch_size: int = 5_000):
    accepted = 0
    for index in range(0, len(flows), batch_size):
        payload = json.dumps({"flows": flows[index:index + batch_size]}).encode()
        request = urllib.request.Request(
            f"{api_url.rstrip('/')}/api/v1/flows",
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            accepted += json.loads(response.read())["accepted"]
    return accepted


def main():
    parser = argparse.ArgumentParser(description="Load deterministic simulated NetFlow traffic")
    parser.add_argument("--api-url", default="http://localhost:8080")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--seed", type=int, default=35)
    parser.add_argument("--api-key", default="replace-with-a-long-random-value")
    parser.add_argument("--output", help="Write JSON locally instead of posting to the API")
    args = parser.parse_args()
    if not 1 <= args.hours <= 168:
        parser.error("--hours must be between 1 and 168")

    flows = build_flows(args.hours, args.seed)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            json.dump({"flows": flows}, stream)
        print(f"Wrote {len(flows)} flows to {args.output}")
        return
    accepted = post_batches(args.api_url, flows, args.api_key)
    print(f"Accepted {accepted} simulated flows")


if __name__ == "__main__":
    main()
