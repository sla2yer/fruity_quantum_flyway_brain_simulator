# FW-M15-002 Rationale

## Design Choices

This ticket adds one library-owned planner module,
`flywire_wave.experiment_suite_planning`, instead of spreading Milestone 15
suite parsing across later runners, reporting code, or ad hoc scripts.

The planner deliberately composes with earlier milestone layers:

- it resolves one reusable base `simulation_plan.v1`
- it reuses the embedded readout-analysis pairing surface from that plan
- it emits suite cells, work items, and planned artifact references through
  `experiment_suite.v1`
- it does not replace the Milestone 9 through Milestone 14 bundle contracts

The normalized suite surface therefore stays at the orchestration layer:

- dimensions declare sweep intent plus deterministic overrides or snapshots
- seed policy declares how simulator seeds are reused across suite cells
- ablation declarations stay explicit and lineage-tracked
- stage targets and output roots are deterministic before execution starts

I also added one new config path default,
`paths.processed_experiment_suites_dir`, so the suite planner has a stable
local root without forcing each caller to invent its own directory convention.

## Why The Planner Stops At Planned Cells Instead Of Full Derived Bundles

Milestone 15 still has later tickets for execution, ablation realization, and
suite packaging. This planner therefore normalizes intent and deterministic
lineage now, but it does not yet:

- materialize per-cell experiment manifests on disk
- run simulation, analysis, validation, or dashboard stages
- realize the scientific transforms behind each ablation family
- publish one finalized suite bundle layout with persisted metadata

That split is intentional. The planner now gives later workflow code one
stable, typed surface to consume instead of rediscovering sweep expansion,
seed reuse, and ablation attachment rules in multiple places.

## Testing Strategy

The regression coverage for this ticket focuses on normalization behavior and
failure clarity:

- deterministic resolution of a representative suite manifest into stable base,
  seed, ablation, and seeded-ablation cells
- config-versus-manifest precedence for stage targets, output roots, and seed
  defaults
- embedded experiment-manifest `suite` extensions as an alternative input path
- explicit failure handling for unknown dimension IDs, linked-axis length
  mismatches, unsupported ablation variants, contradictory perturbation-seed
  rules, and missing subset prerequisites

The suite-planning tests intentionally reuse the existing simulation fixture
helpers so the new planner is exercised on the same manifest/config ecosystem
as the earlier milestone planners.

## Simplifications

The first version intentionally keeps several boundaries conservative:

- ablation declarations use a small, explicit variant-id set per family
- dimension values may carry parameter snapshots or override patches even when
  later execution still has to interpret those patches
- suite-level output references are planned metadata targets, not yet persisted
  bundle files
- wave-dependent dimensions and ablations fail early when the base manifest has
  no surface-wave arm instead of pretending those requests are meaningful

These choices bias toward explicitness and clear failure over premature
generalization.

## Future Expansion Points

The next Milestone 15 tickets can build directly on this normalized surface:

- `FW-M15-003` can execute the emitted suite cells and work items in stable
  order
- `FW-M15-004` can replace planning-only ablation declarations with realized
  transforms
- `FW-M15-005` can persist the planned artifact roots as one suite-owned index
- `FW-M15-006` and `FW-M15-007` can aggregate and report from the same
  deterministic lineage and pairing surface

If later work needs different sweep semantics, seed semantics, or stage-role
meanings, that should be a new planner version rather than a silent behavioral
change.
