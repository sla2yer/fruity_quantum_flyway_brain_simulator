Work ticket FW-M15-003: Build deterministic suite expansion, work scheduling, and resume-safe batch execution.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo already has local entrypoints for `simulate`, experiment-level comparison analysis, validation workflows, and dashboard packaging, but Milestone 15 is specifically about running experiments systematically instead of by hand. There is still no canonical batch runner that can take a normalized suite plan, expand it into deterministic work items, execute the required stages in order, persist intermediate status, and resume or retry safely after partial completion. Without a real orchestration workflow, every suite run will devolve into hand-written shell sequences, inconsistent skips, or forgotten analysis and validation steps, which defeats the point of this milestone.

Requested Change:
Implement the library-owned batch execution workflow for Milestone 15. The workflow should consume a normalized suite plan, expand deterministic work items or suite cells, execute the declared stages in a stable order, persist stage-level status and provenance, and support dry-run plus resume-safe behavior for partial reruns. Reuse the existing Milestone 9 through Milestone 14 library entrypoints rather than shelling out blindly wherever a direct library API already exists. The first version may stay local and deterministic rather than introducing distributed scheduling, but it must make stage ordering, rerun semantics, and failure handling explicit enough that large suites stop depending on manual operator memory.

Acceptance Criteria:
- There is one canonical local workflow that consumes a normalized Milestone 15 suite plan and executes deterministic work items for the declared stages.
- Work-item identities, stage ordering, dry-run output, and persisted status semantics are explicit and stable so a partially completed suite can be resumed without reinterpreting prior outputs.
- The implementation records provenance for each executed stage, including the normalized suite-cell identity and the upstream or downstream artifacts attached to that stage.
- Failures, skips, and partial completions are represented explicitly rather than being inferred later from missing files or console output.
- Regression coverage includes at least one fixture workflow that expands a representative suite, exercises dry-run and resume behavior, and asserts deterministic work-item ordering plus clear failure handling.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style fixture workflow that resolves a small suite plan, exercises dry-run plus at least one resumed execution path, and asserts stable work-item metadata and status persistence

Notes:
Assume `FW-M15-001` and `FW-M15-002` plus the existing simulation, analysis, validation, and dashboard library workflows are already in place. Keep the first runner boring and reviewable; a deterministic local orchestrator is more valuable here than a premature cluster scheduler. Do not attempt to create a git commit as part of this ticket.
