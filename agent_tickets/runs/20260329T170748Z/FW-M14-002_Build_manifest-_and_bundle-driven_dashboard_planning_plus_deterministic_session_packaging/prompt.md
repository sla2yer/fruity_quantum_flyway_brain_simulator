Work ticket FW-M14-002: Build manifest- and bundle-driven dashboard planning plus deterministic session packaging.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even with a locked dashboard contract, Milestone 14 will stall immediately if there is no canonical way to assemble one dashboard session from local artifacts. The repo already knows how to discover simulator bundles, analysis bundles, and validation bundles independently, but there is still no shared planner that can turn a manifest, an experiment ID, or a concrete bundle set into one normalized dashboard session with stable ordering, explicit pane inputs, deterministic output paths, and clear failure handling when a required artifact is missing. Without that assembly layer, every later visualization script will reimplement artifact discovery, special-case one fixture layout, and silently disagree about which baseline arm, wave arm, analysis bundle, or validation package a dashboard is actually showing.

Requested Change:
Add the planning and packaging layer for Milestone 14 dashboard sessions. Extend the library-owned planning surface so local config plus a manifest, experiment reference, or explicit bundle references resolve into one deterministic dashboard session plan; then package that plan into the dashboard-session bundle layout defined by `FW-M14-001`. The normalized plan should identify the scene source, circuit subset, morphology assets, trace sources, analysis artifacts, validation artifacts, overlay availability, and deterministic session output locations needed by the five panes. Fail clearly when inputs are missing, incompatible, or scientifically misleading, such as mismatched shared timebases, incomparable arm pairs, absent geometry assets for requested neurons, or analysis bundles that do not correspond to the selected simulator runs.

Acceptance Criteria:
- There is one canonical API that resolves local config plus manifest, experiment, or explicit bundle inputs into a normalized dashboard session plan with stable ordering and explicit defaults.
- The normalized plan records scene, circuit, morphology, time-series, analysis, and validation artifact references together with the selected comparison arms, active overlays, and deterministic output locations required for Milestone 14 workflows.
- The packaging layer writes one deterministic dashboard-session bundle or equivalent packaged session surface that later UI code can consume without reparsing raw repo directories.
- Planning fails clearly when required local artifacts are missing or incompatible, including mismatched experiment identity, incompatible shared timebases, missing wave-only diagnostics for a requested overlay, or insufficient morphology metadata for requested selections.
- Existing simulator, analysis, and validation bundle discovery helpers remain reusable inputs to the dashboard planner rather than being bypassed by a separate filename-guessing implementation.
- Regression coverage validates deterministic normalization, representative fixture session assembly, override precedence, and clear failure handling for unsupported dashboard requests.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused unit or integration-style test that resolves representative fixture simulator, analysis, and validation artifacts into one normalized Milestone 14 dashboard session plan and asserts deterministic ordering plus clear error handling

Notes:
Assume `FW-M14-001` and the Milestone 9 through Milestone 13 packaging layers are already in place. Favor one planning surface that future export, replay, and showcase code can reuse rather than a pile of script-local directory scans. Do not attempt to create a git commit as part of this ticket.
