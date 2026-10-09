# FibreViz and NOC workspace redesign

The topology uses the full available workspace instead of a fixed 600px map.
The main navigation retracts to an icon rail and remembers the preference.
The map route explorer can be hidden separately. The full-screen button removes
the surrounding application chrome; Escape exits browser full-screen mode.

## Restored FibreViz features

- Dark streets and satellite imagery, zoom controls and metric scale.
- Route list, route search, status filters and route-focused camera controls.
- Map popups with route lengths, fibre metadata, annotations and site details.
- Live/down/planned/unknown route-length totals and built-length percentage.
- Cable glow/casing, travelling light effect, down/planned/unknown line patterns,
  and width based on file fibre count (96/48/access tiers).
- Original POP, landing station, splice closure, handhole, customer and fault
  symbols, permanent zoom-aware labels, and the map legend.
- File upload and drag/drop, Lekki demo, persisted map-layer selection.
- Manual map status annotations, reset to file status, and drawn vs recorded
  lengths. Annotations are local browser preferences, not shared operational
  status or incident resolution. Inventory-linked monitoring alarms take priority.

The integrated viewer also retains inventory geometry links, customer anchors,
alarm observations, customer impact analysis, alternate-path information and
cable-specific impact inspection. Linked imports suppress duplicate inventory
route lines so route length is counted once. Polling does not reset the camera.
Imported file status and customer availability remain separate concepts.

## Rebuilt logical view

Distinct symbols identify network routes, fibre cables, PFP cabinets, PFS
splitters, NAP terminals, customer ONTs, enterprise DIA, Layer 2 and dark-fibre
patch panels. Cable edges display names and known physical core capacity;
feeder/service edges display assigned core numbers. Distribution names and
fibre numbers come from matching inventory records. Missing core capacity is
labelled unrecorded, including drops whose physical strand count is not stored.

The default diagram flows top-to-bottom; a horizontal layout is also available.
Double-click to expand/collapse a branch, or expand all cable descendants.
Search locates loaded assets/customers and highlights their dependency paths.
The inspector provides inventory details, tracing and actual customer impact.
Shared endpoints remain visible if another uncollapsed branch reaches them.
The diagram cannot create arbitrary unpersisted connections, and it does not
invent online status or pretend that opening the incident page creates a ticket.

## NOC interface

The application uses a consistent dark control-room palette, grouped navigation,
compact command bar, actual active/critical incident counts and a WAT shift clock.
Incident summary cards and the response queue appear before the activity-entry
form. API errors mark the feed stale rather than showing an invented healthy state.

Windows Docker development uses opt-in file polling and mounts the Tailwind
configuration, so edits appear in the preview. See
[Vite file-watching guidance](https://vite.dev/config/server-options#server-watch).

## Verification

48 backend tests pass, including allocation/core-label correctness and existing
provisioning, audit and monitoring workflows. Frontend lint and build pass.
Headless Edge acceptance checks cover navigation/map-panel collapse, restored
FibreViz layers, annotations/reset, camera preservation on refresh, native
full-screen, logical expansion, cable labels, NAP symbols, tracing, customer
impact, layout direction and mobile sizing. Screenshots were visually reviewed.

Basemap imagery still requires access to OpenStreetMap/Esri. The Lekki demo is
approximate sample data; imported status percentages are not authoritative SLA
measurements. Entra/PRTG activation, escalation policies and MTTR/SLA remain
separate operational milestones described in the requirements review.
