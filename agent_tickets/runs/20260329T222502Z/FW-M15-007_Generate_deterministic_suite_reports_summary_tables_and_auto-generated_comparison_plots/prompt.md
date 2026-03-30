Work ticket FW-M15-007: Generate deterministic suite reports, summary tables, and auto-generated comparison plots.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Jack explicitly owns summary tables and auto-generated comparison plots for this milestone, but the repo still has no suite-level review surface that turns aggregated results into something a reviewer can scan quickly. Even if the suite index and rollups exist, Milestone 15 is not done until the outputs are easy to compare, which means deterministic reports, stable table exports, and plot catalogs that do not require hand-written notebooks every time someone wants to review a sweep. Without a reporting layer, the suite machinery will technically run while still failing the milestone’s usability goal.

Requested Change:
Add the suite-level reporting workflow for Milestone 15. The implementation should generate deterministic local review artifacts from the packaged suite inventory and suite-level rollups, including summary tables, auto-generated comparison plots across key sweep dimensions and ablation families, and at least one lightweight offline report surface that links the plots back to the underlying suite cells and packaged experiment artifacts. Keep the first version local and reproducible rather than optimizing for a web service; a disciplined static HTML plus JSON and image export story is enough if the outputs remain easy to discover and review.

Acceptance Criteria:
- One documented local workflow can generate deterministic Milestone 15 review artifacts from a packaged suite inventory without reparsing raw per-experiment directories.
- The reporting layer emits summary tables, auto-generated comparison plots, and at least one lightweight offline report or visualization index for suite review.
- Reported plots and tables are metadata-backed and traceable to the underlying suite cells, comparison rows, and packaged experiment-level artifacts rather than being undocumented one-off files.
- The output catalog keeps fairness-critical shared-comparison content visibly separate from wave-only diagnostics and validation findings when those surfaces coexist in the same review artifact set.
- Regression coverage includes at least one fixture workflow that generates representative tables and plots, asserts deterministic output paths and expected summary metadata, and verifies that plot labeling stays stable across reruns.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style fixture workflow that builds a representative packaged suite report, exercises at least one table export and one comparison-plot export, and asserts deterministic artifact discovery plus expected summary metadata

Notes:
Assume `FW-M15-001` through `FW-M15-006` are already in place. The first reporting surface should optimize for trust and repeatability, not for maximal visual novelty; deterministic static outputs are acceptable if they make suite review fast and honest. Do not attempt to create a git commit as part of this ticket.
