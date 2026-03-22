Work ticket FW-M10-006: Integrate canonical visual input streams, manifest-driven `surface_wave` execution, and shared result-bundle serialization.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The milestone's done-when clause explicitly says the engine must run under actual visual input, but the repo still has no public path that executes `surface_wave` runs end to end from the experiment manifest. Without a manifest-driven execution path, the wave solver will remain an internal kernel that cannot be compared fairly against baseline mode, cannot feed the UI, and cannot prove that the same circuit and same input stream are reaching both simulator modes through a shared workflow.

Requested Change:
Extend the simulator execution entrypoint so `model_mode=surface_wave` manifest arms can run end to end using the repo's canonical local input stack. The implementation should resolve the normalized wave plan, consume the agreed input representation from the upstream visual-input milestones, execute the wave solver through the shared runtime, and write outputs into the shared simulator result-bundle layout introduced in Milestone 9. Preserve comparable readouts, provenance, logs, and UI-facing payloads so later metrics and dashboard work can switch between baseline and wave runs without reverse-engineering a second result schema.

Acceptance Criteria:
- A documented local command or script can execute `model_mode=surface_wave` manifest arms end to end using only local repo artifacts and write outputs into deterministic result-bundle paths.
- The written bundle follows the shared simulator result contract while adding the wave-specific metadata, state summaries, or snapshot references needed to interpret morphology-resolved runs.
- The same manifest and local asset identity produce reproducible `surface_wave` output locations, provenance fields, logs, and comparison-ready readouts for a given seed.
- The execution path reuses library-owned planning, runtime, and serialization helpers rather than implementing a parallel script-local output layout.
- Regression coverage includes at least one smoke-style fixture manifest run that asserts deterministic bundle identity, shared readout payloads, and discovery of wave-specific outputs.

Verification:
- `make test`
- A smoke-style fixture run that executes a `surface_wave` manifest arm and asserts deterministic result-bundle paths, summary fields, and comparison-ready payload discovery

Notes:
Assume `FW-M10-001` through `FW-M10-005`, the Milestone 9 simulator contract, and the relevant upstream local input contracts are already in place. Favor one clean public execution path over multiple partially overlapping scripts; later mixed-fidelity and analysis work should extend this workflow rather than compete with it. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
