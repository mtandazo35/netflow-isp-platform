import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[2] / "processor" / "processor.py"
SPEC = importlib.util.spec_from_file_location("processor", MODULE_PATH)
PROCESSOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROCESSOR)


def record(src, dst, byte_count=1_000_000):
    return {
        "first": "2026-08-23T12:00:00Z",
        "last": "2026-08-23T12:00:10Z",
        "exporter_v4": "10.8.0.2",
        "src4_addr": src,
        "dst4_addr": dst,
        "src_port": 50000,
        "dst_port": 443,
        "proto": "TCP",
        "in_bytes": byte_count,
        "in_packets": 100,
    }


def test_processor_identifies_upload_and_download_customer_ip():
    upload = PROCESSOR.normalize(record("10.10.0.10", "8.8.8.8"))
    download = PROCESSOR.normalize(record("8.8.8.8", "10.10.0.10"))
    assert upload["direction"] == "upload"
    assert download["direction"] == "download"
    assert upload["subscriber_name"] == download["subscriber_name"] == "10.10.0.10"
    assert upload["subscriber_id"] == download["subscriber_id"]


def test_processor_recognizes_shared_cgnat_space_as_customer_network():
    flow = PROCESSOR.normalize(record("100.64.12.30", "8.8.8.8"))
    assert flow["subscriber_name"] == "100.64.12.30"
    assert flow["direction"] == "upload"


def test_processor_applies_manual_customer_name_plan_and_access_type():
    customer_map = [{
        "id": 500,
        "name": "cliente-pedro",
        "ip": "10.10.0.10",
        "exporter_ip": "10.8.0.2",
        "plan_mbps": 100,
        "access_type": "static",
    }]
    flow = PROCESSOR.normalize(record("10.10.0.10", "8.8.8.8"), customer_map)
    assert flow["subscriber_id"] == 500
    assert flow["subscriber_name"] == "cliente-pedro"
    assert flow["plan_mbps"] == 100
    assert flow["access_type"] == "static"
