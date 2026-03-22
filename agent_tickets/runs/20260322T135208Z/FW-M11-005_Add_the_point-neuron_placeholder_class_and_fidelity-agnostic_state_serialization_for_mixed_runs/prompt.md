Work ticket FW-M11-005: Add the point-neuron placeholder class and fidelity-agnostic state serialization for mixed runs.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Point-level placeholders already exist as a concept in registry roles and baseline simulator logic, but mixed-fidelity wave-side execution still lacks a first-class point-neuron class inside the same runtime. There is also no fidelity-agnostic state serialization layer that can tell downstream tooling how to load surface, skeleton, and point state from one run without hardcoding class-specific file rules. If Milestone 11 adds point placeholders only as internal shortcuts, downstream readout, validation, and UI work will inherit an opaque special case instead of a stable mixed-class contract.

Requested Change:
Implement the point-neuron morphology class inside the shared mixed-fidelity runtime and add fidelity-agnostic state and readout serialization for mixed runs. Reuse existing baseline family behavior where that is scientifically appropriate, but normalize it through the Milestone 11 contract so a point placeholder can coexist with surface and skeleton neurons in one result bundle. The written outputs should let later metrics, validation, and UI code discover per-root class, state summary, and readout payloads without reverse-engineering runtime internals.

Acceptance Criteria:
- A mixed-fidelity plan can include one or more point-neuron placeholders that execute through the shared morphology-class runtime rather than a separate baseline-only path.
- Result-bundle metadata records the realized morphology class for every root and points to class-appropriate but contract-consistent state and readout artifacts.
- Shared state-summary and readout loading helpers can consume mixed runs without the caller having to guess which roots were surface, skeleton, or point implementations.
- Constant or repeated fixture input produces stable point-class output structure and deterministic serialization across repeated runs.
- Regression coverage validates mixed-run serialization, deterministic point-class behavior, and discovery of per-root fidelity metadata through library helpers.

Verification:
- `make test`
- A focused integration-style test that runs a small mixed fixture containing at least one point placeholder and asserts deterministic mixed-class serialization plus helper-based discovery

Notes:
Assume `FW-M11-001` through `FW-M11-004` are already in place. Favor one clear result contract over a pile of class-specific one-off files; later Milestone 12 and Milestone 14 tooling should be able to load mixed runs through shared helpers first. Do not attempt to create a git commit as part of this ticket.
