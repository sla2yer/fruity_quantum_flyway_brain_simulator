# FW-M13-002 Rationale

## Purpose

Milestone 13 needed one library-owned planning surface above the existing
execution and Milestone 12 analysis layers. Before this ticket, the repo had
the `validation_ladder.v1` taxonomy and deterministic validation-bundle layout,
but it did not have a canonical resolver that could answer:

- which validators are active for a local run
- which local simulator and analysis artifacts they target
- which perturbation suites belong to each validation pass
- which criteria-profile reference each validator should use
- which deterministic validation output directory later tooling should write to

The implementation in `flywire_wave.validation_planning` closes that gap.

## Design Choices

- The planner reuses the existing normalized surfaces instead of opening a
  second manifest-resolution path.
  It consumes `simulation_plan`, `readout_analysis_plan`, discovered
  experiment bundle sets, and optional packaged analysis-bundle metadata.
- `validation` config is normalized into one explicit `validation_config.v1`
  structure.
  Layer selection, validator selection, criteria-profile overrides, and
  perturbation-suite declarations now have one stable shape.
- Criteria-profile precedence is explicit and deterministic.
  The resolver applies overrides in this order:
  validator override, validator-family override, layer override, validator
  contract default.
- Validation-bundle identity now includes more than the active validator IDs.
  The normalized plan-reference also records validator-to-profile assignments,
  target arm IDs, comparison-group IDs, and perturbation-suite identity so the
  validation spec hash changes when the validation intent changes.
- Perturbation suites are represented even though later Milestone 13 tickets
  will own execution.
  The planner emits stable suite and variant records now, including deterministic
  per-variant output directories under the validation bundle.

## Testing Strategy

Coverage was added in two layers.

- `tests/test_validation_contract.py` now checks deterministic normalization for
  the expanded validation-plan reference, including criteria assignments and
  perturbation-suite references.
- `tests/test_validation_planning.py` resolves a representative fixture manifest
  into a normalized validation plan, compares manifest-wrapper resolution with
  direct reuse of precomputed upstream planning surfaces, and asserts:
  deterministic ordering,
  criteria-profile override precedence,
  perturbation-suite normalization,
  deterministic output paths,
  missing analysis-bundle failure,
  unsupported geometry-variant failure,
  incomplete seed-coverage failure,
  and unknown criteria-profile failure.

The fixture test synthesizes condition-specific stimulus-bundle metadata and
simulator-result bundle metadata so the existing Milestone 12 bundle-set
discovery path is exercised instead of being mocked around.

## Simplifications

- The planner does not execute validators.
  It only resolves validation intent, prerequisites, and deterministic output
  locations.
- Sign and delay perturbations are represented as a fixed first catalog of
  supported probe IDs.
  Later tickets can expand that catalog or attach concrete executors without
  changing the planner surface.
- Noise robustness is planned as a seed/noise variant surface, not a simulator
  feature implementation.
  The suite exists so later tooling can consume one stable declaration.
- Geometry-variant selection is inferred from normalized arm topology labels.
  That keeps the current Milestone 1 fixture and Milestone 12 comparison groups
  reusable, but it does not yet model future mesh-resolution or patchification
  variants separately.

## Future Expansion

Likely follow-on work:

- attach validator-specific execution entrypoints to the normalized suite and
  artifact records
- add richer planning for operator-QA, surface-wave-inspection, and
  mixed-fidelity-inspection prerequisite existence checks
- extend geometry variants beyond the current topology-condition surface
- replace the fixed sign/delay perturbation catalog with executor-backed
  parameterized perturbations
- add a loader or registry for future Grant-owned criteria-profile payloads
  while keeping the current contract references stable
