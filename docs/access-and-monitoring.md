# Access, audit and monitoring foundation

Local preview remains available at http://localhost:5173 after `dev.ps1 start`.
Select **Open local preview**. The passcode simulation was removed: preview is
explicitly unauthenticated, and its audit actor is `local-preview`, unverified.
Compose publishes only loopback ports and enables preview mode only in development.

## Microsoft 365 configuration

Production defaults to Entra access and returns 503 for protected routes until
registration identifiers are configured. `AUTH_MODE=preview` cannot bypass access
in `ENVIRONMENT=production`. Health and non-secret sign-in configuration remain public.

Create two single-tenant Entra registrations: a browser SPA and an API. Set API
`requestedAccessTokenVersion=2`; expose delegated scope `access_as_user` with the
default application URI `api://<API-client-ID>`. Grant the SPA that permission and
admin consent. Register the exact SPA redirect URI
`https://<NOC-host>/redirect.html` (local testing: `http://localhost:5173/redirect.html`).
The dedicated redirect bridge is bundled into the frontend production output.
Register the app origin as the logout return URI as applicable.

Define API application roles `NOC.Viewer`, `NOC.Operator`, `NOC.Admin`, assign
company users/groups, and require assignments. Viewer can read operational data;
operator can write; admin can read audit history and create sensor mappings.
Permissions apply at the API boundary. Existing forms may still appear to a
viewer, but writes are rejected. Finer installer/customer roles remain outstanding.

Backend settings:

```dotenv
ENVIRONMENT=production
AUTH_MODE=entra
ENTRA_TENANT_ID=<tenant UUID>
ENTRA_API_CLIENT_ID=<API application UUID>
ENTRA_SPA_CLIENT_ID=<SPA application UUID>
ENTRA_SCOPE=access_as_user
CORS_ORIGINS=["https://<NOC-host>"]
MONITORING_INGEST_TOKEN=<separately generated random secret, at least 32 characters>
```

Use HTTPS and a same-origin reverse proxy for `/api` and `/static`. Do not expose
the storage directory through an independent web server: that bypasses API access
controls. Static PDFs/images and API docs require the same access check. The UI
downloads acceptance PDFs with its bearer token. Browser sign-in uses MSAL; API
validates RS256 signature, expiry, issuer, audience, tenant, client, delegated scope
and roles, with signing keys obtained from a fixed configured Microsoft URL.
Live tenant sign-in cannot be accepted as validated until the IDs are available.
See [Microsoft's sign-in and redirect bridge guidance](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/login-user)
and [PyJWT verification guidance](https://pyjwt.readthedocs.io/en/stable/usage.html).

## Audit records

The **Audit history** page shows committed database changes and request IDs. Database
triggers cover orders, installation metrics, incidents, activities, customers,
services, allocations, selected infrastructure, map links, mappings and observations.
They record inserts, updates and deletes in the same transaction. History begins
when the migration is applied; existing records are not retroactively attributed.
Snapshots use explicit field allowlists. Contact details, raw pasted requests,
free text and map geometry are excluded. An excluded-field change still creates
an event, but its before/after snapshots may appear identical.

Ordinary UPDATE/DELETE/TRUNCATE on the audit table is rejected. This is not proof
against a database owner/superuser who can disable triggers. Production must use
a separate migration owner and a least-privilege runtime role; independently
retained audit exports/backups and retention policy remain deployment gates.
Direct database changes are marked unattributed unless performed in a trusted
actor transaction. User-entered person/engineer names remain operational metadata;
the verified actor is the Entra object ID in the audit record.

## Monitoring workflow

Open **Monitoring**, select the existing cable, route or service and register its
PRTG sensor ID. IDs must use a namespace if multiple PRTG instances share this API.
In preview use **Preview Down**, then check Incidents, Dashboard and Audit history.
Mapped infrastructure alarms create service tickets from current allocations;
inventory routes with geometry show last-observed down alarms in FibreViz.
Alternative paths remain visible in impact analysis; this is potential impact.
Use **Preview Up** to record alarm clearance. It does not close the incident or
assert customer restoration. Confirm restoration through the incident workflow.

The machine endpoint is `POST /api/monitoring/events`, with
`Authorization: Bearer <MONITORING_INGEST_TOKEN>`. Its credential is separate from
user sign-in. If absent or short, intake is disabled; never put credentials in
query strings or map/UI data. `/api/monitoring/simulate` is enabled only in local
preview. No live PRTG connection or outgoing customer messages have been enabled.
For local bridge testing, add the token to the ignored root `.env` and restart
the stack. Preview simulation does not require a token.

Normalized example payload:

```json
{
  "event_id": "prtg-main:12345:transition-6789",
  "sensor_id": "12345",
  "state": "down",
  "observed_at": "2026-10-09T14:30:00+01:00"
}
```

Accepted states: `down`, `up`, `warning`, `paused`, `unknown`. Observation time must
include timezone. A producer/bridge must map PRTG status values and preserve the
same event ID and original observation timestamp when retrying. An identical
event returns `duplicate`; reuse with different content returns 409. Database
transaction locks serialize event IDs and sensors. Older/equal-time observations
are stored as `stale` and do not overwrite the latest state. Unmapped observations
are retained as `unmapped`, without creating incidents; new mappings apply to
future observations, not automatic replay. Existing active incidents are reused.

PRTG HTTP actions and placeholders vary with configuration/version: confirm the
installed version's payload and credential support. If it cannot send the bearer
header securely, use an internal authenticated bridge; do not weaken API access.
See [PRTG notification templates](https://manuals.paessler.com/notification_templates.htm)
and [notification placeholders](https://manuals.paessler.com/list_of_placeholders_for_notifications.htm).
TLS ingress, rate/body limits, token rotation, bridge delivery/retry monitoring,
cross-sensor correlation, flapping debounce, maintenance windows, sensor freshness,
and acknowledged/restored outage intervals remain outstanding. Last-observed state
is not a continuous health poll and cannot yet be used for authoritative SLA/MTTR.

## Validation

The milestone regression suite passes 47 tests against the isolated preview,
including existing provisioning, actual signed-token rejection, API role checks,
audit rollback/redaction/protection, alarm duplicates, older events and clearance.
Frontend lint/build pass. The preview health endpoints and redirect page respond.
Live tenant sign-in, a real PRTG producer and interactive browser acceptance are
still external acceptance gates.

Compatible frontend dependency updates reduced npm audit findings from 20 to 7
(5 high, 2 moderate). The remaining Tailwind dependency findings require a
separate upgrade and visual acceptance; they remain a production release gate.
