import json

import pytest

from app.nfdump import NfdumpRecordError, iter_ndjson, normalize_record


def test_normalizes_common_nfdump_aliases():
    record = normalize_record({
        "first": "2026-08-23T12:00:00Z",
        "last": "2026-08-23T12:00:30Z",
        "exp_ip": "10.8.0.2",
        "srcip": "10.10.2.44",
        "dstip": "142.250.78.14",
        "srcport": 52144,
        "dstport": 443,
        "proto": "TCP",
        "in_bytes": 12500000,
        "in_packets": 9000,
    })
    assert record["protocol"] == 6
    assert record["bytes"] == 12_500_000
    assert record["source_ip"] == "10.10.2.44"


def test_iterates_ndjson_and_reports_bad_line():
    valid = json.dumps({
        "event_time": "2026-08-23T12:00:00Z",
        "end_time": "2026-08-23T12:00:01Z",
        "source_ip": "10.10.2.44",
        "destination_ip": "1.1.1.1",
        "protocol": 17,
        "bytes": 512,
    })
    assert len(list(iter_ndjson([valid]))) == 1
    with pytest.raises(NfdumpRecordError, match="line 2"):
        list(iter_ndjson([valid, "not-json"]))
