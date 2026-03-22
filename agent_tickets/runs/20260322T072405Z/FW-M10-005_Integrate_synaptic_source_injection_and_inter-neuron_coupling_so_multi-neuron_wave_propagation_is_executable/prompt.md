Work ticket FW-M10-005: Integrate synaptic source injection and inter-neuron coupling so multi-neuron wave propagation is executable.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 10 is not complete when a single neuron can support a wave in isolation. The roadmap requires multi-neuron propagation, which means the engine must consume the Milestone 7 coupling bundle, sample presynaptic wave readouts, apply delays and signs deterministically, and inject the resulting source terms onto the postsynaptic state space. Right now there is no wave-side coupling executor, no canonical definition of how a presynaptic surface state becomes a postsynaptic source, and no deterministic update ordering for a coupled morphology-resolved circuit.

Requested Change:
Implement the coupling execution layer that turns Milestone 7 coupling artifacts into live inter-neuron wave sources. The implementation should resolve presynaptic sampling anchors and postsynaptic landing anchors, apply the documented delay, sign, kernel, and aggregation semantics, and inject those contributions into the wave solver through library-owned logic rather than script-local glue. Keep the update ordering deterministic, support the topology conditions already used by the simulator manifests, and make the realized coupling metadata discoverable in run outputs for later comparison and debugging.

Acceptance Criteria:
- A canonical API can construct and execute a coupled multi-neuron `surface_wave` circuit from selected roots, operator bundles, and Milestone 7 coupling assets using only local repo artifacts.
- Presynaptic readout sampling, postsynaptic source injection, delay handling, sign semantics, and aggregation are applied through library-owned coupling logic rather than reimplemented ad hoc inside runner scripts.
- The same resolved circuit, coupling assets, and seed produce the same realized injection schedule and multi-neuron state evolution deterministically.
- Missing or incompatible anchors, unusable delay metadata, or unsupported mixed-resolution combinations fail clearly instead of being silently skipped.
- Regression coverage validates deterministic multi-neuron propagation on a small fixture circuit, including at least one coupling-sensitive or delay-sensitive case.

Verification:
- `make test`
- A focused integration-style test that runs a small coupled fixture circuit and asserts deterministic inter-neuron source injection plus multi-neuron propagation behavior

Notes:
Assume `FW-M10-001` through `FW-M10-004` and the Milestone 7 coupling pipeline are already in place. The main requirement is a stable connectome-constrained wave handoff, not a one-off coupling demo. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
