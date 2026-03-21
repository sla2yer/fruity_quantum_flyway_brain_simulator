Work ticket FW-M5-003: Build explicit surface-graph and patch-graph artifacts for the multiresolution morphology bundle.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 5 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`scripts/03_build_wave_assets.py` currently emits a simplified mesh and one combined graph archive with an example patch mask. That is a good scaffold, but it is not yet a true multiresolution morphology bundle. Milestone 5 calls for explicit surface and patch graph assets, stable mappings between resolutions, and a clearer representation boundary between fine surface data and coarse simulation-ready patches.

Requested Change:
Refactor the processed-asset builder so it writes explicit surface-graph and patch-graph artifacts with well-defined metadata and mapping arrays. Preserve the simplified mesh output, but make the coarse representation first-class rather than an implicit mask tucked into a single archive. The result should be a bundle that a later simulator can consume without reverse-engineering the build step.

Acceptance Criteria:
- The processed output contains a first-class surface graph artifact and a first-class patch graph artifact instead of only one opaque combined archive.
- Patch generation is deterministic for the same mesh and config, and the bundle records the mapping from fine surface vertices to coarse patches.
- The processed manifest ties each multiresolution artifact back to the raw mesh and skeleton inputs used to build it.
- The implementation keeps graph construction in library code and leaves the script as a thin orchestration layer.
- Regression coverage validates artifact filenames, key arrays, graph dimensions, and deterministic behavior on fixture meshes.

Verification:
- `make test`
- A focused fixture-driven test that builds assets for a stub mesh and asserts the surface graph, patch graph, and mapping outputs

Notes:
Assume `FW-M5-001` has landed so the artifact layout is already settled. Keep formats easy to inspect and serialize; avoid burying unrelated structures in one monolithic file if separate artifacts make later operator work clearer.
