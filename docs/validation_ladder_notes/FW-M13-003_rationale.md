# FW-M13-003 Rationale

## Purpose

Milestone 13 needed a first executable numerical-sanity layer, not just the
taxonomy and planning vocabulary added in FW-M13-001 and FW-M13-002. The new
implementation in `flywire_wave.validation_numerics` adds one canonical local
workflow that:

- evaluates operator health on the live runtime surface
- sweeps timestep variants with explicit stability tripwires
- records energy and activation-peak behavior for undriven pulse probes
- compares declared boundary-condition variants when fixtures provide them
- compares fine projected patch behavior against a coarse operator surrogate
- writes deterministic validation artifacts in the Milestone 13 bundle layout

## Design Choices

- The library owns one reusable case abstraction.
  `NumericalValidationCase` lets tests and local workflows describe the same
  evidence surface: operator bundle, model parameters, timestep factors,
  optional boundary variants, and optional coarse comparison bundle.
- The workflow resolves a numerical-only validation plan.
  The repo-wide validation ladder already reserves bundle paths and validator
  IDs, but later layers still depend on Milestone 12 packaged analysis inputs.
  This ticket therefore resolves the numerical subset directly from the same
  normalized `validation` config surface so local numerical execution remains
  usable without requiring unrelated later-layer artifacts.
- Findings stay explicit instead of collapsing into one score.
  Each record names the validator, case, measured quantity, comparison basis,
  status, and diagnostic metadata. Failures therefore say which assumption
  broke and under which perturbation.
- Resolution sensitivity uses a coarse-as-surface surrogate.
  The fine solver already exposes patch projection. Replaying the projected
  initial state on the coarse operator gives a deterministic coarse-versus-fine
  comparison without adding a second special-purpose solver implementation.
- Boundary behavior is fixture-backed in the first version.
  The default Milestone 6 local assets are mostly closed-surface bundles, so
  the reusable API supports explicit boundary variants and the regression suite
  exercises them directly. That keeps the first suite auditable without
  inventing synthetic boundary semantics for every cached asset.

## Local Workflow

The repo now exposes one deterministic local command path:

```bash
make numerical-validate CONFIG=path/to/config.yaml MANIFEST=path/to/manifest.yaml
```

That target runs `scripts/23_numerical_validation.py`, resolves the numerical
validation plan, executes the local cases, and writes:

- `validation_bundle.json`
- `validation_summary.json`
- `validator_findings.json`
- `review_handoff.json`
- `report/validation_report.md`

under the deterministic Milestone 13 validation bundle directory.

## Testing Strategy

Coverage lands in two layers.

- `tests/test_validation_numerics.py` drives the library directly with stable
  and intentionally unstable fixtures. It asserts deterministic bundle paths,
  stable finding IDs, stable statuses, boundary checks, timestep tripwires, and
  coarse-versus-fine sensitivity diagnostics.
- The same test file runs the end-to-end workflow on the local execution
  fixture and asserts deterministic validation artifacts for a real
  manifest/config/operator path.

This keeps the suite local, reproducible, and fast enough for the normal repo
test loop.

## Simplifications

- The first workflow executes only the numerical layer.
  Morphology, circuit, and task validators remain separate tickets.
- Criteria references are still identifiers, not Grant-owned numeric threshold
  tables loaded from an external registry.
  The implementation uses the contract-stable criteria references and the first
  auditable local thresholds needed for regression testing.
- Boundary comparisons are optional per case.
  Cases without explicit boundary variants still run the operator, timestep,
  and resolution checks.
- The report artifact is Markdown and JSON only.
  That is enough for deterministic reuse by later readiness or packaging code.

## Future Expansion

Likely follow-on work:

- merge this numerical execution surface into a full multi-layer Milestone 13
  validation runner once later validators land
- add richer trace sidecars if reviewers need time-series drilldown beyond the
  current scalar findings
- derive boundary variants directly from richer operator bundles when open
  surfaces become common local assets
- promote the current local thresholds into a Grant-reviewed criteria loader
  while preserving the stable finding vocabulary added here
