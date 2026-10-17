# Anker SharePoint / OneDrive energy synchronization

The connector reads saved XLSX revisions through Microsoft Graph. It never writes
to Excel, sends email or infers physical power state. The default check interval
is 60 seconds; the Energy page refreshes every 30 seconds. This is near-real-time
workbook synchronization, subject to Excel save/upload delays and Graph retries.

The supplied workbook link identifies this target (sharing query parameters are
deliberately not retained):

- SharePoint host: `ankersupport.sharepoint.com`
- Site: `/sites/AFLNOCTEAM`
- Document library: `Shared Documents`
- File within the library:
  `General/Tracker/Site-Energy/2026/SiteEnergyTracker-Q1-5.4.26.xlsx`

Graph drive/item IDs have not yet been resolved. They must come from the tenant;
the `d=` parameter in an Excel sharing link is not the Graph drive item ID.

## 1. Check your Anker access

Sign in to [Microsoft Entra](https://entra.microsoft.com) with the Anker account,
and select the Anker directory. Open **Entra ID → Users → All users**, select your
account and inspect **Assigned roles**. Activate an eligible PIM role when required.
Creating an app registration may be permitted for a normal member; that does not
mean the account can consent to Graph application permissions.

For Microsoft Graph application permissions, use a Global Administrator,
Privileged Role Administrator, or a custom role explicitly authorized to grant
the requested permissions. Application Administrator/Cloud Application
Administrator alone excludes Graph application permissions. See
[Microsoft's consent requirements](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent).

## 2. Register a dedicated workbook reader

Under **App registrations → New registration**, create **AFL NOC Energy Reader**:

1. Single tenant: accounts in the Anker organizational directory only.
2. Leave the redirect URI blank; this is a background application.
3. Record the **Directory (tenant) ID** and **Application (client) ID**.
4. Add **Microsoft Graph → Application permissions → Sites.Selected**.
5. Have the authorized administrator grant admin consent.
6. Create a client secret under **Certificates & secrets**, choose the company's
   approved expiry, and enter its **value** directly in protected server
   configuration. Record the expiry for rotation. Do not share it in chat or Git.

The reader uses the
[client credentials flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow)
and the `https://graph.microsoft.com/.default` scope. Its registration is separate
from the browser SPA/API registrations used for employee sign-in.

Do not grant the reader `Files.ReadWrite.All`, `Sites.ReadWrite.All` or
`Sites.FullControl.All`. `Sites.Selected` grants no site access by itself.

## 3. Grant read access and resolve the file

Using an approved administrator/provisioning identity in Graph Explorer or the
company's Graph administration tooling, resolve:

```http
GET https://graph.microsoft.com/v1.0/sites/ankersupport.sharepoint.com:/sites/AFLNOCTEAM
```

Record its `id` as `SITE_ID`. The provisioning identity needs the permissions
and site membership required by
[Create site permission](https://learn.microsoft.com/en-us/graph/api/site-post-permissions?view=graph-rest-1.0).
In a delegated workflow this includes `Sites.FullControl.All`, a SharePoint
Administrator or higher role, and membership of the target site. These are
provisioning permissions, **not permissions for the reader application**.

Grant the reader access to this site:

```http
POST https://graph.microsoft.com/v1.0/sites/SITE_ID/permissions
Content-Type: application/json

{
  "roles": ["read"],
  "grantedToIdentities": [{
    "application": {
      "id": "READER_APPLICATION_CLIENT_ID",
      "displayName": "AFL NOC Energy Reader"
    }
  }]
}
```

Keep the returned permission ID for revocation. This permits reading the selected
site, not just the workbook. If company policy requires file-only scope, Anker IT
can instead provision `Files.SelectedOperations.Selected` with a read grant to
the exact workbook; the connector still uses drive/item IDs. See
[Selected permissions](https://learn.microsoft.com/en-us/graph/permissions-selected-overview).

List the site's libraries and select the drive whose `webUrl` corresponds to
`Shared Documents`:

```http
GET https://graph.microsoft.com/v1.0/sites/SITE_ID/drives
GET https://graph.microsoft.com/v1.0/drives/DRIVE_ID/root:/General/Tracker/Site-Energy/2026/SiteEnergyTracker-Q1-5.4.26.xlsx
```

Record the chosen drive's `id` and the workbook's `id`. Verify the returned
filename and `parentReference.driveId`. IDs remain usable across ordinary renames;
moving the workbook to another drive requires updating configuration. A change
of configured source hides the previous source's report until the new source has
a valid snapshot.

## 4. Server configuration

Live sync requires `ENVIRONMENT=production`, `AUTH_MODE=entra` and valid employee
sign-in registration IDs. The public shared-password review environment is still
a development preview and cannot activate the live reader. Complete company
sign-in and access acceptance using [the access guide](access-and-monitoring.md).

The current demo Basic-auth gateway strips `Authorization` before proxying to
the preview API. It must not be used in front of the Entra bearer-token flow.
For live data, use the production frontend behind an HTTPS ingress that preserves
bearer tokens. Funnel can remain the HTTPS transport if it is pointed at that
production frontend rather than the demo password gateway; register its exact
`https://HOST/redirect.html` URI on the SPA registration.

Add the non-secret source configuration to protected production configuration:

```dotenv
ENERGY_ONEDRIVE_ENABLED=true
ENERGY_GRAPH_TENANT_ID=ANKER_TENANT_UUID
ENERGY_GRAPH_CLIENT_ID=READER_APPLICATION_UUID
ENERGY_GRAPH_DRIVE_ID=RESOLVED_DRIVE_ID
ENERGY_GRAPH_ITEM_ID=RESOLVED_WORKBOOK_ITEM_ID
ENERGY_SYNC_INTERVAL_SECONDS=60
```

Set `ENERGY_GRAPH_CLIENT_SECRET` there using an editor, with the real secret
value. The production Compose reference injects it only into `energy-sync-worker`.
Keep the configuration file mode 0600. Do not publish expanded Compose config;
use `config -q`. The API receives only the non-secret source settings.

The worker also supports `ENERGY_GRAPH_CLIENT_SECRET_FILE` for a secret-manager
mount. To use it, add the read-only mount and that variable to the worker service
in the finalized server configuration, and leave the environment secret empty.
Ensure UID 10001 can read the mounted file. Never place it under a served directory.

## 5. Deploy and verify

Build reviewed backend/frontend images, back up the database and both document
volumes, then apply migration **`14c8e2f7a901`** using the usual migration job.
The production Compose reference includes the reader under the `energy-sync`
profile. Against the finalized server configuration:

```bash
sudo docker compose --env-file /etc/noc-platform/production.env -f compose.production.yaml config -q
sudo docker compose --env-file /etc/noc-platform/production.env -f compose.production.yaml run --rm --no-deps migrate
sudo docker compose --env-file /etc/noc-platform/production.env -f compose.production.yaml --profile energy-sync up -d --no-build --wait
```

`compose.production.yaml` refers to the finalized server deployment described in
the Rocky runbook. It is not the current shared-preview configuration.

As an administrator, open **Energy operations**, inspect the source status and
select **Sync now**. The request queues a worker check; it does not make Graph
requests in the web handler. Check the worker's health/logs, `last_checked_at`,
`last_success_at` and the workbook's `source_modified_at`. Make a known authorized
workbook edit, wait for Excel to save it to SharePoint, then verify the report
changes and a new revision is recorded. Actual tenant acceptance cannot be
claimed until this check passes with the real file and granted identity.

## Behavior and recovery

- ETags avoid downloading an unchanged file. A second metadata check rejects a
  file that changed while its content was downloading.
- Downloads are capped at 10 MB, expanded workbooks at 40 MB / 2,000 entries and
  parsed operational records at 50,000. The RawData header contract is shared
  with manual imports.
- Network errors, lost grants, missing files, invalid workbooks and disk failures
  retain the last valid report. The UI shows the error and freshness instead of
  presenting it as live. Microsoft `Retry-After` and bounded exponential backoff
  apply even to administrator-requested refreshes.
- Only one worker can publish at a time, using a PostgreSQL advisory lock. A
  refresh queued during a download is retained for the next check.
- Original XLSX snapshots are retained in
  `DOCUMENT_STORAGE_ROOT/energy_sources/<source-hash>/<content-hash>.xlsx`, within
  the protected private-document volume. Include them in backups and agree
  retention/capacity policy before enabling continuous operation.
- `energy_source_revisions` links each remote version to an immutable normalized
  import and its checksum. Reverting to an earlier saved version correctly
  reactivates its previous import; it does not pick the most recently inserted
  workbook by timestamp. Duplicate bytes do not create duplicate imports.
- Authorized administrators can download a verified original from
  `GET /api/energy/sync/revisions/{revision_id}/download`; viewer/operator roles
  cannot. Downloads require the original checksum to match.
- Automatic mode rejects manual workbook replacement. To pause it, set the
  enabled flag false, retain the source IDs, and recreate API/worker containers.
  The last accepted snapshot remains available as cached data.
- Graph tokens, client secrets and presigned download URLs are never returned
  by the API or intentionally logged. Redirect downloads receive no bearer token.

There are no webhooks in this slice. A shorter polling interval cannot make an
unsaved workbook or stale operator reading into live power telemetry. Webhooks
with subscription renewal/reconciliation can be added if the measured polling
delay is insufficient; the saved workbook remains the source of truth.

If Graph consent is unavailable, use [hourly desktop delivery over SSH](energy-file-delivery.md) instead. Enable only one synchronization transport at a time.
