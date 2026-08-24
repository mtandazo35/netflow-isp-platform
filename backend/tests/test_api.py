from datetime import datetime, timedelta, timezone


def sample_flow(**overrides):
    start = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    data = {
        "event_time": start.isoformat(),
        "end_time": (start + timedelta(seconds=30)).isoformat(),
        "exporter_ip": "10.8.0.2",
        "source_ip": "10.10.2.44",
        "destination_ip": "142.250.78.14",
        "source_port": 52144,
        "destination_port": 443,
        "protocol": 6,
        "bytes": 12_500_000,
        "packets": 9_000,
        "direction": "download",
        "subscriber_id": 101,
        "subscriber_name": "cliente101",
        "plan_mbps": 100,
        "domain": "youtube.com",
        "application": "YouTube",
        "attribution_confidence": "high",
        "asn": 15169,
        "country": "US",
    }
    data.update(overrides)
    return data


def test_health(client, fake_clickhouse):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert fake_clickhouse.command_calls == ["SELECT 1"]


def test_ingest_normalized_flow(client, fake_clickhouse):
    response = client.post("/api/v1/flows", json={"flows": [sample_flow()]})
    assert response.status_code == 202
    assert response.json() == {"accepted": 1}
    table, rows, columns = fake_clickhouse.insert_calls[0]
    assert table == "flows"
    assert len(rows) == 1
    assert rows[0][columns.index("domain")] == "youtube.com"
    assert rows[0][columns.index("bytes")] == 12_500_000


def test_ingestion_rejects_invalid_api_key(client):
    response = client.post(
        "/api/v1/flows",
        json={"flows": [sample_flow()]},
        headers={"X-API-Key": "wrong"},
    )
    assert response.status_code == 401


def test_rejects_invalid_flow_time(client):
    start = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    response = client.post(
        "/api/v1/flows",
        json={"flows": [sample_flow(end_time=(start - timedelta(seconds=1)).isoformat())]},
    )
    assert response.status_code == 422


def test_ingest_dns_answer_normalizes_domain(client, fake_clickhouse):
    response = client.post("/api/v1/dns-answers", json={"answers": [{
        "event_time": "2026-08-23T12:00:00Z",
        "client_ip": "10.10.2.44",
        "domain": "YouTube.COM.",
        "answer_ip": "142.250.78.14",
        "ttl": 300,
        "resolver": "technitium",
    }]})
    assert response.status_code == 202
    table, rows, columns = fake_clickhouse.insert_calls[0]
    assert table == "dns_answers"
    assert rows[0][columns.index("domain")] == "youtube.com"


def test_domain_query_maps_rows(client, fake_clickhouse):
    fake_clickhouse.next_result.column_names = ["domain_name", "total_bytes", "active_seconds"]
    fake_clickhouse.next_result.result_rows = [("youtube.com", 1_000_000_000, 3_600)]
    response = client.get("/api/v1/analytics/subscribers/101/domains?hours=24")
    assert response.status_code == 200
    assert response.json()["items"][0] == {
        "domain_name": "youtube.com",
        "total_bytes": 1_000_000_000,
        "active_seconds": 3_600,
    }
    _, parameters = fake_clickhouse.query_calls[0]
    assert parameters["subscriber_id"] == 101


def test_query_limits_are_validated(client):
    response = client.get("/api/v1/analytics/top-subscribers?hours=0")
    assert response.status_code == 422


def test_overview_maps_aggregate_values(client, fake_clickhouse):
    fake_clickhouse.next_result.column_names = [
        "total_bytes", "bytes_down", "bytes_up", "subscribers", "flows", "exporters"
    ]
    fake_clickhouse.next_result.result_rows = [(1_500_000, 1_200_000, 300_000, 3, 800, 1)]
    response = client.get("/api/v1/analytics/overview?hours=24")
    assert response.status_code == 200
    assert response.json()["subscribers"] == 3
    assert response.json()["total_bytes"] == 1_500_000
