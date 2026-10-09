"""Single-tenant delegated Entra access. Preview identities are never verified."""
from contextvars import ContextVar
from functools import lru_cache
from uuid import UUID, uuid4
from secrets import compare_digest

import jwt
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.core.config import settings

actor_context = ContextVar("audit_actor", default={"id": "unknown", "verified": False, "request_id": ""})
ROLES = {"NOC.Viewer", "NOC.Operator", "NOC.Admin"}


def auth_configuration():
    preview = settings.AUTH_MODE == "preview" and settings.ENVIRONMENT == "development"
    configured = settings.AUTH_MODE == "entra"
    for value in (settings.ENTRA_TENANT_ID, settings.ENTRA_API_CLIENT_ID, settings.ENTRA_SPA_CLIENT_ID):
        try:
            UUID(value)
        except (ValueError, TypeError):
            configured = False
    return {"mode": "preview" if preview else "entra", "configured": preview or configured,
            "tenant_id": settings.ENTRA_TENANT_ID, "client_id": settings.ENTRA_SPA_CLIENT_ID,
            "scope": f"api://{settings.ENTRA_API_CLIENT_ID}/{settings.ENTRA_SCOPE}"}


@lru_cache(maxsize=4)
def key_client(tenant_id):
    # Never use a URL supplied in the token. Trust only this configured tenant.
    return jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys", timeout=5)


def validate_token(token):
    try:
        key = key_client(settings.ENTRA_TENANT_ID).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"],
                            audience=settings.ENTRA_API_CLIENT_ID,
                            issuer=f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}/v2.0",
                            options={"require": ["exp", "iat", "nbf", "iss", "aud", "tid", "oid", "azp", "scp"]})
        if claims["tid"] != settings.ENTRA_TENANT_ID or claims["azp"] != settings.ENTRA_SPA_CLIENT_ID:
            raise jwt.InvalidTokenError("Wrong tenant or client")
        UUID(claims["oid"])
        if settings.ENTRA_SCOPE not in claims["scp"].split():
            raise HTTPException(403, "Required API scope missing")
        roles = claims.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise jwt.InvalidTokenError("Invalid roles")
        if not ROLES.intersection(roles):
            raise HTTPException(403, "NOC role assignment required")
        return {"id": claims["oid"], "verified": True, "roles": roles}
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, "Identity provider temporarily unavailable")
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        raise HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})


def authenticate(headers, method, path):
    if path == "/api/monitoring/events" and method == "POST":
        secret = settings.MONITORING_INGEST_TOKEN
        if len(secret) < 32:
            raise HTTPException(503, "Monitoring intake credential is not configured")
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not compare_digest(token.encode(), secret.encode()):
            raise HTTPException(401, "Invalid monitoring credential")
        return {"id": "prtg-bridge", "verified": True, "roles": ["NOC.Operator"]}
    config = auth_configuration()
    if not config["configured"]:
        raise HTTPException(503, "Microsoft 365 access is not configured")
    if config["mode"] == "preview":
        actor = {"id": "local-preview", "verified": False, "roles": ["NOC.Admin"]}
    else:
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 16384:
            raise HTTPException(401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
        actor = validate_token(token)
    roles = set(actor["roles"])
    if (path.startswith("/api/audit") or (path.startswith("/api/monitoring/mappings") and method not in {"GET", "HEAD"})) and "NOC.Admin" not in roles:
        raise HTTPException(403, "Administrator role required")
    if method not in {"GET", "HEAD", "OPTIONS"} and not roles.intersection({"NOC.Operator", "NOC.Admin"}):
        raise HTTPException(403, "Operator role required")
    return actor


class AccessMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        public = {"/", "/health/ready", "/api/auth/config"}
        if path in public or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        from starlette.datastructures import Headers
        request_id = str(uuid4())
        try:
            actor = await run_in_threadpool(authenticate, Headers(scope=scope), scope["method"], path)
        except HTTPException as exc:
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
            return await response(scope, receive, send)
        actor["request_id"] = request_id
        context_token = actor_context.set(actor)
        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)
        try:
            await self.app(scope, receive, send_with_id)
        finally:
            actor_context.reset(context_token)
