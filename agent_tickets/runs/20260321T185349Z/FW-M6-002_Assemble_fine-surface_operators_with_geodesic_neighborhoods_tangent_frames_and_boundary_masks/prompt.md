Work ticket FW-M6-002: Assemble fine-surface operators with geodesic neighborhoods, tangent frames, and boundary masks.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 6 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The current processed surface graph is still a Milestone 5 scaffold. It exposes simplified mesh connectivity and a uniform graph Laplacian, but it does not yet provide the numerical objects Milestone 6 actually needs: geodesic neighborhoods, boundary masks, local tangent frames, metric-aware weights, or a surface operator whose supporting geometry is explicit enough to debug and validate. That leaves the repo unable to build a simulation-ready single-neuron surface state without rewriting the existing graph archive by hand.

Requested Change:
Implement the fine-surface operator builder that turns a simplified mesh bundle into a numerically meaningful fine-resolution operator artifact. Use the discretization family chosen in `FW-M6-001`, and serialize the supporting geometry needed to inspect or reuse the operator later: adjacency and edge geometry, local areas or mass terms, normals and tangent frames, geodesic-neighborhood structures, and boundary masks. Keep sparse assembly in library code, make the script layer an orchestrator only, and ensure the output is deterministic for the same mesh and config.

Acceptance Criteria:
- A first-class fine-operator artifact is written for each processed neuron bundle using only local Milestone 5 assets.
- The artifact includes the chosen surface operator matrix plus the supporting arrays needed to interpret it, including boundary masks, local frames, and neighborhood or metric data required by the selected discretization.
- The implementation exposes enough metadata to distinguish operator family, weighting scheme, orientation convention, and any mass or area normalization applied during assembly.
- Regression coverage validates structural invariants on fixture meshes, such as matrix shape, sparsity consistency, deterministic output, and expected symmetry or definiteness properties for the chosen operator family.
- The build path remains library-owned and script-thin, with no duplicate sparse-assembly logic in CLI wrappers.

Verification:
- `make test`
- A fixture-driven test suite that assembles fine operators for one or more small meshes and asserts matrix invariants plus supporting-array integrity

Notes:
Assume `FW-M6-001` is already in place. Favor inspectable sparse formats and explicit metadata over opaque archives that require reverse-engineering at read time.
