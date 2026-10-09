import base64
import os
import pytest
from test_ftth_intake_api import api, REQUEST  # shared transaction-rollback fixture

pytestmark = pytest.mark.skipif(os.environ.get("NOC_ALLOW_INTEGRATION_TESTS") != "1", reason="Preview only")


def test_assignment_acceptance_and_customer_impact(api):
    client, session = api
    from app.models.infrastructure import FiberCable
    from app.models.allocations import DropAllocation
    order_in = client.post("/api/provisioning/intake/preview", json={"raw_text": REQUEST}).json()["order"]
    order = client.post("/api/provisioning/", json=order_in).json()
    options = client.get("/api/inventory/assignment-options").json()
    nap = options["naps"][0]
    assert 1 not in nap["available_ports"]  # existing seeded customer
    assert client.patch(f"/api/provisioning/{order['order_id']}/status", json={"status": "MONITORED"}).status_code == 409
    assignment = {"nap_id": nap["nap_id"], "port_number": 1, "new_drop_cable_code": "DROP-WORKFLOW-TEST",
                  "installer": "TEST INSTALLER", "planned_install_date": "2099-01-01T10:00:00+01:00"}
    assert client.patch(f"/api/provisioning/{order['order_id']}/allocate", json=assignment).status_code == 409
    assignment["port_number"] = nap["available_ports"][0]
    scheduled = client.patch(f"/api/provisioning/{order['order_id']}/allocate", json=assignment)
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["status"] == "SCHEDULED"
    assert scheduled.json()["drop_tech_name"] == "TEST INSTALLER"
    assert assignment["port_number"] not in client.get("/api/inventory/assignment-options").json()["naps"][0]["available_ports"]
    assert client.patch(f"/api/provisioning/{order['order_id']}/status", json={"status": "IN_PROGRESS"}).status_code == 200
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jqO0AAAAASUVORK5CYII=")
    completed = client.post(f"/api/provisioning/{order['order_id']}/complete",
        data={"flexscan_result_dbm": "-22.5", "checklist_completed": "true"},
        files={key: ("test.png", image, "image/png") for key in ("photo_nap", "photo_routing", "photo_rosette", "photo_flexscan")})
    assert completed.status_code == 200, completed.text
    accepted = client.patch(f"/api/provisioning/{order['order_id']}/accept")
    assert accepted.status_code == 200, accepted.text
    service_id = accepted.json()["activated_service_id"]
    assert service_id
    assert session.query(DropAllocation).filter_by(service_id=service_id).count() == 1
    assert client.patch(f"/api/provisioning/{order['order_id']}/accept").status_code == 400
    cable = session.query(FiberCable).filter_by(cable_name="CABLE-N1").one()
    impact = client.get(f"/api/topology/impact/{cable.route_id}")
    assert impact.status_code == 200, impact.text
    match = next(row for row in impact.json()["services"] if row["service_id"] == service_id)
    assert match["affected_paths"][0]["nap_id"] == nap["nap_id"]
    assert match["service_health"] == "not_verified"
    logical = client.get(f"/api/topology/expand/{cable.cable_id}").json()
    assert any(node["data"]["label"] == order["customer_name"] for node in logical["nodes"])


def test_create_nap_and_validate_assignment(api):
    client, _ = api
    splitter = client.get("/api/inventory/assignment-options").json()["splitters"][0]
    payload = {"nap_code": "NAP-INTAKE-TEST", "pfs_id": splitter["pfs_id"], "total_ports": 8}
    assert client.post("/api/inventory/naps", json=payload).status_code == 200
    assert client.post("/api/inventory/naps", json=payload).status_code == 409
    assert client.post("/api/inventory/naps", json={**payload, "total_ports": 0}).status_code == 422


def test_shared_activity_incident_and_handover_fields(api):
    client, _ = api
    payload = {"person": "TEST OPERATOR", "shift": "Night", "category": "Incident", "title": "Test link outage",
               "description": "Awaiting engineering investigation", "handover": True, "severity": "High"}
    response = client.post("/api/activities/", json=payload)
    assert response.status_code == 200, response.text
    entry = response.json()
    assert entry["incident_id"]
    incident = client.get(f"/api/incidents/{entry['incident_id']}").json()
    assert incident["tt_number"].startswith("TN_IM_")
    assert client.patch(f"/api/activities/{entry['activity_id']}", json={"status": "Completed"}).status_code == 200
    assert client.get(f"/api/incidents/{entry['incident_id']}").json()["status"] == "open"
    assert any(row["activity_id"] == entry["activity_id"] for row in client.get("/api/activities/").json())


def test_persistent_map_link_and_customer_anchor(api):
    client, session = api
    from app.models.infrastructure import FiberRoute
    kml = b'<kml><Document><name>Test map</name><Placemark><name>Test route</name><LineString><coordinates>3.4,6.4 3.5,6.5</coordinates></LineString></Placemark></Document></kml>'
    uploaded = client.post("/api/topology/maps", files={"file": ("test.kml", kml, "application/xml")})
    assert uploaded.status_code == 200, uploaded.text
    map_id = uploaded.json()["import_id"]
    assert client.post("/api/topology/maps", files={"file": ("test.kml", kml, "application/xml")}).json()["outcome"] == "existing"
    route = session.query(FiberRoute).filter_by(route_name="North-Zone-Backbone").one()
    linked = client.post(f"/api/topology/maps/{map_id}/link", json={"route_id": str(route.route_id), "feature_index": 0})
    assert linked.status_code == 200, linked.text
    assert client.get(f"/api/topology/maps/{map_id}").json()["features"][0]["properties"]["inventory_route_id"] == str(route.route_id)
    geo = client.get("/api/topology/geography")
    assert geo.status_code == 200, geo.text
    assert any(f["properties"].get("node_type") == "customer" for f in geo.json()["features"])


@pytest.mark.parametrize("service_type", ["DIA", "DARKFIBER", "LAYER2"])
def test_enterprise_services_and_core_reservation(api, service_type):
    client, session = api
    from app.models.infrastructure import FiberCore, FiberCable
    cable = session.query(FiberCable).filter_by(cable_name="CABLE-N1").one()
    core = FiberCore(cable_id=cable.cable_id, core_number=20, usage_type="FREE", allocation_status="free")
    session.add(core); session.flush()
    payload = {"customer_name": "TEST ENTERPRISE", "customer_code": "TEST-ENTERPRISE",
               "service_type": service_type, "bandwidth_mbps": None if service_type == "DARKFIBER" else 100,
               "core_id": str(core.core_id)}
    response = client.post("/api/services/", json=payload)
    assert response.status_code == 200, response.text
    service_id = response.json()["service_id"]
    impact = client.get(f"/api/topology/cable-impact/{cable.cable_id}")
    assert impact.status_code == 200, impact.text
    match = next(row for row in impact.json()["services"] if row["service_id"] == service_id)
    assert match["service_type"] == service_type
    assert match["affected_paths"][0]["core_id"] == str(core.core_id)
    assert client.post("/api/services/", json=payload).status_code == 409


def test_alternate_path_is_recorded_without_claiming_health(api):
    client, session = api
    from app.models.infrastructure import FiberCore, FiberCable
    cables = session.query(FiberCable).order_by(FiberCable.cable_name).all()
    cores = [FiberCore(cable_id=cable.cable_id, core_number=21, usage_type="FREE", allocation_status="free") for cable in cables]
    session.add_all(cores); session.flush()
    response = client.post("/api/services/", json={"customer_name": "TEST PROTECTED", "customer_code": "TEST-PROTECTED",
        "service_type": "DIA", "bandwidth_mbps": 100, "core_id": str(cores[0].core_id), "backup_core_id": str(cores[1].core_id)})
    assert response.status_code == 200, response.text
    impact = client.get(f"/api/topology/cable-impact/{cables[0].cable_id}").json()
    row = next(row for row in impact["services"] if row["service_id"] == response.json()["service_id"])
    assert row["alternate_path_recorded"] is True
    assert row["service_health"] == "not_verified"
