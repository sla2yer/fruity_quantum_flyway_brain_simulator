Work ticket FW-M11-004: Build the skeleton-neuron asset handoff, graph approximation, and deterministic skeleton runtime adapter.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo already fetches raw SWC skeletons and uses skeleton anchors for coupling fallback, but it still has no simulator-facing skeleton morphology class. There is no canonical processed skeleton-graph handoff for runtime consumption, no deterministic skeleton-state container, and no graph-based approximation path that can stand in for a surface neuron while still participating in the same simulator architecture. Without that, Milestone 11 would claim skeleton support while actually treating skeletons only as coupling-localization helpers.

Requested Change:
Implement the first real skeleton-neuron approximation path end to end. Add a deterministic skeleton asset handoff suitable for runtime use, define the graph operator or reduced propagation structure required by the chosen approximation strategy, and implement a skeleton runtime adapter that conforms to the shared morphology-class interface from `FW-M11-003`. The resulting class should support initialization, stepping, source injection, readout export, and coupling projection using only local cached artifacts and documented approximation semantics.

Acceptance Criteria:
- There is a canonical runtime-discoverable skeleton asset representation or bundle that a mixed-fidelity plan can reference deterministically.
- The skeleton-neuron implementation exposes an explicit state container, graph or reduced operator payload, and documented readout semantics rather than loose script-local arrays.
- A mixed-fidelity plan can include at least one skeleton neuron that runs through the shared simulator lifecycle alongside surface-class peers.
- Missing, invalid, or scientifically unsupported skeleton inputs fail clearly instead of silently degrading to point behavior.
- Regression coverage validates deterministic skeleton-asset discovery, stable single-neuron skeleton stepping on local fixtures, and compatibility with the shared morphology-class runtime interface.

Verification:
- `make test`
- A focused fixture test that builds or loads a small skeleton asset, runs the skeleton adapter for several steps, and asserts deterministic state and readout behavior

Notes:
Assume `FW-M11-001` through `FW-M11-003` are already in place. Keep the first skeleton approximation narrow, well documented, and easy to audit; later biological tuning and richer branch-sensitive behavior can build on that stable contract. Do not attempt to create a git commit as part of this ticket.
