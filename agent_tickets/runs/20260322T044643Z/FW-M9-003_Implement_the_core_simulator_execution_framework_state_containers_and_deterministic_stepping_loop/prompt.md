Work ticket FW-M9-003: Implement the core simulator execution framework, state containers, and deterministic stepping loop.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 9 cannot start from a bag of per-neuron update functions. The repo still lacks the simulator framework itself: there is no canonical runtime object for one experiment arm, no fixed-timestep stepping loop, no typed state container, no lifecycle for initialization versus update versus readout extraction, and no shared execution interface that later `surface_wave` code could plug into. Without that core, baseline implementation will hardcode orchestration details that should have been reusable engine plumbing.

Requested Change:
Build the core simulator execution framework in library code. The framework should own run initialization, fixed-timestep stepping, state storage, deterministic update ordering, lightweight instrumentation hooks, and structured snapshot extraction. Design it so scalar baseline state is easy to implement now, while the same top-level run interface can later host morphology-resolved state for `surface_wave` without rewriting orchestration, serialization, or monitoring logic.

Acceptance Criteria:
- There is a canonical simulator runtime API that can initialize, step, and finalize a run with deterministic ordering and explicit lifecycle boundaries.
- Typed or otherwise explicit state containers represent per-neuron dynamic state, exogenous drive, recurrent input accumulation, and readout-ready summaries without relying on loose dicts passed everywhere.
- The stepping loop exposes the integration timestep, current simulation time, seed or determinism context, and lightweight hooks for logging or metric collection.
- The framework is engine-agnostic enough that a future wave solver can implement the same top-level interface without replacing manifest planning or result-bundle plumbing.
- Regression coverage validates deterministic stepping on local fixture circuits, stable initialization and finalization behavior, and representative snapshot extraction.

Verification:
- `make test`
- A focused simulator-runtime test that steps a small fixture circuit and asserts deterministic state evolution plus lifecycle behavior

Notes:
Assume `FW-M9-001` and `FW-M9-002` have landed. Keep the runtime boring, explicit, and inspectable; later solver work should be able to trust the orchestration layer rather than work around it. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
