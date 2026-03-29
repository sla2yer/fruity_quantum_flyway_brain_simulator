# Validation Ladder Design

## Purpose

Milestone 13 needs one contract-owned validation vocabulary before validator
implementations, readiness reports, notebooks, and reviewer notes encode
different meanings for the same run. The versioned software contract is
`validation_ladder.v1`, implemented in `flywire_wave.validation_contract`.

This note does not reopen earlier milestone boundaries. It reuses them:

- Milestone 6 already defines the operator-QA baseline and its `go` /
  `review` / `hold` gate semantics.
- Milestone 9 already defines the shared result-bundle comparison surface.
- Milestone 10 already defines the surface-wave inspection surface for
  numerical warnings and local stability review.
- Milestone 11 already defines mixed-fidelity class semantics and inspection
  outputs.
- Milestone 12 already defines the shared-readout fairness boundary, wave-only
  diagnostics, null tests, and packaged experiment-analysis outputs.

Milestone 13 therefore layers validation on top of those contract-owned
surfaces. It does not bypass them with notebook-local file naming or private
metric semantics.

## Locked Ladder

`validation_ladder.v1` freezes four layers and one first validator family per
layer.

- `numerical_sanity` -> `numerical_stability`
  Validators:
  `operator_bundle_gate_alignment`,
  `surface_wave_stability_envelope`
- `morphology_sanity` -> `morphology_dependence`
  Validators:
  `mixed_fidelity_surrogate_preservation`,
  `geometry_dependence_collapse`
- `circuit_sanity` -> `circuit_response`
  Validators:
  `coupling_semantics_continuity`,
  `motion_pathway_asymmetry`
- `task_sanity` -> `task_effect_reproducibility`
  Validators:
  `shared_effect_reproducibility`,
  `task_decoder_robustness`

The contract owns these layer IDs, family IDs, and validator IDs. Later
Milestone 13 work may add execution code or more validators, but it must not
silently rename these first identities inside `validation_ladder.v1`.

## Evidence Scopes

The contract also freezes the first evidence-scope vocabulary:

- `operator_qa_review`
- `surface_wave_inspection`
- `mixed_fidelity_inspection`
- `simulator_shared_readout`
- `experiment_shared_analysis`
- `experiment_wave_diagnostics`
- `experiment_null_tests`

Meaning:

- numerical validators start from Milestone 6 and Milestone 10 review artifacts
  rather than ad hoc local recomputation
- morphology validators use Milestone 11 mixed-fidelity inspection plus the
  Milestone 12 perturbation surfaces
- circuit and task validators stay on the shared simulator-result and packaged
  experiment-analysis surfaces
- wave-only diagnostics remain labeled as diagnostics; they do not replace the
  shared-readout fairness boundary frozen in Milestone 12

## Result Statuses

Every validator uses the same result-status vocabulary:

- `pass`: the declared machine-checkable diagnostics satisfied the active
  criteria profile on the declared evidence scopes
- `review`: the machine findings are stable and readable, but Grant must decide
  whether the observed behavior is scientifically plausible or sufficient for
  the current claim
- `blocking`: a blocking invariant or criteria threshold failed; do not treat
  the run as validation-equivalent until the issue is addressed
- `blocked`: required evidence was missing or incompatible, so the validator
  could not complete

This intentionally reuses the repo’s existing language instead of creating a
second near-duplicate review vocabulary.

## Criteria And Review Handoff

`validation_ladder.v1` freezes criteria-profile *references*, not the future
numeric thresholds themselves. Each validator names the criteria-profile
reference it expects, but the scientific threshold values and plausibility
judgments remain Grant-owned.

Machine-checkable diagnostics stop at one explicit boundary:

- validators may classify only what the declared upstream artifacts and active
  criteria profile support
- validators may not assert biological plausibility, claim acceptance, or
  scientific sufficiency on their own
- Grant-owned interpretation begins at the `review_handoff.json` artifact and
  the offline reviewer report

The required reviewer fields are:

- `scientific_plausibility_decision`
- `reviewer_rationale`
- `follow_on_action`

That is the canonical handoff between deterministic machine findings and
reviewer-adjudicated interpretation.

## Validation Bundle Layout

The contract reserves one deterministic output layout under:

```text
data/processed/simulator_results/validation/<experiment_id>/<validation_spec_hash>/
```

The first artifact slots are:

- `validation_bundle.json`: authoritative metadata
- `validation_summary.json`: machine-readable layer and validator summary
- `validator_findings.json`: stable per-validator findings keyed by
  `validator_id`
- `review_handoff.json`: Grant-owned plausibility handoff payload
- `report/validation_report.md`: offline reviewer report

Later Milestone 13 workflows should discover these paths through
`flywire_wave.validation_contract` rather than hardcoded filenames.

## Invariants For Later Milestone 13 Tickets

Later validation tickets may add execution code, criteria-profile loaders,
reports, and dashboards, but they must preserve these invariants unless the
contract version changes:

- `validation_ladder.v1` remains the canonical source of Milestone 13 layer,
  family, validator, evidence-scope, and output-artifact IDs
- validators compose with operator QA, simulator results, mixed-fidelity
  inspection, and experiment analysis instead of bypassing those contracts
- shared-readout fairness remains bounded by the Milestone 12 analysis surface
- wave-only diagnostics remain explicitly labeled as diagnostics
- machine findings stop at the explicit Grant handoff boundary
- changing validator meaning, status semantics, evidence-scope meaning, or
  output-slot meaning is a new contract version, not a silent edit
