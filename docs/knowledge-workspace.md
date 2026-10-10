# Knowledge workspace and case assistant preview

Start the platform with `./dev.ps1` and open http://localhost:5173.
The sidebar's **Knowledge assistant** opens `/knowledge` with a question panel
and an authorized source catalogue. The opening guide links to the case pages.

To open the companion drawer:

1. **Response centre → Manage response → Ask about this incident**.
2. Or **FTTH operations → History / incidents → Ask about this FTTH case**.

On wide screens the case and assistant remain side by side. On smaller screens
the assistant occupies the case panel; its close button returns to the case.
Escape closes the assistant first without closing incident history. The drawer
shows actual record facts and documents directly linked to that incident/order.
Related service documents are not automatically included in this first slice.
Customer/service drawers remain follow-up work.

## Available now

- Search document titles and inspect accessible catalogue records.
- Inspect the latest revision's filename, revision, timestamp and checksum.
- Download that exact revision through the existing authenticated, checksum-verified
  file endpoint. Source files are downloaded rather than rendered inline.
- Inspect real case facts and prepare a local question using suggested prompts.
- View truthful integration status through authenticated `GET /api/knowledge/status`.

The source browser shows the first 20 matching documents; use **Documents** for
pagination and the complete revision history. Existing owner/admin/NOC-sharing
rules apply to both source listing and downloads. There is no new public file URL.

## Connection boundary

This is an interface foundation. The RAG engine, document approval, extraction
and indexing are not connected. Sources are labelled unreviewed/not indexed,
indexed and approved counts are zero, and **Ask** remains disabled. No answers,
citations or generated documents are fabricated. Question drafts are local to
the mounted page/drawer, are cleared when switching cases and are neither saved
nor sent to an API/model. This preview does not provide a conversation history.

Next, integrate the colleague's RAG/completeness tools behind an adapter, add
reviewed source approval and validated extraction, then test permission-filtered
retrieval, exact version/page/sheet citations and answer quality before enabling
queries. Operational totals and MTTR continue to come from SQL reports. Generated
handover/RCA/email drafts require human review and the approved templates.

## Verification

The backend status test verifies unavailable capabilities and private catalogue
counts. Browser checks exercise source inspection with an explicit UI fixture,
real incident/FTTH record context, desktop positioning, mobile return, Escape,
absence of browser errors and no AI query submissions. The fixture is not stored
in the platform.
