# Knowledge workspace and floating assistant preview

Start the platform with `./dev.ps1` and open http://localhost:5173.
The sidebar's **Knowledge assistant** opens `/knowledge` with a question panel
and an authorized source catalogue. A bottom-right **AI assistant** launcher is
available on every signed-in page. It opens a compact chat-style panel with
**Chat** and **Sources** tabs and a link to the full Knowledge workspace.
The launcher remains available inside topology full-screen mode.

To supply case context automatically, open a case. These buttons also open the panel:

1. **Response centre → Manage response → Ask about this incident**.
2. Or **FTTH operations → History / incidents → Ask about this FTTH case**.

On desktop the assistant floats above the current page without moving the layout.
On mobile it fills the screen, confines keyboard focus and uses **Minimize** to
return to the page. Escape minimizes it first without closing incident history.
The panel shows actual record facts and directly linked documents for an active
incident/order. Closing a case switches to the page context and clears its draft;
switching pages closes the assistant and clears context. Minimizing also clears
the draft. No local storage retains questions or case data.
Related service documents are not automatically included in this first slice.
Customer/service context remains follow-up work.

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
queries. The introductory chat bubble is static preview guidance, not a generated
answer; no artificial conversation history is added. Operational totals and MTTR
continue to come from SQL reports. Generated
handover/RCA/email drafts require human review and the approved templates.

## Verification

The backend status test verifies unavailable capabilities and private catalogue
counts. Browser checks exercise source inspection with an explicit UI fixture,
real incident/FTTH record context, floating desktop positioning, mobile focus
confinement and return, Escape, context/draft clearing and topology full-screen access,
absence of browser errors and no AI query submissions. The fixture is not stored
in the platform.
