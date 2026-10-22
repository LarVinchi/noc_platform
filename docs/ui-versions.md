# UI design versions

These annotated Git tags identify complete repository snapshots for UI review.
They are separate from the platform's `review-<sha>` deployment tags. Creating a
local UI tag does not publish a release, push code, or deploy it.

| Tag | Design snapshot |
| --- | --- |
| `ui-v1.0.0` | Original control room design with weekly reporting refinements, bottom-aligned table actions and header counters; before edge illumination. |
| `ui-v1.1.0` | Adds cyan/red/amber KPI edge accents and cyan selected-navigation illumination in both themes. Keeps the version 1.0.0 workflows and reporting calculations. |
| `ui-v1.1.1` | Makes the primary palette consistently cyan/light blue, including action buttons, branding, selection backgrounds, links and focus accents. Removes remaining cobalt/periwinkle accent tokens. |
| `ui-v1.2.0` | Extends cyan styling across operational pages and adds the approved-TXT Knowledge workspace, with version review, explicit source selection and verifiable citations. Includes the disabled-by-default NOC backend integration; requires the separately reviewed RAG runtime. |
| `ui-v1.2.1` | Aligns knowledge request timeouts with the private worker for live Gemini queries. Earlier tags remain unchanged. |
| `ui-v1.3.0` | Adds reviewed PDF sources, reindex controls, actual retrieval identity and request budgets for semantic retrieval. Requires the optional vector/PDF worker dependencies; earlier tags remain unchanged. |
| `ui-v1.4.0` | Adds OneDrive-linked document intake, collector-report import, extraction/provenance previews, pause/resume, storage counters and audience controls. Original OneDrive files remain at their source. |
| `ui-v1.5.0` | Adds the official AFL navy/green brand and a separate FTTH workspace with provisioning, Telewyz support, frozen daily plans and closure, reconciled network snapshots, weekly reports and opt-in server mail delivery. Preserves the OneDrive intake workflow. |
| `ui-v1.6.0` | Refines energy date selection and chart readability; adds visible refill/top-up bars, explicit refill accounting, zero-day weekly averages and current-week reporting. |
| `ui-v1.6.1` | Restores Excel template colours and grid-free daily charts; combines weekly runtime and smoothed consumption on dual axes, with horizontal guides and black-backed values. Removes the separate weekly consumption band. |
| `ui-v1.6.2` | Fixes FTTH scrolling in preview and deployed layouts, keeps the footer visible, resets scroll on navigation and includes optional FTTH mail setup files in the release runtime. |

The numeric portion follows MAJOR.MINOR.PATCH: a compatible design enhancement
increments MINOR; a correction increments PATCH; an incompatible UI contract
change increments MAJOR. The `ui-` prefix names the design version series and
does not assert a platform-wide application version. Published tags must remain
immutable; future changes receive a new version rather than moving an old tag.

## Compare or inspect a previous version

Run these commands from the `noc-platform-ui` checkout:

```powershell
git tag --list 'ui-v*' --sort=version:refname
git show --no-patch ui-v1.0.0
git diff ui-v1.0.0 ui-v1.1.0 -- frontend
```

To open the baseline on a separate branch, first commit or stash any pending
work, then run:

```powershell
git switch -c review/ui-v1.0.0 ui-v1.0.0
```

Restart the local preview to compare, then return to the current feature branch:

```powershell
git switch feature/noc-ui-polish
```

For an eventual deployed rollback, use the tested release pipeline and an approved
revert PR or the deployer's rollback process. A UI tag alone does not change the
running server. Remote backup of these tags is a separate, explicit push step.
