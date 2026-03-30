# Experiment Orchestration Design

## Purpose

Milestone 15 needs one suite-owned software contract before batch runners,
ablation transforms, suite indexes, tables, and plots start encoding different
meanings for the same experiment family. The versioned contract is
`experiment_suite.v1`, implemented in
`flywire_wave.experiment_suite_contract`.

This note does not replace earlier milestone contracts. It composes with them:

- `simulation_plan.v1` still owns manifest-driven simulator planning
- `simulator_result_bundle.v1` still owns per-arm simulator outputs
- `experiment_analysis_bundle.v1` still owns experiment-level packaged analysis
- `validation_ladder.v1` still owns validation bundle taxonomy and review
  handoff semantics
- `dashboard_session.v1` still owns packaged dashboard-session semantics

Milestone 15 sits above those layers. It names how one suite references them
consistently.

## Suite Identity

The suite contract freezes two identity concepts:

- `suite_id`: the stable human-declared suite identifier
- `suite_spec_hash`: the deterministic hash over normalized upstream
  references, suite-cell lineage, and work-item identity

The hash deliberately does not depend on downstream output paths. A rerun may
refresh bundle locations, tables, or plots without changing the suite identity
if the normalized suite declaration is the same.

## Dimension Taxonomy

`experiment_suite.v1` freezes these first dimension IDs:

- `scene_type`
- `motion_direction`
- `motion_speed`
- `contrast_level`
- `noise_level`
- `active_subset`
- `wave_kernel`
- `coupling_mode`
- `mesh_resolution`
- `solver_settings`
- `fidelity_class`

These are orchestration IDs, not ad hoc display labels. Later suite planning,
execution, reporting, and review code should key on these IDs rather than on
folder names or plot text.

The intent is explicit:

- stimulus and scene choices stay visible as suite dimensions
- circuit-selection choices stay visible as suite dimensions
- wave, coupling, geometry, solver, and fidelity choices stay visible as suite
  dimensions
- earlier milestone bundles still own their local parameter schemas and file
  layouts

## Required Ablation Families

`experiment_suite.v1` freezes these first Milestone 15 ablation-family IDs:

- `no_waves`
- `waves_only_selected_cell_classes`
- `no_lateral_coupling`
- `shuffle_synapse_locations`
- `shuffle_morphology`
- `coarsen_geometry`
- `altered_sign_assumptions`
- `altered_delay_assumptions`

The contract owns the family IDs and lineage semantics. It does not decide
which families are scientifically meaningful for a given claim. That decision
remains Grant-owned.

The contract also reserves a separate perturbation-seed hook for ablation
families that need stochastic realization, so a morphology or synapse shuffle
does not silently reuse the simulator seed.

## Suite-Cell Lineage

The first lineage kinds are:

- `base_condition`
- `seed_replicate`
- `ablation_variant`
- `seeded_ablation_variant`

Every non-root suite cell carries:

- `parent_cell_id`
- `root_cell_id`

Meaning:

- base conditions are the root cells declared directly from dimension values
- seed replicates introduce simulator-seed lineage without changing the
  dimension story
- ablation variants introduce explicit ablation-family lineage without hiding
  that change inside an arm name
- seeded ablation variants make both sources of lineage explicit

That is the canonical Milestone 15 answer to “what changed relative to the
base condition?”

## Work-Item Statuses

The first work-item status vocabulary is:

- `planned`
- `ready`
- `running`
- `succeeded`
- `partial`
- `failed`
- `blocked`
- `skipped`

These statuses describe orchestration state, not scientific judgment. A suite
runner may mark a work item as `failed` or `blocked`; that does not imply
anything about biological plausibility. Grant-owned scientific interpretation
still begins on the validation and review surfaces defined earlier.

## Artifact Roles And Discovery

The suite contract freezes one artifact-role catalog for both upstream inputs
and downstream outputs.

Upstream roles:

- `suite_manifest_input`
- `experiment_manifest_input`
- `simulation_plan`

Downstream bundle roles:

- `simulator_result_bundle`
- `experiment_analysis_bundle`
- `validation_bundle`
- `dashboard_session`

Suite-owned review-output roles:

- `summary_table`
- `comparison_plot`
- `review_artifact`

These roles are metadata-backed discovery hooks. The suite layer points at
earlier milestone bundles; it does not rename or relocate their internal
artifacts.

## Storage Expectations

This ticket intentionally freezes vocabulary before full suite packaging lands.
The storage expectation for `experiment_suite.v1` is therefore:

- suite metadata is the discovery anchor for suite-level lineage and artifact
  references
- upstream manifests and `simulation_plan.v1` remain upstream references
- simulator, analysis, validation, and dashboard bundles remain on their own
  contract-owned paths
- future Milestone 15 packaging may place suite metadata, tables, plots, and
  review artifacts under a suite-owned root, but it must keep the role IDs,
  lineage semantics, and upstream bundle references frozen here

That keeps this ticket from pre-empting the later packaging work while still
locking the suite vocabulary now.

## Ownership Boundary

The boundary is explicit:

- Jack owns suite identity, dimension IDs, artifact roles, lineage semantics,
  work-item status semantics, and reproducibility mechanics
- Grant owns which scientifically meaningful ablation families, parameter
  choices, and subset choices are declared through that surface

In other words:

- Jack owns how the suite is described and replayed
- Grant owns which scientific perturbations are worth describing through it

## Reproducibility Semantics

`experiment_suite.v1` freezes these first reproducibility hooks:

- `suite_spec_hash`
- `suite_cell_id`
- `parent_lineage_reference`
- `simulation_seed_scope`
- `ablation_seed_scope`
- `artifact_reference_catalog`
- `stable_discovery_order`

Invariants:

- suite discovery is metadata-backed rather than directory-scan-backed
- suite-cell identity is independent of output file naming
- simulator seed lineage stays separate from ablation perturbation lineage
- later suite tables and plots must point back to metadata-backed bundle
  references rather than becoming a second source of truth

## Consequences For Later Milestone 15 Tickets

Later Milestone 15 work may add:

- suite-manifest normalization
- deterministic suite expansion and execution
- ablation transform realizations
- suite packaging and indexing
- suite aggregation, tables, plots, and reports

Those tickets should reuse the IDs, lineage kinds, work-item statuses, artifact
roles, and reproducibility hooks frozen here. If they need different meanings,
that is a new contract version rather than a silent edit to
`experiment_suite.v1`.

## Local Review Workflow

The first deterministic local review workflow now has two explicit steps after a
suite has been executed and packaged:

1. `scripts/32_suite_aggregation.py` consumes the packaged suite inventory and
   writes suite-level JSON plus CSV rollups under `package/aggregation/`
2. `scripts/33_suite_report.py` consumes the packaged suite inventory again,
   regenerates aggregation deterministically, and writes reviewer-facing report
   artifacts under `package/report/suite_review/`

The review directory contains:

- `index.html`: static offline suite review surface
- `suite_review_summary.json`: deterministic summary metadata
- `catalog/artifact_catalog.json`: table, plot, and report discovery catalog
- `plots/<section-id>/*.svg`: auto-generated comparison plots with stable labels

`make suite-aggregate` and `make suite-report` are the repo entrypoints for
those two CLIs when reviewers want the wrapped command surface instead of
calling the scripts directly.

## Milestone 15 Readiness

Milestone 15 readiness is tracked as an explicit in-repo audit rather than as
an implied side effect of the other orchestration tickets.
The entrypoint is `scripts/34_milestone15_readiness.py`.

That readiness pass deliberately checks two different surfaces:

- a representative manifest-driven suite path through
  `scripts/31_run_experiment_suite.py` so suite-manifest resolution,
  deterministic scheduling, seed lineage, ablation materialization, and batch
  simulation execution are all exercised through the shipped runner
- a deterministic packaged-suite fixture through `scripts/32_suite_aggregation.py`
  and `scripts/33_suite_report.py` so suite packaging, indexing, rollups,
  plots, and reviewer-facing report delivery are all exercised through the
  shipped local CLIs

The repo entrypoint is `make milestone15-readiness`, which runs
`scripts/34_milestone15_readiness.py --config config/milestone_15_verification.yaml`
and writes `milestone_15_readiness.md` plus `milestone_15_readiness.json`
under `config.paths.processed_simulator_results_dir/readiness/milestone_15/`.

The current readiness gate is intentionally allowed to land at `hold` while the
report records explicit blocking follow-on tickets. That is not a failed audit;
it is the designed mechanism for surfacing remaining contract gaps before
Milestone 16 showcase work assumes more end-to-end orchestration coverage than
the repo actually has today.

That workflow is intentionally metadata-backed and local:

- it starts from `experiment_suite_package.json` or `result_index.json`
- it does not reparse raw per-experiment directories
- it keeps `shared_comparison_metrics`, `wave_only_diagnostics`, and
  `validation_findings` visibly separate in both the catalog and the HTML
  report
