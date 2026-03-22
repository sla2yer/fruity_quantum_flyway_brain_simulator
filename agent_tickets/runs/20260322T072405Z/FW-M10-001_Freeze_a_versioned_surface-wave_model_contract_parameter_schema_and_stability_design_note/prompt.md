Work ticket FW-M10-001: Freeze a versioned surface-wave model contract, parameter schema, and stability design note.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 9 gives the repo a baseline simulator runtime and result-bundle contract, while Milestones 6 and 7 provide operator and coupling assets, but the repo still has no first-class contract for the wave model itself. There is no canonical definition for the chosen model family, state variable names and units, parameter presets, solver-mode identifiers, synaptic source semantics, recovery-state semantics, optional anisotropy or branching modifiers, or which stability assumptions later tickets are allowed to rely on. Without a versioned wave-model contract and a decisive design note, the actual equations will drift into solver internals, manifest parsing will become inconsistent, and later validation work will struggle to distinguish scientific intent from implementation accident.

Requested Change:
Define a first-class surface-wave model contract in library code and document the numerical and scientific choices behind it. Centralize wave-model naming, parameter normalization and serialization, contract-version metadata, and design-note discovery so later planning, execution, and result tooling can resolve one canonical `surface_wave` family without hardcoded strings. The design note should compare the candidate model families named in the roadmap, choose the default family for Milestone 10, define the state variables, propagation term, damping term, recovery or refractory behavior, synaptic source injection semantics, nonlinearities, optional anisotropy and branching extensions, and state what counts as physically meaningful behavior versus a numerical artifact.

Acceptance Criteria:
- Wave-model identifiers, parameter path construction, and metadata serialization are centralized in library code rather than duplicated inside scripts or solver modules.
- The chosen contract records an explicit wave-model contract version plus the normalized parameters and defaults needed to reproduce a `surface_wave` run deterministically, including state-variable definitions, solver family, damping and recovery settings, nonlinearity mode, anisotropy mode, and branching mode.
- A dedicated markdown design note compares the viable Milestone 10 model families, chooses the default, documents the stability-relevant assumptions and parameter ranges, and names the invariants later execution, metrics, and validation tickets must preserve.
- `docs/pipeline_notes.md` is updated so the wave-model contract sits alongside the geometry, operator, coupling, stimulus, retinal, and simulator contracts already in the repo.
- Regression coverage verifies deterministic contract serialization, stable model discovery, and compatibility of normalized fixture parameter bundles.

Verification:
- `make test`
- A focused unit test that builds fixture wave-model metadata and asserts deterministic contract serialization plus discovery

Notes:
This ticket should land first. Reuse Milestone 1, Milestone 6, and Milestone 9 language where those documents already answer fairness or stability questions instead of forking duplicate definitions. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
