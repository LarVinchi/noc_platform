# Private document catalogue preview

Open **Documents** at http://localhost:5173/documents after starting `dev.ps1`.
The additive migration creates a catalogue and immutable file-version records.
The single command starts the same preview services and mounts the new private
document volume outside `/static`. Existing database and installation files are
retained.

## What is implemented

- PDF, DOCX, XLSX, UTF-8 CSV/TXT, JPEG and PNG uploads, up to 20 MB per file.
- Type/content validation, bounded Office archives, encryption/macro rejection
  and generated UUID storage paths independent of submitted filenames.
- Owner/admin access by default. Only administrators can share with **all NOC
  roles** or revoke that sharing. Shared readers cannot modify another user's
  revisions. A hidden record returns 404 on detail and download as well as being
  omitted from catalogue results.
- Document types, title search, type filters, paginated results and optional
  FK-backed FTTH order/service/incident links. An activated order supplies its
  service and customer; a conflicting service link is rejected.
- New revisions retain older original bytes, filename, SHA-256, size, MIME type,
  actor, time and source/change note. Reuploading identical current bytes returns
  the existing revision rather than creating another one. A new catalogue entry
  intentionally represents a separate document, even if its bytes match another.
- Authorized attachment downloads recheck size/checksum and disable caching.
  Private storage keys are not exposed in catalogue responses.
- Transactional audit records for registration, revisions and sharing changes.
  Database triggers reject updating/deleting committed version records.

Upload an original, select its document type, describe its source and optionally
link it to an order, service or incident. Use **Versions / links** to download any
revision, add a correction as a new revision or change sharing as an administrator.
Selecting `customer_handover` categorizes an uploaded source; it does not approve
the document or imply delivery to a customer.

## Storage and operational limits

`DOCUMENT_STORAGE_ROOT` configures the private filesystem adapter. Preview uses
`/app/private_documents`, persisted in the Compose `preview_private_documents`
volume. Bytes are stored as `originals/{document_id}/{version_id}/source.ext`.
This adapter uses same-filesystem hard links for immutable publication and
requires a filesystem supporting hard links. Metadata lives in PostgreSQL.

An unsuccessful or ambiguous database commit may leave an unreferenced immutable
file. Retain these for reconciliation; never delete bytes on an ambiguous commit
that may have succeeded. A future manifest reconciliation job should identify
orphans with an agreed retention window. Staging files are removed on handled
validation failures. Crash recovery/cleanup and filesystem durability must be
validated for the production storage provider.

Format validation is not malware scanning or a completeness audit. Files remain
labelled **Unreviewed source**, **Not indexed**, and **Malware scan not integrated**.
This slice adds no document approval, extraction, OCR, embeddings, AI answer or
OneDrive connection. Do not treat its uploads as approved RAG knowledge.

Access currently uses owner plus explicit NOC-wide sharing. Department-specific
grants, source ACL reconciliation and entity-level access must be added before
broader departmental rollout. Linking a record does not automatically broaden
access. A pre-activation order link is retained; its later service activation is
not yet backfilled into existing document links.

Existing installation photos/acceptance PDFs remain in their original protected
static storage. They have not been moved into the catalogue. A verified migration
manifest and compatibility downloads are still needed; existing workflow URLs
remain usable while that migration is prepared.

Production also requires request-body limits before multipart parsing, malware
scanning/quarantine, isolated parser workers/timeouts, granular permissions,
backups of both file volumes plus metadata, restore testing and retention rules.
Parsing currently runs within the API request; the per-file limit does not replace
an ingress request-size limit. Attachments are untrusted source files.

## Validation

Database-backed tests cover immutable history, identical-version retries, original
downloads, audit actors, private listing/detail/download denial, sharing/revocation,
non-owner edits, invalid/oversized formats, missing record links, unsafe filenames,
checksum tampering and valid PDF/Office/image files. Test files use an isolated
temporary directory and database writes roll back.

The next milestone is explicit FTTH stage/acceptance history, installation totals
and pre/post-activation incident links. Approved MTN handover rendering and the
colleague's RAG/completeness tools remain pending inputs, as described in
[the complete design](document-storage-and-ftth-design.md).
