# UI design versions

These annotated Git tags identify complete repository snapshots for UI review.
They are separate from the platform's `review-<sha>` deployment tags. Creating a
local UI tag does not publish a release, push code, or deploy it.

| Tag | Design snapshot |
| --- | --- |
| `ui-v1.0.0` | Original control room design with weekly reporting refinements, bottom-aligned table actions and header counters; before edge illumination. |
| `ui-v1.1.0` | Adds cyan/red/amber KPI edge accents and cyan selected-navigation illumination in both themes. Keeps the version 1.0.0 workflows and reporting calculations. |

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
