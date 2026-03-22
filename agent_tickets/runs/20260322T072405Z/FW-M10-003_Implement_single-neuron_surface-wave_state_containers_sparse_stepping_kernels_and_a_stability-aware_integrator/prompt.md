Work ticket FW-M10-003: Implement single-neuron surface-wave state containers, sparse stepping kernels, and a stability-aware integrator.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 10 cannot begin with multi-neuron wiring if the repo still lacks the actual single-neuron wave solver. The current simulator framework has no morphology-resolved state container, no canonical sparse operator application path for surface or patch state, no stability-aware time integrator for the chosen model family, and no deterministic stepping semantics for a distributed field state. Without that core, later tickets will either duplicate low-level solver logic or couple together incomplete one-off kernels that are too opaque to trust scientifically.

Requested Change:
Implement the first working single-neuron wave-solver core in library code. Build explicit state containers for the chosen field and auxiliary state variables, add sparse operator application against the Milestone 6 assets, and implement the chosen stability-aware integration method with deterministic stepping order and inspectable runtime metadata. The implementation should support localized pulse initialization, propagation and damping on real operator bundles or fixture stand-ins, boundary handling chosen by the contract, and lightweight per-step diagnostics that later validation work can reuse.

Acceptance Criteria:
- A canonical solver API can initialize, step, and finalize a single-neuron `surface_wave` state using the repo's operator assets or deterministic fixture operators.
- The implementation uses explicit state containers for the distributed field and any auxiliary variables rather than loose dictionaries of arrays passed through the runtime.
- Sparse operator application, boundary handling, and the chosen integration method are owned by library code and expose enough metadata for a reviewer to recover the realized solver mode and timestep assumptions.
- At least one localized pulse or impulse-style smoke case demonstrates stable single-neuron propagation and decay on fixture assets in a deterministic, test-covered way.
- Regression coverage validates deterministic stepping, stable initialization and finalization behavior, and representative single-neuron propagation behavior on local fixtures.

Verification:
- `make test`
- A focused solver test that initializes a localized single-neuron wave state, steps it for several iterations, and asserts deterministic propagation and damping behavior

Notes:
Assume `FW-M10-001`, `FW-M10-002`, and the Milestone 6 operator pipeline are already in place. Keep the first solver core inspectable and boring; a reviewer should be able to see exactly which operator, timestep, and update path produced a given trajectory. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
