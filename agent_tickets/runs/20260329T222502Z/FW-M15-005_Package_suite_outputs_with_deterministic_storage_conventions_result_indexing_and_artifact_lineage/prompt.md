Work ticket FW-M15-005: Package suite outputs with deterministic storage conventions, result indexing, and artifact lineage.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if a suite executes correctly, Milestone 15 still fails if the outputs sprawl across per-experiment directories with no authoritative index tying one suite cell to its simulator bundles, analysis bundle, validation outputs, dashboard session, tables, and plots. Right now the repo has strong per-run and per-experiment packaging layers, but no suite-level storage convention or result index that makes it easy to answer simple questions such as which ablation cell failed, which baseline cell a plot belongs to, or which validation bundle corresponds to one reported summary row. Without a suite-level packaging layer, comparison workflows and readiness checks will keep re-scanning the filesystem instead of reading one deterministic artifact catalog.

Requested Change:
Add the packaging and indexing layer for Milestone 15 suite outputs. Define deterministic output locations, one authoritative suite metadata anchor, shared discovery helpers for suite-cell records and stage artifacts, and a result index that maps normalized dimension values plus ablation identity to downstream simulator, analysis, validation, dashboard, and report artifacts. The first version should expose both machine-friendly discovery and reviewer-friendly inventory surfaces, but it should avoid inventing a second source of truth for experiment-level artifacts that already have their own bundle contracts.

Acceptance Criteria:
- There is one canonical Milestone 15 suite packaging layer with deterministic output paths, metadata-backed discovery, and stable artifact references for suite cells and stage outputs.
- The suite package records explicit lineage from normalized dimension values and ablation identity to the realized simulator, analysis, validation, dashboard, table, and plot artifacts for that cell.
- Failed, skipped, and incomplete cells remain visible in the result index instead of disappearing from the suite inventory.
- The implementation exposes at least one machine-friendly index surface that downstream reporting and readiness workflows can consume without globbing raw directories.
- Regression coverage includes at least one fixture suite that writes deterministic package metadata plus indexed artifact references and asserts stable paths for both successful and incomplete cells.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style fixture workflow that packages a representative suite output inventory and asserts deterministic artifact discovery plus expected lineage fields

Notes:
Assume `FW-M15-001` through `FW-M15-004` and the Milestone 12 through Milestone 14 bundle contracts are already in place. This ticket should make result indexing and storage conventions explicit enough that later review tooling never has to guess which artifact belongs to which suite cell. Do not attempt to create a git commit as part of this ticket.
