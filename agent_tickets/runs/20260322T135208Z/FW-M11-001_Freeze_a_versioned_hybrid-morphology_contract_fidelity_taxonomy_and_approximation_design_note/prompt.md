Work ticket FW-M11-001: Freeze a versioned hybrid-morphology contract, fidelity taxonomy, and approximation design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo now has strong contracts for geometry bundles, coupling bundles, retinal input, baseline execution, and `surface_wave` execution, but there is still no first-class contract for mixed morphology fidelity inside one simulator run. Role labels such as `surface_simulated`, `skeleton_simulated`, and `point_simulated` already exist in registry and coupling code, yet they do not currently define one canonical simulator-facing meaning for required assets, state layout, coupling anchor resolution, readout semantics, approximation limits, or promotion and demotion rules. Without a versioned hybrid contract, Milestone 11 work will drift across planner code, runtime glue, and result serialization, and it will be too easy to implement a mixed run that is operationally convenient but scientifically ambiguous.

Requested Change:
Define a library-owned hybrid-morphology contract and publish a concise design note that locks the Milestone 11 vocabulary. The contract should name the supported simulator-facing morphology classes, their required and optional local assets, their state and readout semantics, the allowed cross-class coupling routes, and the invariants that must remain stable when a neuron is promoted from point to skeleton to surface fidelity. Prefer extending the existing `surface_wave` planning and execution path with per-root morphology-class metadata instead of introducing a separate top-level simulator mode, unless a hard compatibility blocker is discovered and documented.

Acceptance Criteria:
- There is one canonical hybrid-morphology contract in library code with explicit identifiers for `surface_neuron`, `skeleton_neuron`, and `point_neuron` or equivalently named normalized classes.
- The contract records, per class, the required assets, realized state space, readout surface, coupling anchor resolution, serialization requirements, and approximation notes needed for deterministic planning and review.
- A dedicated markdown design note explains what each fidelity class is allowed to approximate, which semantics must remain invariant across promotion and demotion, and which behaviors are intentionally class-specific.
- `docs/pipeline_notes.md` is updated so mixed morphology sits alongside the existing geometry, coupling, retinal, and simulator contracts rather than living only in code comments.
- Regression coverage verifies deterministic contract serialization, stable class discovery, and normalization of representative fixture class metadata.

Verification:
- `make test`
- A focused unit test that builds fixture hybrid-morphology metadata and asserts deterministic contract serialization plus class discovery

Notes:
This ticket should land first and give the later tickets a stable vocabulary. Reuse Milestone 7, Milestone 9, and Milestone 10 contract language where those milestones already define anchor semantics, shared readouts, and result-bundle expectations. Do not attempt to create a git commit as part of this ticket.
