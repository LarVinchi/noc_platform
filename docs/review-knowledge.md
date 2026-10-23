# Accepted-extraction review collection

The optional `/knowledge/review` workspace separates a complete **incident inventory** from a bounded **Ask the collection** answer. It is for the password-protected development review stack and administrators only. It does not mark these incident documents as production-approved knowledge or change the approved-source catalogue.

## Coverage and identity

Inventory checks every accepted text/table report in one immutable extraction snapshot, independently of embedding progress. MTN and MTNN are matched as the same label. Customer filtering matches report mentions; it does not establish a verified affected-service relationship. Groups use an explicitly extracted incident ID; dates/filenames alone never merge incidents. Missing or multiple IDs remain review items. Exact original SHA-256 duplicates retain all paths. Different cause text is shown side by side, with no automatically chosen authoritative revision. A missing cause is labelled missing, not inferred from the filename or an LLM.

Pagination and CSV cover every matching group. Counts disclose all input files, accepted reports, deferred files, matching report origins, grouped records, unresolved identities and missing causes. Complete coverage means the accepted extracted text snapshot was checked, not that omitted images, Word notes or deferred files were inspected. Inspect source evidence by immutable source/version/hash and table locator.

Questions use keyword retrieval over every accepted source by default, optional source filters, MTN/MTNN normalization, report diversity and version-pinned citations. At most six passages / 9,000 evidence characters are supplied to Gemini. This is a top-match summary and must not be presented as an exhaustive incident inventory. The worker builds a separate local lexical registry without embedding calls; existing Chroma/Gemini indexes remain separate and unchanged. Chroma ingestion can resume after quota resets. Gemini generation still has its own quotas. Content tracing stays off.

## Deployment boundary

The private worker uses the **same CI-tested backend image** as the NOC API, runs as a separate container with 768 MB / one CPU limits, and has no published ports. API requests pass through the existing review password gate and administrator guard, then a private service token. It is disabled by default and rejected outside `ENVIRONMENT=development`, `AUTH_MODE=preview`. It mounts the existing completed extraction read-only and writes derived SQLite text only into `.review-access/knowledge/index`. Original files are not copied into the app, Git or the image.

The upstream RAG runtime is an explicit 14-file code snapshot under `backend/app/review_rag`, with per-file hashes and upstream commit in `UPSTREAM.json`. `scripts/sync-review-rag.py --source /path/to/RAG-SYSTEM` refreshes only that allowlist. No local preview HTML, developer CLI scripts, keys, corpus, SQLite or Chroma files are vendored. The RAG repository remains the source of these modules. The public runtime release includes this installer/documentation; its image packaging and main CI provenance checks stay intact.

After the feature release is installed, run on the Linux server as `steve`:

```bash
cd /home/steve/Downloads/noc_platform
runtime=$(python3 -c 'import json; print(json.load(open(".review-access/cd/current.json"))["runtime"])')
python3 "$runtime/scripts/install-review-knowledge.py" \
  --root "$PWD" \
  --assessment /home/steve/.local/share/afl-noc-rag-demo/20261022T194044Z-7c3228ecf3d6/extraction-01 \
  --provider-env /home/steve/.local/share/afl-noc-rag-demo/pilot.env \
  --activate
```

The installer verifies that the installed runtime supports this service, locks against concurrent deployments, creates a protected worker token/configuration, mounts the extraction, starts and health-checks the worker/API, and updates the protected deployment controller. It never prints provider credentials. Omit `--provider-env` for inventory without generation. Provider configuration stays in the private worker environment, not in the frontend or GitHub Actions.

Subsequent tested releases update/stop/start/check the optional worker alongside the API and retain the previous configuration for rollback. Existing monitoring overlays remain included. The new worker uses accepted demo text only; it does not call Gemini during startup or automatically approve OneDrive intake. Replace an extraction snapshot only through an explicit restart/activation with a completed, reviewed batch. The derived index can be rebuilt from that batch; private service/provider configuration needs the organization's normal protected backup handling.

Open **Knowledge → Review collection**, or `/knowledge/review`. Start with Inventory, filter MTN, inspect different cause text and unresolved IDs, then export all matching groups. Ask the collection for focused summaries, inspect each citation and compare the displayed searched/matching/supplied report counts. An extraction-quality or provider failure stays visible and is never converted into a zero count or a fabricated answer.

To disable access, stop the deploy timer, remove only `.review-access/knowledge/enabled`, then recreate API with the current runtime's base/monitoring overlays and image override; stop `noc-review-knowledge-review-1`. Keep the protected configuration/index for review or later reactivation. Do not delete the input extraction or roll back the NOC database merely to disable this worker.
