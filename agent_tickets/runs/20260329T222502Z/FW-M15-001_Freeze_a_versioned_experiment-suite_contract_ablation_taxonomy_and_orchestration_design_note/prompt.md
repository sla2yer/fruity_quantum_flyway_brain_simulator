Work ticket FW-M15-001: Freeze a versioned experiment-suite contract, ablation taxonomy, and orchestration design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestones 9 through 14 already give the repo deterministic simulator bundles, experiment-analysis bundles, validation ladders, and packaged dashboard sessions, but there is still no first-class software contract for the suite-level workflow that Milestone 15 is supposed to make routine. Right now the roadmap names experiment dimensions such as scene type, motion direction, speed, contrast, noise level, active subset, wave kernel, coupling mode, mesh resolution, solver settings, and fidelity class, plus required ablations such as no waves, no lateral coupling, shuffled synapse locations, shuffled morphology, and altered sign or delay assumptions. None of those suite-level concepts currently have stable IDs, lineage semantics, bundle roles, or one canonical place where Jack-owned orchestration stops and Grant-owned scientific ablation choice begins. Without a versioned contract and decisive design note, later automation will sprawl across ad hoc manifest variants, shell scripts, and result folders that are hard to compare or trust.

Requested Change:
Define a library-owned Milestone 15 suite contract and publish a concise design note that locks the orchestration vocabulary. The contract should name the suite identity, canonical experiment-dimension IDs, required ablation family IDs, suite-cell lineage, work-item status semantics, reproducibility hooks, and artifact roles for upstream manifests plus downstream simulator, analysis, validation, dashboard, table, and plot outputs. The design note should explain how the suite layer composes with `simulation_plan.v1`, `experiment_analysis_bundle.v1`, `validation_ladder.v1`, and `dashboard_session.v1`, and it should make the ownership boundary explicit: Jack owns the orchestration surface and reproducibility mechanics, while Grant owns which scientifically meaningful ablation sets are declared through that surface.

Acceptance Criteria:
- There is one canonical Milestone 15 suite contract in library code with explicit identifiers for experiment dimensions, required ablation families, suite-cell lineage, work-item statuses, and suite-level artifact roles.
- The contract records deterministic discovery hooks for upstream manifest inputs and downstream simulator-result bundles, experiment-analysis bundles, validation bundles, dashboard sessions, summary tables, plots, and review artifacts without mutating the earlier milestone contracts.
- A dedicated markdown design note explains suite identity, suite-cell lineage, reproducibility semantics, the taxonomy for the Milestone 15 dimensions and required ablations, storage expectations, and the boundary between orchestration mechanics versus scientific ablation selection.
- `docs/pipeline_notes.md` is updated so the Milestone 15 suite contract sits alongside the existing simulator, analysis, validation, and dashboard contracts.
- Regression coverage verifies deterministic contract serialization, stable dimension and ablation discovery, and normalization of representative fixture suite metadata.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused unit test that builds fixture suite-contract metadata and asserts deterministic serialization plus stable dimension and ablation discovery

Notes:
This ticket should land first and give the rest of Milestone 15 a stable vocabulary. Reuse the existing simulator, analysis, validation, and dashboard contract language where those layers already answer lineage, fairness-boundary, or artifact-discovery questions. Do not attempt to create a git commit as part of this ticket.
