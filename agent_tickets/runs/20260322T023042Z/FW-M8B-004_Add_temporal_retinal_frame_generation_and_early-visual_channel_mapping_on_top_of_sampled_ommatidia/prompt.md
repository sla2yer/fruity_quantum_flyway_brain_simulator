Work ticket FW-M8B-004: Add temporal retinal frame generation and early-visual channel mapping on top of sampled ommatidia.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8B roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Raw per-ommatidium samples are not yet a full simulator-facing retinal representation. Milestone 8B also needs a defensible answer to how sampled detector values become time-indexed retinotopic input frames or early visual units that later simulator code can consume. Right now there is no canonical temporal bundling layer, no stable indexing for frame stacks, no place to record normalization or adaptation choices, and no shared mapping from ommatidial samples into the early-unit abstraction Grant defines.

Requested Change:
Build the temporal retinal-frame generation layer that turns sampled ommatidial values into deterministic time-indexed retinal bundles using the abstraction chosen in `FW-M8B-001`. Implement the default mapping from detector samples into the chosen simulator-facing retinal representation, record the metadata needed to explain that mapping, and keep the representation extensible enough that later milestones can add richer early-visual channels without breaking the default contract. The resulting bundle should be something later baseline and wave simulators can load directly instead of reverse-engineering raw detector samples.

Acceptance Criteria:
- There is a canonical API that turns sampled ommatidial values into deterministic retinal frames or early-visual units with explicit temporal indexing and metadata.
- The resulting retinal bundle records the mapping from raw detector samples to the simulator-facing representation, including any normalization, aggregation, polarity, or channel semantics required to reproduce the output.
- Constant or repeated source input produces stable, reproducible retinal frame outputs rather than subtly drifting or shape-changing bundle structure.
- The bundle is discoverable through the contract and loadable through library helpers rather than relying on implicit script-local array conventions.
- Regression coverage validates temporal bundling, mapping semantics, and representative steady-state or motion-onset cases using local fixtures only.

Verification:
- `make test`
- A focused unit or integration-style test that builds a small sampled detector sequence and asserts deterministic retinal-frame serialization plus early-unit mapping behavior

Notes:
Assume `FW-M8B-001` through `FW-M8B-003` are already in place. The main deliverable is a stable simulator handoff: later code should be able to load "retinal input" as a named contract, not reconstruct it from scattered detector arrays. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
