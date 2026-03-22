Work ticket FW-M11-003: Refactor the wave runtime around a pluggable morphology-class interface while preserving current surface behavior.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The current `surface_wave` runtime is organized around a surface-only execution path with `SingleNeuronSurfaceWaveSolver`, surface operator bundles, and patch-cloud coupling semantics baked directly into the circuit assembly. That is a good Milestone 10 implementation, but it is not yet a stable architecture for Milestone 11 because adding a skeleton or point class would currently require threading special cases through the same surface-specific code paths. Without a shared morphology-class runtime interface, every later fidelity class will either duplicate simulator plumbing or force a risky rewrite after functionality already lands.

Requested Change:
Refactor the mixed-fidelity runtime around a narrow pluggable morphology-class interface and migrate the existing surface implementation onto it first. The interface should cover initialization, stepping, state export, readout export, source injection, and coupling-facing projection in a way that remains deterministic and inspectable. Preserve current surface-run behavior and result compatibility while making it possible for later tickets to add skeleton and point implementations without changing the surrounding simulator architecture again.

Acceptance Criteria:
- There is a library-owned morphology-class runtime interface or adapter layer that the simulator uses instead of calling the surface solver directly as a special case.
- The existing surface implementation is migrated onto that interface without regressing current pure-surface fixture behavior beyond documented tolerances.
- The runtime exposes enough shared metadata that later classes can serialize comparable state summaries, readouts, and coupling projections without inventing their own ad hoc result formats.
- Pure-surface `surface_wave` arms remain executable through the refactored runtime using the same public command surface and deterministic result-bundle layout.
- Regression coverage verifies that the refactor preserves representative Milestone 10 surface behavior and that the new interface is sufficient to host at least one lightweight stub class in tests.

Verification:
- `make test`
- Focused regression tests that run a representative pure-surface fixture before and after the refactor path and assert deterministic compatibility through the new interface

Notes:
Assume `FW-M11-001` and `FW-M11-002` are already in place. The main deliverable is architectural headroom with no Milestone 10 behavior loss: make the runtime more general without making the current surface path harder to reason about. Do not attempt to create a git commit as part of this ticket.
