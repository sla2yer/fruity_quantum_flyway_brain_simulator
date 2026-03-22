Work ticket FW-M8B-001: Freeze a versioned retinal input bundle contract and ommatidial sampling design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8B roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 8A can define and replay canonical visual stimuli, but the repo still has no first-class contract for what the fly-facing retinal output actually is. There is no library-owned definition for retinal bundle paths, eye indexing, ommatidial ordering, coordinate frames, temporal sampling semantics, sampling-kernel metadata, or how later simulator and UI code should discover a reusable retinal recording. Without a versioned contract and a decisive design note, Milestones 8C, 9, 10, and 14 will bind themselves to ad hoc frame arrays and incompatible assumptions about what one "retinal frame" means.

Requested Change:
Define a first-class retinal input bundle contract in library code and document the design choices behind it. Centralize bundle naming, manifest metadata, and artifact discovery so later tooling can resolve sampled retinal outputs without hardcoded filenames, and add a markdown design note that compares the viable abstraction families before choosing the default. The design note should be decisive: choose the default among direct per-ommatidium irradiance, eye-image raster intermediates, and higher-level retinotopic feature maps; define the canonical world, body, head, and eye coordinate frames; specify temporal units and luminance or contrast conventions; and state which invariants later scene, simulator, and UI code must preserve.

Acceptance Criteria:
- Retinal bundle path construction and metadata serialization are centralized in library code rather than being reimplemented inside scripts.
- The chosen contract records an explicit retinal-contract version plus the metadata needed to reproduce a retinal recording deterministically, including source stimulus or scene identity, eye or lattice specification, frame timing, coordinate-frame conventions, and sampling-kernel settings.
- A dedicated markdown design note compares the supported retinal abstraction families, chooses the default, documents the coordinate and timing conventions, and names the invariants later Milestones 8C, 9, and 10 must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 8B contract sits alongside the existing subset, geometry, coupling, and operator contracts.
- Regression coverage verifies deterministic contract serialization, stable path generation, and bundle discovery for fixture retinal specs.

Verification:
- `make test`
- A focused unit test that builds fixture retinal metadata and asserts deterministic manifest or bundle serialization plus path discovery

Notes:
This ticket should land first. Keep the contract boring and explicit: one place to build retinal paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the sampling model. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
