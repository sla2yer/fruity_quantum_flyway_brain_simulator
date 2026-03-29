Work ticket FW-M14-001: Freeze a versioned dashboard-session contract, pane taxonomy, and interaction design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestones 8 through 13 already give the repo deterministic local artifacts for scene inputs, selected circuits, simulator bundles, experiment analysis, and validation ladders, but there is still no first-class software contract for the Milestone 14 dashboard that is supposed to make all of that understandable. Right now the project has separate offline reports and UI-facing payload fragments, yet there is no canonical definition of what one dashboard session is, which pane IDs exist, how a selected neuron or selected timepoint should propagate across panes, how baseline-versus-wave comparison mode should be represented, which overlays are fairness-critical versus wave-only, or how exportable dashboard state should be serialized. Without one decisive contract and design note, later UI work will drift across static reports, ad hoc HTML widgets, and script-local JSON, and the team will end up with a demo surface that looks polished while quietly violating upstream bundle semantics.

Requested Change:
Define a library-owned Milestone 14 dashboard-session contract and publish a concise design note that locks the pane taxonomy and interaction model. The contract should name the five dashboard panes, stable pane IDs, global interaction state such as selected arm pair, selected neuron, selected readout, active overlay, and time cursor, plus the artifact references and export target identities required to build a deterministic local dashboard session from existing simulator, analysis, and validation bundles. The design note should choose the default UI delivery model for this repo, explain how the dashboard stays compatible with the existing self-contained offline report approach, and specify the boundary between shared-comparison content, wave-only diagnostics, and reviewer-oriented validation evidence.

Acceptance Criteria:
- There is one canonical dashboard-session contract in library code with explicit identifiers for pane IDs, global interaction state, overlay categories, comparison modes, and export target identities.
- The contract records stable discovery hooks for simulator result bundles, experiment analysis bundles, validation ladder bundles, and any Milestone 14-specific packaged assets without mutating the earlier bundle contracts.
- A dedicated markdown design note explains the chosen UI delivery model, the five-pane taxonomy, linked-selection semantics, replay and comparison semantics, export boundaries, and which upstream contract invariants the dashboard must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 14 dashboard contract sits alongside the existing simulator, analysis, and validation bundle contracts.
- Regression coverage verifies deterministic contract serialization, stable pane and overlay discovery, and normalization of representative fixture dashboard-session metadata.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-001_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused unit test that builds fixture dashboard-session metadata and asserts deterministic serialization plus stable pane and overlay discovery

Notes:
This ticket should land first and give the rest of Milestone 14 a stable vocabulary. Reuse the existing `simulator_result_bundle.v1`, `experiment_analysis_bundle.v1`, and Milestone 13 validation packaging language where those contracts already answer artifact-discovery or fairness-boundary questions. Do not attempt to create a git commit as part of this ticket.
