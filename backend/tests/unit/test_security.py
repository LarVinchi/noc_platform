"""Local signing keys test validation without contacting Microsoft."""
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

# Unit suite must not require a database password or connection.
import os
os.environ.setdefault("POSTGRES_PASSWORD", "unit-test-unused")
from app.core import security


@pytest.fixture
def identity(monkeypatch):
    tenant, audience, client, oid = [str(uuid4()) for _ in range(4)]
    for name, value in {"ENVIRONMENT": "production", "AUTH_MODE": "entra", "ENTRA_TENANT_ID": tenant,
                        "ENTRA_API_CLIENT_ID": audience, "ENTRA_SPA_CLIENT_ID": client}.items():
        monkeypatch.setattr(security.settings, name, value)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(security, "key_client", lambda tenant: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())))
    now = int(time.time())
    claims = {"tid": tenant, "aud": audience, "azp": client, "oid": oid, "ver": "2.0",
              "iss": f"https://login.microsoftonline.com/{tenant}/v2.0", "iat": now, "nbf": now,
              "exp": now + 600, "scp": "access_as_user", "roles": ["NOC.Operator"]}
    return private, claims


def test_verified_operator(identity):
    private, claims = identity
    actor = security.authenticate({"authorization": "Bearer " + jwt.encode(claims, private, algorithm="RS256")}, "POST", "/api/provisioning/")
    assert actor["verified"] and actor["id"] == claims["oid"]


@pytest.mark.parametrize("field,value", [
    ("aud", "wrong"), ("iss", "wrong"), ("tid", "wrong"), ("azp", "wrong"),
    ("exp", 1), ("nbf", 9999999999), ("oid", "not-a-uuid"),
    ("scp", "wrong"), ("roles", []), ("roles", "NOC.Admin"),
])
def test_rejects_invalid_claims(identity, field, value):
    private, claims = identity
    with pytest.raises(HTTPException) as error:
        security.validate_token(jwt.encode({**claims, field: value}, private, algorithm="RS256"))
    assert error.value.status_code in (401, 403)


def test_missing_expiry_and_wrong_signature(identity):
    private, claims = identity
    del claims["exp"]
    with pytest.raises(HTTPException):
        security.validate_token(jwt.encode(claims, private, algorithm="RS256"))
    with pytest.raises(HTTPException):
        security.validate_token(jwt.encode(claims, "attacker" * 8, algorithm="HS256"))


def test_viewer_can_read_but_not_mutate_or_read_audit(identity):
    private, claims = identity
    token = jwt.encode({**claims, "roles": ["NOC.Viewer"]}, private, algorithm="RS256")
    headers = {"authorization": "Bearer " + token}
    assert security.authenticate(headers, "GET", "/api/provisioning/")["verified"]
    for method, path in (("POST", "/api/provisioning/"), ("GET", "/api/audit/")):
        with pytest.raises(HTTPException) as error:
            security.authenticate(headers, method, path)
        assert error.value.status_code == 403


def test_preview_requires_explicit_development_mode(monkeypatch):
    monkeypatch.setattr(security.settings, "AUTH_MODE", "preview")
    monkeypatch.setattr(security.settings, "ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as error:
        security.authenticate({}, "GET", "/api/customers/")
    assert error.value.status_code == 503
    monkeypatch.setattr(security.settings, "ENVIRONMENT", "development")
    assert not security.authenticate({}, "POST", "/api/provisioning/")["verified"]


def test_missing_bearer_and_unconfigured_identity(identity, monkeypatch):
    with pytest.raises(HTTPException) as error:
        security.authenticate({}, "GET", "/static/documents/private.pdf")
    assert error.value.status_code == 401
    monkeypatch.setattr(security.settings, "ENTRA_API_CLIENT_ID", "")
    with pytest.raises(HTTPException) as error:
        security.authenticate({}, "GET", "/api/customers/")
    assert error.value.status_code == 503
