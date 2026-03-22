Work ticket FW-M7-001: Freeze a versioned synapse asset contract and inter-neuron coupling design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 7 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo currently stops at per-neuron geometry and operator bundles plus an aggregated connectivity registry. Milestone 7 needs a first-class handoff contract for synapse-level data and inter-neuron coupling artifacts, but there is no canonical definition for where synapse-derived assets live, how downstream code discovers them, how coupling topology is encoded, or how sign, delay, aggregation, and morphology fallback decisions are documented. Without a versioned contract and a decisive design note, later simulator and UI work will bind itself to ad hoc filenames, undocumented semantics, and incompatible assumptions about what a "coupling edge" means.

Requested Change:
Define a first-class synapse and coupling contract for Milestone 7 and document the design choices behind it. Centralize asset naming and manifest metadata in library code, extend the processed manifest so downstream consumers can discover the local synapse registry plus any per-root or per-edge coupling artifacts without hardcoded paths, and add a markdown design note that compares the viable coupling-topology families before committing to the default. The design note should be decisive: choose the default among point-to-point, patch-to-patch, and distributed patch-cloud coupling, define the fallback hierarchy for surface, skeleton, and point-neuron representations, and state how sign, delay, missing geometry, and multi-synapse aggregation must be represented for later simulator code.

Acceptance Criteria:
- Synapse and coupling path construction is centralized in library code rather than being reimplemented inside scripts.
- The processed manifest records an explicit synapse-contract or coupling-contract version plus discoverable pointers to the local synapse registry, anchor-map artifacts, coupling bundles, and the design-note version they conform to.
- A dedicated markdown design note compares the supported coupling-topology families, chooses the default, names the supported fallback modes, and documents the invariants later milestones must preserve when consuming the coupling bundle.
- `docs/pipeline_notes.md` is updated so the Milestone 7 contract sits alongside the existing geometry and operator contracts.
- Regression coverage verifies deterministic contract serialization, manifest discovery, and compatibility for existing geometry or operator consumers that should continue to work unchanged.

Verification:
- `make test`
- A focused unit test that builds fixture synapse or coupling metadata and asserts deterministic manifest serialization plus bundle discovery

Notes:
This ticket should land first. Keep the contract boring and explicit: one place to build paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the coupling model.
