import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[2] / "tools" / "simulate_traffic.py"
SPEC = importlib.util.spec_from_file_location("simulate_traffic", MODULE_PATH)
SIMULATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SIMULATOR)


def test_simulator_creates_three_access_types_and_usage_levels():
    flows = SIMULATOR.build_flows(hours=1, seed=35)
    assert {flow["access_type"] for flow in flows} == {"pppoe", "dhcp", "static"}
    totals = {}
    for flow in flows:
        totals.setdefault(flow["subscriber_name"], 0)
        totals[flow["subscriber_name"]] += flow["bytes"]
    assert totals["hogar-normal"] < totals["streaming-intenso"] < totals["saturacion-sostenida"]
