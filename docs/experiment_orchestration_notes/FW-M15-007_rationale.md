# FW-M15-007 Rationale

## Design Choices

This ticket adds one suite-owned reporting module,
`flywire_wave.experiment_suite_reporting`, plus a thin CLI wrapper
`scripts/33_suite_report.py`.

The key design choice is to keep reporting downstream of the existing Milestone
15 package and aggregation layers instead of introducing a third discovery
mechanism.

- the workflow accepts `experiment_suite_package.json` or `result_index.json`
- it recomputes suite aggregation from the packaged suite inventory
- it generates plots, catalogs, and the offline HTML review surface only from
  the packaged inventory and suite rollups
- it does not reopen raw per-experiment directories or re-infer comparisons
  from folder structure

That preserves the boundary from `FW-M15-005` and `FW-M15-006`: package first,
aggregate second, report third.

The review output stays intentionally static and local.

- `package/aggregation/` remains the stable home for machine-friendly rollups
  and CSV exports
- `package/report/suite_review/` now adds a deterministic reviewer surface with
  `index.html`, `suite_review_summary.json`, `catalog/artifact_catalog.json`,
  and generated SVG plots
- plots get JSON sidecars that record source table identity, source pairing
  ids, suite-cell ids, bundle ids, and source paths

That is enough for fast local review without pretending this first version is a
web app.

Another deliberate choice is to keep the review surface visibly sectioned along
the same boundaries already established in earlier tickets:

- `shared_comparison_metrics` is the fairness-critical surface
- `wave_only_diagnostics` is explicitly separate
- `validation_findings` is explicitly separate

The HTML report, plot directories, and artifact catalog all preserve that
separation so reviewers do not have to guess which outputs are safe to compare
directly against baseline-driven claims.

I also chose deterministic SVG generation over notebook code or a heavier
plotting stack.

- SVG files are plain-text, diffable, and path-stable
- labels come directly from normalized suite/group/metric identity rather than
  hand-written captions
- reruns overwrite the same files with the same ordering, legend labels, and
  axis labels

That keeps the first Milestone 15 review surface honest and repeatable.

## Testing Strategy

The regression coverage stays fixture-driven and reuses the real packaged-suite
smoke boundary.

`tests/test_experiment_suite_reporting.py`:

- materializes the representative packaged suite fixture from the aggregation
  test workflow
- runs the new reporting API against packaged suite metadata
- reruns the same workflow and asserts deterministic summary payloads
- verifies that the static HTML, summary JSON, and artifact catalog are written
- checks at least one suite summary-table export and one generated comparison
  plot
- validates expected section separation, plot labels, table metadata, and plot
  traceability back to pairings and bundle references
- compares one generated SVG across reruns to ensure label/content stability

That test intentionally targets the same packaged-suite contract that a human
reviewer will use, rather than a hand-built fake artifact catalog.

## Simplifications

The first version stays conservative in a few places.

- report generation reruns the aggregation workflow instead of caching a second
  incremental state layer
- plots are deterministic grouped-bar SVGs, not interactive notebooks or a
  richer client-side plotting system
- the artifact catalog records traceability metadata, but it does not revise
  the suite-package contract to register the new report outputs as package-owned
  contract artifacts
- the HTML report previews summary-table rows and links to CSVs rather than
  embedding full table explorers
- validation plots summarize finding-count deltas only; they do not yet render
  a validator-by-validator diff matrix

These choices bias toward one boring, inspectable reporting workflow instead of
trying to solve full review UX in one ticket.

## Future Expansion Points

The clearest next steps are:

- register suite-review outputs into a later suite-package contract revision if
  stronger discovery guarantees become necessary
- add richer validation visuals keyed by validator family, finding identity, or
  status transition
- add optional plot filtering for metric families, ablation families, or
  dimension slices
- add compact HTML table sorting/filtering if reviewers need more interactive
  local inspection without moving to a service
- extend SVG plotting with confidence intervals or additional summary-statistic
  overlays if later rollups expose those semantics explicitly
