Work ticket FW-M8A-001: Freeze a versioned stimulus bundle contract and canonical generator design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo currently exposes only lightweight stimulus identifiers such as `stimulus_family` and `stimulus_name` in the example experiment manifest, but it has no first-class contract for what a canonical visual stimulus actually is. There is no library-owned definition for stimulus coordinates, luminance semantics, temporal sampling, seeded randomness, cacheable artifacts, replay metadata, or how later milestones should discover a reusable stimulus bundle. Without a versioned contract and a decisive design note, Milestones 8B, 8C, 9, and 15 will end up binding themselves to ad hoc frame layouts and incompatible assumptions about what it means to "replay the same stimulus."

Requested Change:
Define a first-class canonical stimulus bundle contract in library code and document the design choices behind it. Centralize bundle naming, metadata, and discovery so later tooling can resolve a stimulus without hardcoded filenames, and add a markdown design note that compares the viable representation families before choosing the default. The design note should be decisive: choose the default between pure procedural regeneration, fully cached frame bundles, and a hybrid descriptor-plus-cache model; define the canonical spatial coordinate frame and temporal units; specify luminance or contrast conventions; and state how deterministic seeding, parameter hashing, and compatibility aliases must work.

Acceptance Criteria:
- Stimulus bundle path construction and metadata serialization are centralized in library code rather than being reimplemented inside scripts.
- The chosen contract records an explicit stimulus-contract version plus the metadata needed to reproduce a stimulus deterministically, including timing, spatial frame, luminance conventions, and parameter snapshot or hash.
- A dedicated markdown design note compares the supported representation strategies, chooses the default, documents the coordinate and timing conventions, and names the invariants later retinal-sampling and simulator code must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 8A contract sits alongside the existing subset, geometry, and operator contracts.
- Regression coverage verifies deterministic contract serialization, stable path generation, and bundle discovery for fixture stimulus specs.

Verification:
- `make test`
- A focused unit test that builds fixture stimulus metadata and asserts deterministic manifest or bundle serialization plus path discovery

Notes:
This ticket should land first. Keep the contract implementation boring and explicit: one place to build paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the representation model. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
