Work ticket FW-M9-006: Ship manifest-driven baseline execution, result serialization, logging, metrics, and UI-ready comparison payloads.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 9 is not done when a baseline simulation can run only from Python internals. The same experiment manifest must run in baseline mode, baseline outputs must line up with later wave-mode outputs for comparison, and the UI must be able to switch between modes without reverse-engineering custom file layouts. Right now there is no documented command that executes a manifest arm end-to-end, no deterministic result serialization for run logs and metrics, and no UI-facing comparison payload that uses the shared contract described in the roadmap.

Requested Change:
Add the public execution and result-handoff layer for baseline mode. This should include a thin local command or script that resolves a manifest into baseline runs, executes them through the simulator framework, writes the versioned result bundle, records structured logs and provenance, and emits comparison-ready metrics plus UI-facing payloads that follow the shared simulator and UI contracts. The output should be shaped so later `surface_wave` runs can write into the same high-level layout and comparison tooling can switch modes without special-casing baseline internals.

Acceptance Criteria:
- A documented local command or script can execute `model_mode=baseline` manifest arms end-to-end using only local repo artifacts and write outputs into deterministic result-bundle paths.
- The written bundle includes run metadata, structured logs, per-neuron or per-readout summaries, shared output traces, metric tables, and UI-facing payloads needed for side-by-side comparison with future `surface_wave` runs.
- The baseline output schema is aligned with the shared result-bundle and UI contracts so later tooling can switch modes without guessing at filenames or field semantics.
- Result serialization and logging remain deterministic and provenance-rich enough that repeated runs can be diffed and audited locally.
- Regression coverage includes at least one smoke-style fixture manifest run that asserts deterministic output files, summary fields, and UI-payload discovery.

Verification:
- `make test`
- A smoke-style fixture run that executes a baseline manifest arm and asserts deterministic bundle identity, summary metrics, and UI-facing payload structure

Notes:
Assume `FW-M9-001` through `FW-M9-005` are already in place. Favor one clean user-facing execution path over multiple half-overlapping scripts; later wave-mode work should extend this workflow, not compete with it. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
