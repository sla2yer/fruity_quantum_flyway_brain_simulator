Work ticket FW-M5-001: Define a versioned geometry asset contract for multiresolution morphology bundles.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 5 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The current geometry handoff contract is too narrow for Milestone 5. The repo documents a simplified mesh, one graph archive, and one metadata file, but the roadmap requires a fuller per-neuron bundle that can account for raw mesh, simplified mesh, skeleton, surface graph, patch graph, derived descriptors, and the versioned preprocessing choices that produced them. Without a centralized asset contract, later milestones will end up binding themselves to ad hoc filenames and partially duplicated script logic.

Requested Change:
Introduce a single versioned geometry asset contract in library code and apply it across the fetch and build steps. Define the canonical per-neuron output layout, manifest fields, naming rules, and build metadata needed for multiresolution morphology assets. The contract should make it obvious which raw and processed files belong to a neuron, which config values shaped them, and which bundle version downstream code is reading.

Acceptance Criteria:
- Geometry bundle path construction is centralized in library code instead of being reimplemented in multiple scripts.
- The processed manifest records, per root ID, the canonical locations and statuses for raw mesh, raw skeleton, simplified mesh, surface graph, patch graph, descriptor sidecar, and QA sidecar.
- The manifest includes an explicit asset-contract version plus the dataset, materialization version, and meshing config snapshot used to build the bundle.
- Existing pipeline scripts write outputs that conform to the new contract, or a documented compatibility shim keeps current consumers working while the repo migrates.
- Regression coverage verifies manifest structure, version fields, and deterministic path generation for fixture builds.

Verification:
- `make test`
- A focused unit or integration-style test that builds a fixture geometry bundle and asserts the manifest contents and output layout

Notes:
This is the foundation ticket for the rest of the Milestone 5 work and should land first. Keep the contract implementation small and boring: one code path for path building, one code path for manifest writing, and no script-specific naming rules.
