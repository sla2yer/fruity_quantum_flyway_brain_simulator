# FW-M13-007 Rationale

## Purpose

Milestone 13 already had four executable validation layers, but it still lacked
one packaging surface that made those outputs easy to rerun, review, compare,
and gate in automation. This ticket adds that missing layer in two parts:

- `flywire_wave.validation_reporting` packages existing layer bundles into one
  deterministic ladder-level bundle with aggregate summaries, notebook exports,
  regression artifacts, and a reviewer-facing Markdown report
- `flywire_wave.validation_ladder_smoke` plus `scripts/27_validation_ladder.py`
  provide a fully local smoke fixture that exercises the packaged path end to
  end without live FlyWire access

## Design Choices

- The packaged ladder bundle is separate from `validation_ladder.v1`.
  The existing contract intentionally freezes the per-run layer bundle layout to
  five artifacts. Rather than silently expanding that contract, this ticket adds
  `validation_ladder_package.v1` as a higher-level package that references the
  raw layer bundles.
- Raw findings, summaries, and reviewer reports stay distinct.
  Layer-local `validator_findings.json` files remain the raw machine findings.
  The packaged `validation_ladder_summary.json` is the stable aggregate gate
  surface. `report/validation_ladder_report.md` is the reviewer-facing report.
- Regression baselines compare stable summary fields instead of full raw JSON.
  The committed smoke baseline locks experiment id, layer and validator
  statuses, finding and case counts, and aggregate finding-status counts. That
  makes the baseline portable across output roots and keeps CI diffs readable.
- Notebook exports are flattened once.
  The packaged ladder writes `finding_rows.jsonl` and `finding_rows.csv` so
  later notebooks or dashboards can ingest one stable table instead of reparsing
  four different layer-specific finding schemas.
- The first smoke workflow is fixture-owned on purpose.
  It uses deterministic local synthetic cases for numerical, morphology,
  circuit, and task layers so CI can run a meaningful regression check without
  depending on manifest-local cached assets or live network access.

## Testing Strategy

Coverage lands in three layers.

- `tests/test_validation_reporting.py` runs the full packaged smoke workflow in
  a temporary output root, reruns it to assert deterministic paths and bytes,
  checks the package-discovery helpers, and verifies the committed baseline
  comparison result plus expected summary fields.
- `make validation-ladder-smoke` exercises the same local smoke command surface
  that CI can call directly.
- `make test` keeps the broader repo regression loop intact so the packaging
  layer is validated alongside the existing Milestone 13 suites.

## Simplifications

- The packaged ladder report is Markdown-only in the first version.
  The per-layer bundles already own their own Markdown reports, so the ladder
  package focuses on summary, links, and regression context instead of adding a
  second HTML stack immediately.
- The first smoke baseline is fixture-owned rather than manifest-owned.
  That keeps the CI path deterministic and offline, but it does not replace
  future manifest-level readiness or scientific review passes.
- The package compares only stable aggregate fields.
  It does not attempt byte-for-byte snapshotting of all layer findings because
  that would be noisier and harder to maintain than the intended gate surface.

## Future Expansion

Likely follow-on work:

- package manifest-owned layer bundles from real local result caches more
  directly, not just the smoke fixture and explicit bundle-path packaging mode
- add richer offline report surfaces once the team wants clickable drill-down
  views at the ladder level
- add more regression snapshots for additional fixture families or model modes
- expose the packaged ladder bundle to later dashboard and readiness tooling so
  Milestone 13 and Milestone 14 code can consume one shared review surface
