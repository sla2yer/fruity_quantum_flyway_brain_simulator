Work ticket FW-M10-007: Ship systematic parameter sweeps, stability diagnostics, and offline wave inspection tooling.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 10 is only complete if parameters can be swept systematically and if the team can inspect whether the realized wave behavior is physically meaningful rather than numerically suspicious. Right now the repo has no standard local workflow for sweeping the new model parameters, no deterministic stability or artifact diagnostics, and no offline inspection report that shows how single-neuron and coupled wave trajectories behave over time. Without that tooling, the team will be forced to judge the engine from raw arrays or one-off notebooks, which is too weak a foundation for Milestones 12 and 13.

Requested Change:
Add a parameter-sweep and wave-inspection workflow that consumes normalized `surface_wave` plans and emits deterministic reports. The workflow should support grid or preset-based parameter exploration, repeatable seed handling, compact diagnostics for stability and artifact detection, representative state snapshots or traces, and summary metrics such as wavefront speed, damping behavior, coherence, energy-like quantities, or other contract-approved diagnostics that make the solver's behavior reviewable. Output paths should be deterministic and lightweight enough for local audit and regression testing.

Acceptance Criteria:
- A documented local command or script can run a deterministic local parameter sweep over one or more `surface_wave` plans without requiring live FlyWire access.
- The sweep outputs record the explored parameter combinations, seed context, stability or artifact flags, representative readouts, and deterministic report paths suitable for later review or comparison.
- An offline inspection report is generated in a review-friendly format such as Markdown plus images, HTML, or another lightweight local artifact that summarizes single-neuron and multi-neuron wave behavior.
- The implementation surfaces clear pass, warn, or fail conditions for obviously unstable, degenerate, or numerically suspicious runs rather than leaving every interpretation to manual inspection.
- At least one smoke-style automated test generates a fixture sweep or inspection report and asserts deterministic output paths plus expected summary fields.

Verification:
- `make test`
- A smoke-style fixture run that executes a small `surface_wave` parameter sweep and asserts deterministic report contents, summary diagnostics, and output paths

Notes:
Assume `FW-M10-001` through `FW-M10-006` are already in place. This is not the final UI; it is the local audit layer that helps Grant and Jack decide whether the engine is stable, meaningful, and ready for formal metrics work. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
