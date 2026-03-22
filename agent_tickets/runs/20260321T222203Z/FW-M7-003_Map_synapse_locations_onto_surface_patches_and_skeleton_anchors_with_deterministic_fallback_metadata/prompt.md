Work ticket FW-M7-003: Map synapse locations onto surface patches and skeleton anchors with deterministic fallback metadata.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 7 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 6 gives the repo per-neuron geometry, patch, and operator bundles, but nothing yet translates synapse locations into addresses on those state spaces. The roadmap explicitly calls for locating nearest patches or skeleton nodes and building fast lookup structures, yet the repo has no artifact or API that says where a postsynaptic landing sits on the receiving surface, where a presynaptic readout should be sampled, or how mapping quality and fallback decisions should be recorded when surface geometry is missing or unsuitable.

Requested Change:
Implement the synapse-anchor mapping layer that consumes the local synapse registry plus geometry bundles and emits deterministic lookup artifacts. Postsynaptic synapses should map to receiving-surface anchors using the default resolution chosen in `FW-M7-001`, while presynaptic sites should map to the corresponding readout anchors on the source neuron. The implementation must support the documented fallback hierarchy for surface, skeleton, and point-neuron representations, serialize mapping distances and residuals, and provide fast query helpers for common access patterns such as inbound synapses to a root, outbound synapses from a root, and all mapped synapses for one edge.

Acceptance Criteria:
- A first-class mapping artifact or sidecar is written for the mapped roots or edges and is discoverable from the manifest or coupling contract.
- Each mapped synapse records presynaptic and postsynaptic anchor information, chosen anchor type and resolution, mapping quality metrics, and any fallback or blocked-prerequisite reason.
- Library helpers support efficient edge-level and root-level lookups without requiring downstream simulator code to scan the entire raw synapse table.
- Missing or low-quality mappings surface as structured statuses rather than silent drops, and those statuses are documented.
- Regression coverage validates deterministic mapping behavior on fixture meshes, plus at least one fallback case that uses a skeleton or reduced anchor when a surface anchor is unavailable.

Verification:
- `make test`
- A fixture-driven test that maps synthetic synapses onto a small mesh and optional skeleton and asserts anchor assignments, lookup outputs, and fallback metadata

Notes:
Assume `FW-M7-001` and `FW-M7-002` have landed. Keep the raw nearest-neighbor mechanics inspectable and deterministic; later physics work will only be credible if the localization layer is easy to audit.
