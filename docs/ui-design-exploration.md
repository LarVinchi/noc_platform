# Original local control-room design

This iteration introduces an original application skin and Operations overview on
the isolated `feature/noc-ui-polish` branch. It builds on the preserved v0 branch;
the original overview remains available at `/design/v0` for layout comparison.
The Gemini exports remain separate design references outside the repository.

## Scope

- Navy navigation rail, cyan/light-blue accents, semantic light/dark palettes, selected
  navigation, current WAT shift clock and feed status.
- Interactive incident metrics, severity/age-ordered queue, search, filters,
  compact/comfortable row density and a keyboard-accessible incident selector.
- Incident focus panel uses recorded location, ownership, category and milestones.
  It does not fabricate diagnostic readings or introduce operational write actions.
- Latest handover activity is summarized beside the detail panel. The complete
  existing activity component, including its form and actions, is accessible at
  `/handover` and from the sidebar. No activity API behavior changed.
- Unknown timestamps, unavailable feeds and empty views remain explicit. Activity
  failure is separate from incident-feed failure. Both poll every 30 seconds.
- Awaiting ownership accounts for both `assigned_engineer_id` and legacy
  `responsible_person`: a record assigned by ID is not counted as unassigned solely
  because its legacy name field is empty. The panel does not invent an engineer name.

This is the first original design iteration, not a claim that every platform page
has been redesigned. Existing routes inherit the palette/navigation; page-specific
layout work still needs review. Authentication and deployment configuration remain
unchanged. The weekly report refinement below includes a backend calculation change.

## Weekly report refinement

- A completed week with seven recorded days shows logged hours divided by seven,
  even when unresolved source intervals exist. An asterisk and explanation mark
  that average as provisional. Missing days and in-progress weeks still withhold
  averages. Consumption averages continue to require complete measurements;
  unresolved intervals never contribute invented hours or readings. Confirmed
  availability percentages remain withheld when intervals are unresolved.
- The same average and explanation appear in summary cards, chart canvases,
  pivot tables, metadata panels and separate PNG exports.
- Weekly panels use a column layout with the final table action bar anchored to
  the bottom, including mixed grid/diesel/gas panels. Meter and capacity metadata
  remain beside the pivot table.
- Two compact header counters show active incidents awaiting an owner and under
  investigation, using the existing incident feed and ownership rules. They show
  last-known status on a failed refresh and hide on narrow screens.

Regression checks cover seven-day provisional averages, missing days, incomplete
weeks, missing consumption readings and zero completed generator runs. Browser
checks use explicit synthetic records passed through the backend calculator;
they check footer alignment in all app/report theme combinations, mobile layout,
and separate chart/table export sizes and provisional labels. The local workbook
copy stops on 17 October and cannot independently validate the newer 18 October
readings shown in the operator's screenshots.

## Local review

Run `start-noc-ui-preview.cmd` from the parent workspace and visit
`http://127.0.0.1:15177/`. Choose **Open design preview**. The dedicated Vite demo
configuration uses synthetic data and rejects writes. Production builds exclude
the demo entry and fixture adapter.

Browser verification covers both themes and persistence, incident focus, search,
filters, density, mobile navigation/Escape, preserved activity entry, and empty/error
states. Frontend lint/build are run separately. A synthetic preview cannot verify
real backend connectivity or every operational workflow.

No UI deployment is authorized by merely running this preview. Review the final
change and existing CI gates before merging through the normal release pipeline.
