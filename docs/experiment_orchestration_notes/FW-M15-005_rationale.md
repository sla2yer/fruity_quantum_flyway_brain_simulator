# FW-M15-005 Rationale

## Design Choices

This ticket adds one library-owned package/index module,
`flywire_wave.experiment_suite_packaging`, instead of leaving suite-level
artifact discovery spread across execution-state internals, ad hoc globbing, or
later reporting code.

The core design choice is to treat the suite root as the deterministic storage
anchor and to add one fixed package directory beneath it:

- `.../package/experiment_suite_package.json`
- `.../package/indexes/result_index.json`
- `.../package/exports/cell_inventory.csv`
- `.../package/exports/stage_artifacts.csv`
- `.../package/report/inventory.md`

That gives Milestone 15 one stable answer to “where is the suite inventory?”
without relocating the earlier milestone bundles that already have their own
contracts.

The package layer deliberately composes with the existing Milestone 9 through 14
contracts instead of replacing them.

- simulator, analysis, validation, and dashboard bundles stay on their
  contract-owned paths
- the suite package records references back to those bundle paths
- reviewer-facing tables in the package are inventories, not competing bundle
  summaries

I also kept the distinction between planned targets and realized artifacts
explicit. The suite planner already emits planned per-cell stage targets, but
those are not the authoritative answer for realized bundle locations. The
package therefore records both:

- the planned stage output root and planned metadata path from the suite plan
- the realized workspace root, stage status, and discovered downstream
  artifacts from execution state

That is important because simulation, analysis, validation, and dashboard stages
write into their own earlier-contract layouts under the shared workspace rather
than into the planner’s placeholder metadata paths.

Another deliberate choice is that base and ablation cells carry explicit
simulation-lineage references. Analysis, validation, and dashboard work items
belong to `base_condition` and `ablation_variant` cells, while the simulator
bundles live under child `seed_replicate` and `seeded_ablation_variant` cells.
The result index therefore links parent cells back to their child simulation
cells and their realized simulator artifacts. That makes it possible to answer
questions such as:

- which simulator bundles fed one successful base-cell analysis bundle
- which seeded ablation failed and therefore blocked one ablation review cell

The artifact discovery path is also intentionally resilient. When a stage emits
valid earlier-milestone bundle metadata, the package layer can load and expand
those contract-owned artifact catalogs. When a stage only exposes raw
execution-state artifact records, such as in fixture tests or partial failure
cases, the package falls back to those records instead of discarding the stage
from the index.

## Testing Strategy

The regression coverage for this ticket stays focused on deterministic suite
packaging semantics rather than re-running the full scientific stack.

The new fixture workflow test:

- resolves a real Milestone 15 suite plan
- executes the suite through the real orchestration runner
- injects richer fixture stage executors that emit simulator, analysis,
  validation, dashboard, table, and report artifacts
- forces one seeded ablation simulation work item to fail
- verifies that the suite package is still written
- verifies that successful base cells and incomplete ablation cells both remain
  present in the packaged result index
- checks stable package paths, stage-artifact discovery, and explicit lineage
  back to child simulation cells
- repackages the same persisted execution state and confirms the result index is
  deterministic

I also reran the existing experiment-suite planning, contract, and execution
tests so the new auto-packaging step could not silently break the earlier
Milestone 15 work.

## Simplifications

The first version intentionally keeps several boundaries conservative.

- The suite package emits inventories and references, not suite-level rollups,
  summary science tables, or comparison plots. Those still belong to
  `FW-M15-006` and `FW-M15-007`.
- The package metadata itself stays small and points at the result index and CSV
  inventories instead of embedding every cell and artifact row inline.
- Reviewer-friendly surfaces are lightweight CSV and Markdown inventories rather
  than a richer web UI.
- Artifact categorization is pragmatic and filename-driven for fallback
  execution-state artifacts. When real bundle metadata is available, that richer
  contract information is used; when it is not, the package still indexes the
  outputs instead of failing closed.
- The package does not promote the validation-ladder package into a new suite
  source kind. It keeps the suite-level role as `validation_bundle` while
  recording the underlying contract version that actually produced the artifact.

These choices bias toward one boring, durable storage convention now rather than
prematurely collapsing later aggregation or reporting tickets into the package
layer.

## Future Expansion Points

The clearest next steps are:

- `FW-M15-006`: consume the packaged result index for deterministic rollups and
  ablation-aware comparison rows
- `FW-M15-007`: generate suite-owned tables, plots, and richer review artifacts
  on top of the package layer
- enrich artifact categorization once later tickets introduce canonical
  suite-owned plot and table contracts
- add more targeted integrity checks that compare the packaged suite inventory
  against the earlier bundle contracts and flag mismatches more explicitly
- add a dedicated CLI for re-packaging an existing suite root without rerunning
  execution if later workflows need that separation
