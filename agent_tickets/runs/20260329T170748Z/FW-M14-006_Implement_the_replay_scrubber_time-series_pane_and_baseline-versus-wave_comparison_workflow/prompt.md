Work ticket FW-M14-006: Implement the replay scrubber, time-series pane, and baseline-versus-wave comparison workflow.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 14 is explicitly done only when the UI supports replay and comparison, but the repo still has no canonical time scrubber or shared replay model that ties scene, morphology, traces, and analysis together. Simulator bundles already share a timebase and readout catalog, and Milestone 12 already packages comparison-oriented outputs, yet there is no one interaction surface that lets a reviewer scrub time, play or pause, compare baseline versus wave traces on the same cursor, or keep neuron and readout selections coherent while switching between arms. Without this ticket, the dashboard will remain a set of disconnected snapshots rather than an actual analysis interface.

Requested Change:
Implement the Milestone 14 replay and comparison workflow. Add the global time scrubber and playback controls, build the time-series pane for shared readout traces and related comparison views, and support explicit baseline-versus-wave comparison mode on the shared timebase while keeping wave-only diagnostics visibly distinct. The workflow should synchronize the cursor across scene, circuit, morphology, and analysis panes, support selection-driven trace inspection, and fail clearly when a requested comparison is not valid because the current session lacks a compatible arm pair or shared timebase.

Acceptance Criteria:
- One canonical replay control surface drives the active time cursor for all panes in the dashboard and can play, pause, and scrub deterministically on packaged fixture sessions.
- The time-series pane shows shared readout traces or equivalent comparison-ready signals for the active selection and supports baseline-versus-wave comparison on the canonical shared timebase.
- The comparison workflow preserves the fairness boundary by distinguishing shared-comparison traces from wave-only diagnostics instead of merging them into one unlabeled chart.
- Switching selections, overlays, or compared arms updates the pane through the shared dashboard state rather than each pane managing an independent cursor or comparison model.
- Regression coverage validates shared-timebase alignment, comparison-mode normalization, deterministic replay-state serialization, and clear failure handling for incompatible comparison requests.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused integration-style test that loads a representative fixture dashboard session, drives the replay cursor and comparison mode, and asserts synchronized time-series metadata plus expected fairness-boundary labeling

Notes:
Assume `FW-M14-001` through `FW-M14-005` and the Milestone 9 through Milestone 12 comparison contracts are already in place. This ticket should establish the shared replay semantics that later showcase and experiment-orchestration work can trust. Do not attempt to create a git commit as part of this ticket.
