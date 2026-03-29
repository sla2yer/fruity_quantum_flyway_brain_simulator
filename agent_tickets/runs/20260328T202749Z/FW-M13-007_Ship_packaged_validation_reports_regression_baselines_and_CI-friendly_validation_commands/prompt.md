Work ticket FW-M13-007: Ship packaged validation reports, regression baselines, and CI-friendly validation commands.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 13 roadmap 2026-03-26

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if all four validation layers exist, Milestone 13 will still be weak unless the findings are easy to rerun, compare, and review. Right now there is no canonical validation-bundle layout, no shared discovery helper for per-layer findings, no deterministic regression baseline story, and no single local command surface that Jack can wire into smoke automation or CI. Without that packaging layer, validation results will sprawl across ad hoc JSON, CSV, Markdown, and notebook fragments, and model changes will remain hard to regression-check even when the underlying validators are sound.

Requested Change:
Add the packaging and regression layer for Milestone 13 validation outputs. Define deterministic output locations and shared discovery helpers for per-layer findings, aggregate summaries, and review artifacts; add at least one lightweight offline report workflow plus notebook-friendly exports; and expose a documented local command surface suitable for smoke automation and CI, such as a dedicated validation-ladder script or Make target. Preserve the distinction between raw layer findings, summarized gates, and reviewer-facing reports so future dashboard work can consume stable artifacts without reparsing one-off report files.

Acceptance Criteria:
- There is a canonical packaging layer for Milestone 13 validation outputs with deterministic paths, metadata-backed discovery, and stable export formats for per-layer findings, regression summaries, and review artifacts.
- At least one documented local command or script can run the packaged validation ladder end to end on local fixtures and produce deterministic report outputs without live FlyWire access.
- The implementation includes notebook-friendly or tabular exports plus at least one lightweight offline report surface that helps reviewers inspect validation findings outside raw JSON.
- A CI-friendly smoke command or Make target exists for a reduced local validation pass so model changes can be regression-checked automatically when feasible.
- Regression coverage includes at least one smoke-style fixture workflow that generates packaged Milestone 13 outputs and asserts deterministic paths plus expected summary fields.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style fixture workflow that runs the packaged validation ladder, writes deterministic outputs, and asserts artifact discovery plus expected summary fields

Notes:
Assume `FW-M13-001` through `FW-M13-006` are already in place. This ticket is where Jack’s automation and reporting ownership becomes concrete: make the ladder easy to rerun, review, and gate without turning every validation pass into a bespoke notebook session. Do not attempt to create a git commit as part of this ticket.
