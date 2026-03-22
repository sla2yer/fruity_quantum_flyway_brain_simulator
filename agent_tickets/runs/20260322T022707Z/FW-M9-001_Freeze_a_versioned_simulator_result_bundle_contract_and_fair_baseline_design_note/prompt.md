Work ticket FW-M9-001: Freeze a versioned simulator result bundle contract and fair baseline design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo has a Milestone 1 design lock, manifest schema, coupling bundles, and stimulus-side contracts, but it still has no simulator-owned contract for what one baseline run produces. There is no canonical definition for run-directory layout, per-arm metadata, timebase fields, state-summary payloads, readout traces, comparison-ready metric tables, or how later UI and wave-mode code should discover the same baseline outputs deterministically. Without a versioned result contract and a decisive design note, Milestones 9, 10, 12, 13, and 14 will each invent their own run bundle shape and baseline semantics.

Requested Change:
Define a first-class simulator result bundle contract in library code and document the baseline-model design choices behind it. Centralize run-path construction, metadata serialization, and output discovery so baseline and later `surface_wave` runs can share the same high-level bundle shape. The design note should be decisive: pin down what `P0` and `P1` mean in software terms, define the shared timebase and readout conventions, state what a fair baseline is allowed to add versus what only the wave model may add, and specify the invariants later metrics, UI, and comparison tooling must preserve.

Acceptance Criteria:
- Simulator result-bundle path construction, metadata serialization, and bundle discovery are centralized in library code rather than duplicated inside runner scripts.
- The chosen contract records an explicit simulator-contract version plus the metadata needed to reproduce a run deterministically, including manifest and arm identity, model mode, baseline family, selected asset references, timing, seed, readout catalog, and output artifact inventory.
- A dedicated markdown design note compares the supported baseline families, chooses the default `P0` and `P1` realizations, documents shared readout conventions, and names the invariants later `surface_wave` and UI work must preserve.
- `docs/pipeline_notes.md` is updated so the simulator result contract sits alongside the subset, geometry, coupling, and stimulus contracts.
- Regression coverage verifies deterministic contract serialization, stable path generation, and bundle discovery for fixture baseline run specs.

Verification:
- `make test`
- A focused unit test that builds fixture simulator-run metadata and asserts deterministic bundle serialization plus path discovery

Notes:
This ticket should land first. Reuse the Milestone 1 design-lock language wherever it already answers the fairness question instead of re-litigating the scientific claim in code comments. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
