"""Run only in the isolated preview: dev.ps1 start, then the documented test command.

All writes use savepoints inside an outer transaction rolled back after each test.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("NOC_ALLOW_INTEGRATION_TESTS") != "1",
    reason="Requires explicit opt-in against the isolated preview database",
)


@pytest.fixture
def api():
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from app.core.config import settings
    from app.core.db import engine, get_db
    from app.main import app

    assert settings.POSTGRES_DB == "noc_preview", "These tests must use the preview database"
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: session
        try:
            with TestClient(app) as client:
                yield client, session
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()


REQUEST = """FN NUMBER
FN987654321
PENDING
CUSTOMER NAME
INTAKE TEST CUSTOMER
SERVICE ADDRESS
1 Test Lane, Lagos
SERVICE PACKAGE
100Mbps
CONTACT PHONE
07012345678
EMAIL
orders@example.com
WORK ORDER ID
CO987654321
FN NUMBER
FN987654321
SFC ASSIGNED"""


def test_preview_import_repeat_and_conflicting_order(api):
    client, session = api
    from app.models.provisioning import ServiceOrder
    count_before = session.query(ServiceOrder).count()
    preview = client.post("/api/provisioning/intake/preview", json={"raw_text": REQUEST})
    assert preview.status_code == 200, preview.text
    order = preview.json()["order"]
    payload = {"raw_text": REQUEST, "order": order}
    created = client.post("/api/provisioning/intake", json=payload)
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["outcome"] == "created"
    assert data["order"]["status"] == "REQUESTED"
    assert data["order"]["work_order_id"] == "CO987654321"
    assert data["order"]["intake_source"] == "paste"
    repeated = client.post("/api/provisioning/intake", json=payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["outcome"] == "already_logged"
    assert repeated.json()["order"]["order_id"] == data["order"]["order_id"]
    assert session.query(ServiceOrder).count() == count_before + 1
    row = session.query(ServiceOrder).filter_by(order_id=data["order"]["order_id"]).one()
    assert row.raw_request_text == REQUEST
    conflict = client.post("/api/provisioning/intake", json={
        **payload, "order": {**order, "customer_name": "DIFFERENT CUSTOMER"},
    })
    assert conflict.status_code == 409
    assert session.query(ServiceOrder).count() == count_before + 1
    assert any(item["order_id"] == data["order"]["order_id"] for item in client.get("/api/provisioning/").json())


def test_missing_fields_and_bad_email_cannot_create_orders(api):
    client, _ = api
    assert client.post("/api/provisioning/intake/preview", json={"raw_text": "FN NUMBER\nFN123"}).status_code == 422
    assert client.post("/api/provisioning/intake/preview", json={"raw_text": REQUEST.replace("orders@example.com", "invalid-email")}).status_code == 422


def test_atomic_ids_and_database_reference_uniqueness(api):
    client, session = api
    from sqlalchemy.exc import IntegrityError
    from app.models.provisioning import ServiceOrder
    order = client.post("/api/provisioning/intake/preview", json={"raw_text": REQUEST}).json()["order"]
    first = client.post("/api/provisioning/", json=order).json()
    second = client.post("/api/provisioning/", json={**order, "fn_number": "FN987654322", "work_order_id": "CO987654322"}).json()
    assert first["service_order_number"] != second["service_order_number"]
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(ServiceOrder(**order, service_order_number="TEST-DUPLICATE", service_id="TEST-DUPLICATE"))
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(ServiceOrder(**{**order, "fn_number": "FN987654323"},
                                 service_order_number="TEST-WORK-DUP", service_id="TEST-WORK-DUP"))
        session.flush()


def test_real_topology_expansion_and_invalid_identifiers(api):
    client, session = api
    from app.models.infrastructure import FiberCable
    south = session.query(FiberCable).filter_by(cable_name="CABLE-S1").one()
    assert client.get(f"/api/topology/expand/{south.cable_id}").json() == {"nodes": [], "edges": []}
    assert client.get("/api/topology/expand/not-a-uuid").status_code == 422
    assert client.get("/api/topology/expand/00000000-0000-0000-0000-000000000001").status_code == 404
