# FW-M13-005 Rationale

## Purpose

Milestone 13 still lacked a circuit-sanity execution surface even after the
taxonomy, planning, numerical checks, and morphology checks landed. This ticket
adds that missing layer in `flywire_wave.validation_circuit`.

The first circuit suite covers four concrete questions:

- do declared coupling delays still appear as downstream latency structure
- do declared coupling signs still produce the expected readout polarity
- does sum-preserving aggregation still behave additively on simple motifs
- do pathway readouts preserve preferred-versus-null asymmetry under canonical
  motion stimuli

## Design Choices

- One library-owned suite handles both motif probes and small-circuit checks.
  `run_circuit_validation_suite` accepts reusable delay, sign, aggregation, and
  motion-pathway case objects, then writes the standard Milestone 13 validation
  bundle artifacts.
- Motif checks stay tied to the Milestone 7 coupling contract.
  Delay, sign, and aggregation cases load real edge coupling bundles through
  `load_edge_coupling_bundle`, record edge-family provenance, and phrase each
  expectation in terms of signed weights, delay bins, and aggregation rules
  already frozen by Milestone 7.
- Readout interpretation reuses Milestone 12 kernels instead of open-coding a
  second metric layer.
  The suite reuses `shared_readout_analysis` windowing and baseline semantics,
  including `_compute_window_response_summary` and
  `compute_shared_readout_analysis`, so circuit findings line up with the same
  readout-analysis surface used elsewhere in the repo.
- The manifest workflow stays small and explicit.
  `execute_circuit_validation_workflow` discovers local simulator bundles,
  reuses the Milestone 12 shared-readout analysis kernels directly, and can also
  attach an explicit packaged experiment-analysis bundle when the caller already
  has one.
  By default it derives motion cases from the canonical matched
  surface-wave-versus-baseline arm pair, which keeps the first circuit suite
  decisive instead of diffusing across every comparison arm.
  Delay, sign, and aggregation motifs remain available through the reusable
  Python API because they often depend on reviewer-chosen local probe bundles.
- Findings remain localized and actionable.
  Every finding records expected relationship, observed relationship, validator,
  case ID, bundle or edge provenance, and a specific next diagnostic step.

## Local Workflow

The repo now exposes one small-circuit command path:

```bash
make circuit-validate \
  CONFIG=path/to/config.yaml \
  MANIFEST=path/to/manifest.yaml \
  CIRCUIT_VALIDATE_ARGS="--pathway-readout-id preferred_pathway_output"
```

That target runs `scripts/25_circuit_validation.py`, reuses local simulator
bundles plus the Milestone 12 shared-readout analysis layer, and writes the
standard Milestone 13 validation artifacts under the deterministic validation
bundle directory.

For motif-level delay, sign, and aggregation probes, the canonical entrypoint is
the library API:

```python
from flywire_wave.validation_circuit import run_circuit_validation_suite
```

Tests use that API directly with fixture-owned coupling bundles and shared
readout payloads.

## Testing Strategy

Coverage lands in two layers.

- `tests/test_validation_circuit.py` drives the reusable suite directly with
  deterministic motif fixtures and asserts pass and fail findings for delay,
  sign, and aggregation behavior, including explicit edge provenance and
  readable failure diagnostics.
- The same test file runs the small-circuit workflow on a local
  preferred-versus-null motion fixture, asserts deterministic validation bundle
  artifacts, and checks motion-pathway asymmetry findings derived from the
  Milestone 12 shared-readout analysis surface.

This keeps the first circuit suite local, deterministic, and fast enough for
the normal `make test` loop.

## Simplifications

- The first workflow auto-builds motion-pathway cases only.
  Delay, sign, and aggregation motifs are exposed through the reusable Python
  API rather than a declarative manifest-side probe catalog.
- Thresholds are still local defaults, not Grant-owned criteria payloads loaded
  from a future criteria registry.
- Circuit findings stop at plausibility tripwires.
  The suite records which relationship broke and where, but scientific
  sufficiency remains a reviewer decision in the standard Milestone 13 handoff.

## Future Expansion

Likely follow-on work:

- add a manifest-owned motif catalog so delay, sign, and aggregation probes can
  be declared without Python-side case construction
- enrich the workflow with more pathway-readout discovery helpers once the repo
  standardizes pathway-specific readout naming
- promote current thresholds into criteria-profile loaders while keeping the
  finding vocabulary stable
- attach richer trace sidecars or plots for reviewer drill-down when one edge
  family or motion pathway trips a plausibility check
