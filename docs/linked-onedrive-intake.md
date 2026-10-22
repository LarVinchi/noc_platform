# OneDrive-linked document intake

Original PDFs, Word documents, spreadsheets and TXT files remain in OneDrive on the existing sync PC. The NOC intake stores metadata and extracted text, then sends explicitly approved extraction revisions to the private RAG worker. It does not upload or permanently retain original-file copies. Existing direct uploads to Documents retain their existing storage behavior.

## What is ready

* Admin-only `/documents/intake`: collection creation, one-second copy feedback, private JSON report import, extraction previews, source hashes, duplicate-origin hints, observation freshness, pause/resume and explicit audience controls.
* Read-only collector export on the sync PC, without Gemini credentials. TXT and text-based PDF extraction are supported. DOCX/XLSX/CSV are inventoried but their contents are not yet eligible for RAG.
* Dedicated machine endpoint `/api/document-intake/ingest`, with its own bearer token restricted to one configured collection. The token cannot sign into the app or use Knowledge. Browser import requires an administrator identity instead.
* Atomic report import, immutable revision identity, replay detection, out-of-order rejection, extraction checksums, private-by-default documents and recorded import events. A changed original hash **or** changed extraction creates an unapproved revision.
* Missing files block retrieval only after a complete inventory. Partial scans retain absent sources. Read failures/placeholders block previously seen sources. Freshness defaults to 24 hours; an old replay does not renew it. Pause blocks every source in that collection.
* Original and extracted-text SHA-256 values are separate. The original hash is attested by the trusted collector; NOC cannot independently hash original bytes it never receives. Extraction integrity is checked by NOC and again by the RAG worker.

## First local pilot

1. On the development PC, start the existing `start-rag-workflow.cmd`. Open `http://127.0.0.1:15178/documents/intake` and choose **Open design preview** if prompted. This harness uses a local administrator identity and private SQLite data; it is not a production sign-in bypass.
2. Create a collection, then **Copy ID**. Collection IDs belong to the environment where they were created: create a separate collection after eventual server deployment.
3. On the PC that syncs the approved OneDrive folder, obtain the collector source code. Do not copy the developer's `.env.noc.local`, provider key, private index or uploaded documents. From the `rag-system` directory install:

   ```powershell
   python -m venv "$env:LOCALAPPDATA\AFL-NOC-Collector\python"
   & "$env:LOCALAPPDATA\AFL-NOC-Collector\python\Scripts\python.exe" -m pip install -r requirements-collector.txt
   ```

4. Export one small approved folder. Replace the root and UUID placeholders:

   ```powershell
   & "$env:LOCALAPPDATA\AFL-NOC-Collector\python\Scripts\python.exe" scripts/export-linked-folder.py --root "C:\Approved OneDrive Folder\Runbooks" --collection-id "COLLECTION-UUID" --outbox "$env:LOCALAPPDATA\AFL-NOC-Collector\outbox"
   ```

   The output is a private `<run-id>.json` report containing relative paths, hashes and extracted text. Keep the outbox outside the source folder and out of Git. No original-file blobs or provider credentials are included. Root folders are explicit; the collector does not scan the whole OneDrive account.

5. Securely bring that JSON report to the development PC and use **Import collector report**. Inspect the extraction and check the original on the sync PC. In **Knowledge**, record a review reason and approve the exact revision. Approval can send its extracted text to Gemini for embeddings. A scan/import never approves a source automatically.
6. Ask a supported question and inspect the citation. Then change the synthetic source and export/import again: the new revision must require approval. Test pause/resume and an unsupported question before using real procedures.

Use a synthetic runbook for this pilot. Copying a report temporarily between PCs is only needed while the application remains local to the developer machine. The collector should not connect to the developer's loopback URL from another PC.

## Server and authenticated collector setup

Do this only after deployment review and the normal CI/release process. The changes remain disabled by default. No production migration, token installation or source-PC enrollment has been performed by this local work.

* Apply migration `47f1b5c0d234` through the existing release migration stage; it follows `36e0a4b9c123`.
* Deploy the separately configured private RAG worker with persistent derived storage and `requirements-noc-vectors.txt`. Keep the Gemini key exclusively in that worker. Enable the existing `KNOWLEDGE_*` integration separately.
* Enable `LINKED_DOCUMENTS_ENABLED=true` for the API. The reviewed review/production Compose definitions now forward the optional `KNOWLEDGE_*` and `LINKED_*` values, disabled by default. Put values in the protected server environment file and recreate the API through the normal deployment process. Do not edit generated release contents.
* Create the server collection in the intake UI. Configure its UUID as `LINKED_COLLECTOR_COLLECTION_ID`.
* Generate a dedicated collector token directly into a protected file:

  ```powershell
  python scripts/create-collector-token.py --output "$env:LOCALAPPDATA\AFL-NOC-Collector\intake.collector-token"
  ```

  Supply the same value as the API's protected `LINKED_COLLECTOR_TOKEN` setting using your server secret-management procedure. Do not paste it into chat, source files or browser settings. This is separate from both Gemini and the NOC-to-RAG service credential. Only the sync PC needs the collector token; manual admin report import needs none.

* Use an HTTPS endpoint. The review gateway permits only POST on the exact machine-ingest path, forwards that bearer credential, caps the body and rate-limits it. Other browser routes retain their existing Basic gate. The API validates the collector token even in review mode. This exception must remain restricted to that exact route.
* Send an exported report from the sync PC:

  ```powershell
  python scripts/send-linked-report.py --report "C:\Private-Outbox\RUN-ID.json" --server "https://YOUR-NOC-HOST" --token-file "$env:LOCALAPPDATA\AFL-NOC-Collector\intake.collector-token"
  ```

  An acknowledgement is saved beside the report. If delivery fails, retry the same report file; do not edit it. Replays are safe and do not refresh observation age. The sender rejects non-HTTPS remote origins and redirects. Acknowledged outbox files can be removed under your local retention policy; never delete source OneDrive files as part of that cleanup.

Start with manual delivery, then schedule export and delivery hourly under the Windows user whose OneDrive sync is active. A disabled/offline sync client cannot prove cloud freshness. Schedule and retention on the actual PC still require its approved folder path and operational owner; this code does not install a task remotely.

## Storage and provenance limits

The default per-collection extracted-content quota is 25 MB, with a 5 MB report cap, 1,000 files per scan and 100 chunks/200,000 characters per extracted document. Historical derived revisions count toward that quota. Collection history and revision counts are capped. The worker refuses new indexing when free space would cross its 512 MiB reserve, checked on both registry and Chroma storage volumes.

The intake counter measures stored extraction JSON, not total disk usage. Metadata, PostgreSQL indexes, audit records, SQLite copies and vectors use additional storage. Chroma generations and original-path aliases are retained; automatic pruning/compaction is not implemented. Monitor disk usage and plan reviewed retention before scaling the pilot. A quota failure rolls back the whole import; it never deletes existing evidence or originals.

No OneDrive cloud link, cloud version ID or Microsoft 365 ACL is inferred from a Windows path. Source provenance shows the relative path, observation and both hashes. Optional current-file URLs must use an explicitly allowed tenant hostname in `LINKED_ONEDRIVE_ALLOWED_HOSTS`. They are current-file links, not verified historical downloads. Exact-version original download deliberately returns an unavailable response for linked sources.

Local verification on 22 October 2026 covered the collector, real NOC/private-worker routes and persistent Chroma with simulated provider transport; it also covered actual browser report import, previews, provenance, pause/resume and copy feedback in light/dark/mobile layouts. A separate live question against the already-approved synthetic runbook returned a Gemini answer with its matching source hash and line citation. PostgreSQL migration and Nginx configuration checks remain required in CI/Linux before deployment; this Windows PC has no Docker/PostgreSQL runtime.

Reviewers must verify audience rights. Sharing a source with NOC roles grants access to its extracted text independently of OneDrive permissions. Inherited Microsoft 365 access changes are not automatically detected by this local collector. Use only a deliberately approved folder/audience for the pilot. Future Graph integration must reconcile stable item/version IDs and permissions; archival copies should be an explicit retention exception, not the default for all OneDrive content.
