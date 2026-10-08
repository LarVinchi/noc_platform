from datetime import date
from types import SimpleNamespace as Record

from app.services.topology import build_cable_topology


def service(identifier="service", kind="DIA"):
    return Record(service_id=identifier, service_type=kind, bandwidth_mbps=100,
                  customer=Record(customer_name="Customer"))


def cable(identifier, service_record=None):
    live = Record(allocation_id=f"{identifier}-live", is_active=True,
                  nap_port_number=1, service=service())
    inactive = Record(allocation_id=f"{identifier}-old", is_active=False,
                      nap_port_number=2, service=service())
    nap = Record(nap_id=f"{identifier}-nap", nap_code="NAP", total_ports=8,
                 drop_cables=[Record(allocations=[live, inactive])])
    pfs = Record(pfs_id=f"{identifier}-pfs", name="PFS", split_ratio="1:8", naps=[nap])
    pfp = Record(pfp_id=f"{identifier}-pfp", name="PFP", split_ratio="1:4", pfss=[pfs])
    allocations = [] if service_record is None else [Record(end_date=None, service=service_record)]
    core = Record(core_number=1, allocations=allocations, pfps=[pfp])
    return Record(cable_id=identifier, cores=[core])


def test_expansion_contains_only_descendants_and_active_customers():
    selected, unrelated = cable("selected"), cable("unrelated")
    result = build_cable_topology(selected)
    identifiers = {node["id"] for node in result["nodes"]}
    assert identifiers == {"selected-pfp", "selected-pfs", "selected-nap", "cpe-selected-live"}
    assert unrelated.cores[0].pfps[0].pfp_id not in identifiers
    assert {(edge["source"], edge["target"]) for edge in result["edges"]} == {
        ("selected", "selected-pfp"), ("selected-pfp", "selected-pfs"),
        ("selected-pfs", "selected-nap"), ("selected-nap", "cpe-selected-live"),
    }


def test_multiple_cores_do_not_duplicate_service_nodes_or_edges():
    selected = cable("selected", service(kind="DARKFIBER"))
    second = Record(core_number=2, pfps=[], allocations=[
        Record(end_date=None, service=service(kind="DARKFIBER")),
        Record(end_date=date(2025, 1, 1), service=service("expired")),
    ])
    selected.cores.append(second)
    result = build_cable_topology(selected)
    endpoints = [node for node in result["nodes"] if node["id"].startswith("srv-")]
    assert len(endpoints) == 1
    assert endpoints[0]["type"] == "dark_fiber_endpoint"
    assert endpoints[0]["data"]["badge"] == "Core 1; Core 2"
    assert len([edge for edge in result["edges"] if edge["target"] == "srv-service"]) == 1


def test_empty_cable_has_no_invented_descendants():
    assert build_cable_topology(Record(cable_id="empty", cores=[])) == {"nodes": [], "edges": []}
