Work ticket FW-M14-007: Implement the analysis pane, scientific overlay catalog, and deterministic export tools for images, video, and metrics.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The dashboard is supposed to surface metrics, heatmaps, ablations, phase maps, and exportable outputs, but the repo currently stops at packaged analysis and validation artifacts plus separate offline reports. There is no interactive analysis pane that can bring together task-summary cards, matrix views, phase-map references, validation-ladder findings, and experiment-level comparisons under one linked dashboard state. There is also no canonical export layer for turning the current dashboard view into deterministic images, videos, or metrics exports. Without this ticket, the Milestone 14 UI may look interactive while still failing the roadmap requirement that the project become understandable and shareable through polished analysis views and exports.

Requested Change:
Implement the Milestone 14 analysis pane together with the first scientific overlay catalog and export workflow. The pane should render packaged Milestone 12 and Milestone 13 outputs such as task-summary cards, comparison cards, matrix-like views, ablation summaries when present, phase-map references, and validation evidence, while keeping shared-comparison content, wave-only diagnostics, and reviewer-oriented validation findings visibly separated. Add deterministic export tools that can capture the current dashboard state as local review artifacts, including at least still-image export, metrics export, and one replay-oriented export path such as a video artifact or deterministic frame sequence suitable for later encoding.

Acceptance Criteria:
- The analysis pane can display representative packaged Milestone 12 and Milestone 13 outputs from the active dashboard session without reparsing raw simulator bundle directories.
- Overlay selection is contract-backed and explicit, with clear labeling for shared-comparison overlays, wave-only diagnostics, validation overlays, and unavailable overlays.
- The export workflow can generate deterministic local artifacts for at least still images, metrics-oriented data export, and one replay-oriented export path from the current dashboard state.
- Exported artifacts are discoverable through documented local commands or metadata-backed output paths rather than hidden temporary files.
- Regression coverage includes at least one fixture workflow that exercises analysis-pane payload discovery, overlay normalization, and deterministic export output paths plus expected summary fields.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-007_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style fixture workflow that builds a representative analysis-pane session, exercises at least one overlay selection and one export path, and asserts deterministic artifact discovery plus expected export metadata

Notes:
Assume `FW-M14-001` through `FW-M14-006` and the Milestone 12 and Milestone 13 packaging layers are already in place. Keep the first export story honest and reproducible; a deterministic frame-sequence export is acceptable if a full video container proves too heavy for the initial version. Do not attempt to create a git commit as part of this ticket.
