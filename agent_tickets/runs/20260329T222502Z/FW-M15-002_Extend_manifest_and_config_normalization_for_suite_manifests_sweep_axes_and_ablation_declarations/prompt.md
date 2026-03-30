Work ticket FW-M15-002: Extend manifest and config normalization for suite manifests, sweep axes, and ablation declarations.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo can already normalize one manifest into deterministic simulation, analysis, validation, and dashboard planning surfaces, but it still has no canonical way to declare a whole Milestone 15 suite. There is no shared planning layer for expressing which dimensions should sweep, which dimensions should stay fixed, when dimensions should be zipped versus cross-product expanded, which seed policies should be reused across cells, which ablation families attach to which base conditions, or how output roots should be named. Without one normalized suite-planning surface, every orchestration script will rediscover experiment intent differently, silently disagree about which runs belong together, and make reproducibility harder exactly where Milestone 15 is supposed to improve it.

Requested Change:
Extend the library-owned manifest and config normalization path so local config plus one suite manifest or one experiment manifest with suite extensions resolves into a deterministic Milestone 15 orchestration plan. The normalized plan should identify active experiment dimensions, sweep policies, seed policies, ablation declarations, comparison pairings, stage targets, output roots, and deterministic suite-cell ordering. It should support the roadmap dimensions directly, including scene type, motion direction, speed, contrast, noise level, active subset, wave kernel, coupling mode, mesh resolution, timestep or solver settings, and fidelity class, while also failing clearly when a requested sweep or ablation combination is unsupported, scientifically misleading, or incompatible with the shipped upstream bundle contracts.

Acceptance Criteria:
- There is one canonical API that resolves local config plus a suite-oriented manifest input into a normalized Milestone 15 orchestration plan with stable ordering and explicit defaults.
- The normalized plan records active dimensions, per-dimension sweep semantics, ablation declarations, seed reuse policy, stage targets, comparison pairings, and deterministic output locations needed by Milestone 15 workflows.
- The planner supports explicit control over cross-product versus linked-dimension expansion and fails clearly on unknown dimension IDs, incompatible axis combinations, unsupported ablation declarations, contradictory seed rules, or missing upstream prerequisites.
- Existing simulation, analysis, validation, and dashboard planning layers remain reusable inputs to the suite planner rather than being bypassed by a second filename-guessing or script-local YAML path.
- Regression coverage validates deterministic normalization, override precedence, representative fixture suite-plan resolution, and clear failure handling for unsupported suite requests.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-002_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused unit or integration-style test that resolves a representative fixture suite manifest into a normalized Milestone 15 orchestration plan and asserts deterministic cell ordering plus clear error handling

Notes:
Assume `FW-M15-001` and the Milestone 9 through Milestone 14 planning layers are already in place. Favor one planning surface that execution, reporting, readiness, and later showcase tooling can all reuse rather than a pile of special-purpose suite readers. Do not attempt to create a git commit as part of this ticket.
