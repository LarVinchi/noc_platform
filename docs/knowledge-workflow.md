# Approved-source knowledge workflow

For derived-only OneDrive ingestion, see [linked-onedrive-intake.md](linked-onedrive-intake.md).
The intake stores metadata and extracted text; original OneDrive files stay at their source.

The connected workflow is a stateless question against explicitly selected,
approved UTF-8 TXT or text-based PDF revisions. The private worker supports
lexical retrieval or explicitly configured persistent Chroma/Gemini embeddings.
Knowledge displays the actual worker index identity. It does not enable case-aware
generation in the floating assistant, RCA drafts, DOCX extraction or automatic actions.

PDFs are limited to 5 MB and 100 text-bearing pages, with original-byte hashes and
page/line citations. Scanned, encrypted, partially blank or oversized PDFs fail
approval rather than silently omitting pages. The pilot parser still requires
process isolation and resource limits before accepting arbitrary public files.
Worker installations need `requirements-noc-vectors.txt` for PDF/vector support.

The collector exports metadata and supported extractions from explicitly approved
folders on the sync PC. Admin import and collection-scoped machine delivery are
implemented. Source sharing and approval remain manual; neither scan nor import
grants NOC access. No direct Microsoft Graph document connector is active.

## User workflow

1. Upload a non-sensitive TXT runbook (maximum 200 KB; lines at most 2800 characters)
   or text-based PDF (maximum 5 MB). Inspect its original content and current revision.
2. In Knowledge, an administrator selects **Review / approve**, records the
   decision reason, and approves that exact immutable revision. Merely writing
   APPROVED inside a file does not grant knowledge approval.
3. Select one or more approved sources (maximum ten) and ask a question. The
   backend constructs the actual version/hash allowlist after checking access.
4. Inspect the answer's citations, original line ranges, version/hash and original
   revision download. An answer is not an operational instruction or an approval.
5. An unrelated question should abstain. Revoke the source and confirm it cannot
   be queried. A newly uploaded revision requires its own approval; an older
   approved revision does not authorize the new content.
6. After changing the worker retrieval backend or embedding model/dimensions,
   use **Reindex** for previously approved revisions. Existing lexical approval
   does not create vectors. Failed indexing retains the previous working generation.
   Indexing with Gemini embeddings sends the approved source chunks to that provider.

## Authorization and failure behavior

Existing sign-in and document ownership/sharing rules remain authoritative. An
authenticated viewer can ask a read-only knowledge question; only administrators
can approve or revoke sources. Browser requests contain document IDs, never a
trusted source allowlist or provider/service credentials.

Approval publishes the index before committing NOC approval. Publication failure
does not approve the new source. Revocation commits the NOC deny before notifying
the worker. Failed notification cannot restore source access. The NOC backend
rechecks approval, current revision and user access after generation; a mid-request
change discards the answer. The worker also rechecks its durable registry before
and after retrieval/generation. It filters exact source versions before ranking.

Worker responses have bounded size and validated request/citation identities.
The query budgets cover embedding (30 seconds) plus generation (60 seconds):
NOC worker call 105 seconds, frontend proxy 110 seconds, gateway/local preview
proxy 115 seconds and browser call 120 seconds. Other API routes retain their
existing proxy timeouts.
Invalid citations, provider timeouts/quotas and blocked/truncated JSON responses
produce an explicit unavailable state rather than a fabricated answer. Minimal
audit events store actor, source versions, result and model/index identity, but not
questions, generated answer text or credentials. Review reasons are retained.

`/knowledge/status` distinguishes configured adapters from a live provider probe.
Configured does not mean the Gemini key/model/quota has been verified. Semantic
answer correctness still requires a real-provider evaluation; structural citation
checks do not prove every generated claim is supported.

## Deployment

The existing NOC build, migration and tested-release pipeline remains unchanged.
Migration `36e0a4b9c123` adds approval and audit tables. The feature defaults off.
Frontend changes require no provider secret or new frontend dependency.

Deploy the separately reviewed RAG worker privately, with a persistent index and
an explicitly approved model. Only it receives `GEMINI_API_KEY`. Configure the NOC
API with `KNOWLEDGE_ENABLED`, `KNOWLEDGE_SERVICE_URL` and the matching separate
`KNOWLEDGE_SERVICE_TOKEN`. Do not publish the worker's port through the public
gateway. Use private networking or TLS, protected runtime secrets and backups.
The worker is not installed automatically by the existing NOC release agent.

The two repositories must be reviewed together against this contract. Local UI
tags are not deployed release identities. Do not enable the integration on company
documents until the live evaluation, access tests and normal CI gates pass.

## Local review without Docker/PostgreSQL

In the parent developer workspace, `start-rag-workflow.cmd` starts a dedicated
loopback workflow at `http://127.0.0.1:15178/knowledge`. It uses the real document
and knowledge routes against a separate local SQLite catalogue, the real private
worker, and your locally configured Gemini provider. Other pages retain synthetic
read-only fixtures. A persistent LOCAL RAG TEST banner identifies the mode.

This harness lives outside the application checkout and is not a production entry
point. It does not validate PostgreSQL migrations, Entra or the deployed network;
those remain CI/server checks. The ordinary design preview on port 15177 remains
synthetic and never loads a provider key.
