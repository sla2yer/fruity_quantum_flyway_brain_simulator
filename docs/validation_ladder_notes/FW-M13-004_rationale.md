# FW-M13-004 Rationale

## Purpose

Milestone 13 needed a first morphology-sanity execution surface that can say
which structure changed, how propagation changed, and whether that difference
is acceptable, reviewable, or blocking. This ticket adds that surface in
`flywire_wave.validation_morphology`.

The implementation covers four local comparison modes:

- bottleneck effects on distal propagation
- branching-dependent damping and retained energy
- simplification sensitivity on matched semantic patch sets
- patchification sensitivity on matched semantic patch sets

It also reuses Milestone 10 and 11 runtime artifacts for two manifest-owned
paths:

- intact-versus-shuffled surface-wave result comparisons
- mixed-fidelity surrogate-versus-reference inspection summaries

## Design Choices

- One library-owned suite drives both fixtures and manifest workflows.
  `run_morphology_validation_suite` accepts local probe cases, geometry trace
  cases, and mixed-fidelity summaries, then writes one deterministic Milestone
  13 validation bundle.
- Findings stay localized instead of collapsing to one score.
  Every finding names the compared variant or arm, the measured quantity, the
  threshold basis, and diagnostic metadata such as root ID, patch set,
  provenance, and localized scope label.
- Local probe cases reuse the existing solver rather than introducing a special
  morphology-only simulator.
  The suite runs `SingleNeuronSurfaceWaveSolver` on matched operator bundles so
  bottleneck, branching, simplification, and patchification checks stay on the
  same runtime surface the repo already validates elsewhere.
- Manifest workflows reuse existing artifact discovery.
  Geometry trace cases load simulator result bundles through
  `simulator_result_contract`, and mixed-fidelity findings are lifted directly
  from `execute_mixed_fidelity_inspection_workflow`.
- Automatic mixed-fidelity references are policy-scoped by default.
  When callers do not pass explicit `reference_root_specs`, the morphology
  workflow only inspects roots with policy-recommended promotions. This avoids
  turning the default workflow into a bundle of blocked findings for roots that
  have no actionable higher-fidelity local reference in the current fixture.

## Local Workflow

The repo now exposes one local command path for morphology sanity:

```bash
make morphology-validate CONFIG=path/to/config.yaml MANIFEST=path/to/manifest.yaml
```

For deterministic local mixed-fidelity fixtures, the same workflow can be
scoped to a known arm:

```bash
make morphology-validate \
  CONFIG=path/to/config.yaml \
  MANIFEST=path/to/manifest.yaml \
  MORPHOLOGY_VALIDATE_ARGS="--arm-id surface_wave_intact"
```

The regression suite also exercises the library directly with:

```bash
.venv/bin/python -m unittest tests.test_validation_morphology -v
```

None of those paths require live FlyWire access.

## Testing Strategy

Coverage lands in two layers.

- `tests/test_validation_morphology.py` drives the local probe suite with
  deterministic fixtures and asserts bottleneck, branching, simplification, and
  patchification findings plus provenance-rich diagnostics.
- The same test file runs the end-to-end workflow on shipped local assets and
  asserts deterministic validation artifacts plus mixed-fidelity promotion
  review findings tied back to policy metadata.

This keeps the suite local, reproducible, and appropriate for the normal
`make test` loop.

## Simplifications

- The first version does not yet package trace plots or richer reviewer sidecar
  artifacts beyond JSON plus Markdown summaries.
- Manifest geometry comparisons currently depend on available intact/shuffled
  surface-wave result bundles and do not invent a separate morphology-input
  stack when those bundles are absent.
- Automatic mixed-fidelity discovery intentionally prefers policy-recommended
  references over exhaustive next-higher-class probing. Users can still force
  explicit references with `--reference-root`.

## Future Expansion

Likely follow-on work:

- promote local thresholds into Grant-reviewed criteria loaders while keeping
  the current finding vocabulary stable
- add richer drill-down artifacts for branch-local or patch-local trace review
- expand manifest-owned morphology checks once Milestone 12 experiment-analysis
  bundles expose more direct geometry-null and wave-diagnostic summary tables
- add more automatic fixture discovery for simplification and patchification
  variant families stored in geometry/operator inventories
