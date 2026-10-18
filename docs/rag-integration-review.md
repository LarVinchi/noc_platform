# NOC integration review

Reviewed 2026-10-18 against commit `5e984d9`, the NOC knowledge workspace and
`docs/document-storage-and-ftth-design.md`. Static source review only: no provider
requests, embeddings, company document uploads or runtime deployment were performed.
Work is isolated on `feature/noc-integration-review`.

## Assessment

Reuse the PDF/Word extraction, table handling, question contextualization and RCA
drafting components behind a private service contract. Keep the existing NOC UI,
identity, document catalogue, revision storage and operational records authoritative.
The current standalone service is a proof of concept, not an authenticated NOC backend.

## Findings that block direct connection

| Priority | Evidence | Required integration change |
| --- | --- | --- |
| High | `main.py:522-532`, `594-654`: chat, RCA creation/revision/export have no user authentication; thread IDs come from requests | Authenticate service calls and bind every conversation/draft to the NOC actor and permitted case. Unpredictable IDs alone do not establish ownership. |
| High | `main.py:53-56`, `138`: one unfiltered retriever queries the shared index | Mandatory filters for permitted approved document **versions** before retrieval/top-k; reject unscoped queries and recheck access before releasing answers/citations/downloads. |
| High | `main.py:108-119`: instructions explicitly allow ordinary general answers when evidence is absent | Operational knowledge mode must return insufficient evidence rather than assert company facts from general knowledge. Add evidence-required answer evaluation. |
| High | `main.py:646-650`: output filename includes request-controlled TT number; mutable shared working-directory output | Generate confined storage keys and immutable draft revisions in NOC document storage. Review the full path and platform-specific filename behavior before enabling exports. |
| High | `ingest.py:251-255`: old chunks are deleted before replacement embeddings complete | Stage replacement version chunks, verify success, then publish atomically. Retain old approved content on failure; clean partial staged chunks safely. |
| High | `main.py:40-41`, `ingest.py:225`: Gemini receives generation/embedding content | Confirm organizational approval for that provider and data categories before sending documents or incident/customer facts. Keep provider configuration and credentials server-side. |
| Medium | `main.py:63`, `140`, `516-519`: returned citations are filenames only, although PDF page metadata exists during extraction | Return structured document ID, version ID, SHA-256, chunk ID and page/section/table locator. Validate citations against the exact retrieved authorized chunks. |
| Medium | `main.py:151-153`, `324-326`: memory-only chat/draft state | Durable bounded sessions with actor ownership, retention, deletion and concurrent-edit handling; keep messages scoped when permissions change. |
| Medium | `ingest.py:63`, `85-122`: only PDF/DOCX; table metadata exists, DOCX text lacks precise section/paragraph locators | Add source-version identity and locators. XLSX/CSV, OCR and completeness auditing are separate missing capabilities; do not claim they exist. |
| Medium | `ingest.py:156-164`, `253-257`: MD5 fingerprints and non-atomic manifest updates | Use SHA-256 source identity, durable idempotent ingestion jobs and atomic checkpoint publication. Distinguish source update from approval. |
| Medium | `main.py:360`, `568-592`: incident lookup reads a local spreadsheet | Feed authorized incident/order facts from the NOC relational database. SQL remains authoritative for outage duration, MTTR and totals. |
| Medium | `main.py:511-514`, `535-552`, `618-621`: unbounded text/session fields and weak date/identifier validation | Add request-size, length, timeout, quota and structured-fact validation. Never derive operational fields solely from a generated narrative. |
| Medium | `main.py:658-665`: health reports static OK; startup mounts absent `static/` directory | Separate process liveness, index readiness and model availability. Start without external model calls; provide truthful unavailable status. |

Repository root contains `README.md`, `main.py`, `ingest.py`, `.gitignore` and
`github_repo.zip`. The archive contains the missing `requirements.txt`, `.env.example`
and `static/index.html`. The documented clean-clone startup is therefore incomplete.
Do not blindly unpack over the root: archived Python files differ from checked-in
copies. Reconcile and track one canonical source tree, pin dependencies, and add CI.
Model identifiers are hardcoded; their live availability has not been verified.

## Proposed integration boundary

```text
Existing NOC chat / case assistant
    -> NOC FastAPI: authenticate actor, authorize case and approved source versions
    -> private RAG adapter: retrieve only within trusted allowed versions
    -> bounded model generation using retrieved evidence
    -> NOC: validate citations, persist audit and return answer / insufficient evidence
```

NOC APIs own authentication, authorization, conversations, document versions,
case facts and reviewed draft storage. The RAG worker owns extraction, embedding,
indexing, retrieval and model invocation. Do not embed its standalone UI or merge
its `/api/chat` directly into the platform. Keep model SDK dependencies in a separate
service image and do not expose that worker directly to browsers.

Treat source text as untrusted data, including instructions embedded in documents.
Prompt wording is not an authorization boundary. The worker must require a trusted
service credential; browser-supplied actor IDs or source allowlists are not trusted.

## Contract to agree before runtime implementation

Trusted query input:

```json
{
  "request_id": "uuid",
  "conversation_id": "server-issued actor-bound uuid",
  "question": "bounded question",
  "allowed_versions": [{"document_id": "uuid", "version_id": "uuid", "sha256": "64 hex characters"}],
  "case_context": {"kind": "incident", "id": "uuid", "facts": {}}
}
```

The NOC server builds the allowlist and case facts after authorization. The private
adapter rejects missing scope, retired/revoked versions and unknown index versions.
Empty scope returns insufficient evidence without a generation call.

Response contains `request_id`, `status` (`answered` or `insufficient_evidence`),
bounded `answer`, structured `citations`, and model/index versions. Each citation
pins document/version/hash/chunk plus an exact locator and evidence excerpt.
No worker-supplied file path or download URL is exposed directly to the browser.

Ingestion accepts only a registered source version with SHA-256 and approval state.
Jobs report queued/extracting/completeness-check/indexing/ready/failed states and
counts. Failed/incomplete/quarantined versions remain visible in the catalogue
and do not become eligible for normal knowledge retrieval.

RCA input uses authorized NOC facts, a reviewed template version and explicit
missing required facts. Responses remain drafts. Generation, operator edits,
review and final approval are separate persisted events; no automatic finalization.

## Delivery sequence and acceptance tests

1. Repair packaging and isolate the service factory/provider adapter. Add pinned
   dependencies, configuration validation and offline tests with a fake provider.
2. Add approved-version ingestion and permission-filtered retrieval with structured
   citations; test private/shared documents, same-name files, version changes,
   partial embedding failures, deletions and permission revocation.
3. Connect the existing NOC assistant behind an explicit feature flag. Verify
   ownership of conversations, case switching, empty evidence, unrelated questions,
   document prompt injection, timeouts, unavailable models and provider quotas.
4. Add reviewed RCA drafting against the approved template. Test missing facts,
   invalid dates, path confinement, export ownership, concurrent revisions and
   human approval. Do not substitute this for the separate completeness tool.
5. Use a small approved evaluation set before enabling real company data. Track
   evidence correctness, retrieval recall, unsupported assertions, citation accuracy,
   latency and usage cost. RAG service health/resource use can join the new host
   monitoring page once that service is deployed.

The existing NOC `GET /api/knowledge/status` should continue to report disconnected
and keep Ask disabled until the relevant capabilities and access tests actually pass.
