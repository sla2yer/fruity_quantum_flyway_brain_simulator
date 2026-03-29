Work ticket FW-M14-005: Implement the morphology pane with mixed-fidelity geometry rendering, activity overlays, and neuron inspection.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The roadmap says users should be able to click neurons and inspect them, but the repo still has no single morphology-focused viewer that can render the selected cells with activity overlays while respecting Milestone 11 mixed-fidelity classes. Surface meshes, skeleton approximations, and point fallbacks already exist as upstream concepts, yet there is no unified Milestone 14 pane that can show whichever representation is available, highlight selected neurons, and clearly distinguish between fairness-critical shared readout overlays and wave-only morphology-aware diagnostics. Without this pane, the dashboard cannot actually explain how structure and activity relate.

Requested Change:
Implement the Milestone 14 morphology pane using the packaged dashboard-session inputs and the existing mixed-fidelity morphology abstractions. The pane should render whichever geometry class is available for a selected neuron set, support linked camera focus and neuron inspection, and expose activity overlays that can switch among shared comparison signals, wave-only diagnostics, and other contract-approved overlay families while keeping those scopes visibly separated. Include sensible empty-state and unavailable-state handling so the dashboard remains truthful when a requested overlay or morphology fidelity is not present in the current session.

Acceptance Criteria:
- The morphology pane can render representative fixture neurons across the supported fidelity classes, including at least one surface-resolved case and one reduced-fidelity fallback case.
- A user can select neurons from elsewhere in the dashboard and inspect the corresponding morphology with synchronized highlighting, metadata, and camera focus updates.
- Overlay rendering supports at least the baseline shared-comparison case and one wave-only diagnostic case while labeling unavailable or inapplicable overlays clearly.
- The pane consumes existing geometry, morphology-class, and simulator-state exports through contract-backed discovery helpers rather than hardcoded file lookups.
- Regression coverage includes deterministic fixture tests for geometry discovery, fidelity fallback behavior, overlay normalization, and linked inspection state.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-005_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused smoke or integration-style test that renders a representative fixture morphology session, exercises at least one fidelity fallback and one overlay mode, and asserts stable pane metadata plus clear unavailable-state handling

Notes:
Assume `FW-M14-001` through `FW-M14-004` and the Milestone 5, 6, 10, and 11 morphology-related contracts are already in place. Preserve truthfulness over visual flash: if only a reduced geometry exists for a neuron in the active session, the pane should say so rather than fabricating surface detail. Do not attempt to create a git commit as part of this ticket.
