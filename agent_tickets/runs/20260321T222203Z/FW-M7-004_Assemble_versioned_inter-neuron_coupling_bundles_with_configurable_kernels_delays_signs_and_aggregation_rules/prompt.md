Work ticket FW-M7-004: Assemble versioned inter-neuron coupling bundles with configurable kernels, delays, signs, and aggregation rules.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 7 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even with synapse rows and anchor maps in place, the repo would still lack the actual object Milestone 7 promises: a simulator-readable definition of how activity transfers between neurons. There is no versioned bundle that captures which presynaptic anchors are read, which postsynaptic anchors are driven, whether the transfer is point-like or distributed, how synaptic sign is represented, how delays are computed, how multiple synapses on one edge aggregate, or how those rules should modify downstream surface state.

Requested Change:
Build the coupling assembly layer that turns mapped synapses into versioned inter-neuron coupling bundles. Use the topology mode, kernel family, and fallback rules chosen in `FW-M7-001`; group mapped synapses by edge; apply configurable sign handling, delay models, and aggregation rules; and emit a coupling artifact that downstream simulator code can consume without reverse-engineering raw synapse rows. Keep the bundle library-owned and script-thin, and make the configuration explicit enough that later baseline and wave simulators can share the same coupling metadata even if they interpret it differently.

Acceptance Criteria:
- A first-class coupling bundle artifact is written for each relevant edge or root pair using the canonical contract rather than ad hoc filenames.
- The bundle records presynaptic readout anchors, postsynaptic landing anchors, coupling-topology mode, kernel family, sign semantics, delay model, aggregation rule, and any normalization or weight totals needed to reproduce the transfer.
- Config plumbing exposes stable defaults while still allowing the supported coupling topology, sign, delay, and aggregation modes to be chosen explicitly and recorded in metadata.
- Downstream code can discover and load the bundle through library helpers instead of reconstructing coupling from raw synapse rows or implicit script conventions.
- Regression coverage validates deterministic bundle serialization plus the implemented semantics for sign handling, delay assignment, and multiple-synapse aggregation on fixture edges.

Verification:
- `make test`
- A focused fixture test that assembles one or more edge-level coupling bundles and asserts payload invariants, deterministic serialization, and the documented sign or delay semantics

Notes:
Assume `FW-M7-001` through `FW-M7-003` are already in place. The main requirement is not merely having another archive; it is having a coupling handoff that later simulator work can treat as a stable, inspectable contract.
