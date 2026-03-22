Work ticket FW-M10-002: Extend manifest-driven simulation planning and config normalization for `model_mode=surface_wave`.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo now has baseline-oriented simulation planning, but there is still no canonical planning layer that turns a manifest arm into an executable wave run. A `surface_wave` arm needs operator assets, coupling assets, input references, resolution choices, solver defaults, parameter presets, and stability guardrails resolved together, yet none of that is normalized today. Without a shared planning API, each runner will parse `surface_wave` manifests differently, miss prerequisites in inconsistent ways, and encode wave-only assumptions directly into CLI scripts.

Requested Change:
Extend the library-owned simulation planning layer so manifests and config can resolve `model_mode=surface_wave` arms into normalized wave execution plans. The API should consume the existing experiment-manifest structure, validate required local prerequisites, normalize the chosen wave-model parameters and runtime defaults, resolve operator and coupling asset references, and assign deterministic run identities and output locations. Keep the representation explicit enough that later sweep, validation, and mixed-fidelity tickets can reuse the same planning surface instead of inventing a second wave-specific execution path.

Acceptance Criteria:
- There is one canonical API that resolves a manifest plus local config into normalized `surface_wave` run plans with explicit defaults and stable arm ordering.
- The normalized plan records the manifest-level input reference, selected roots, operator assets, coupling assets, topology condition, timebase, integration timestep, seed handling, model parameters, and deterministic output locations needed to launch a wave run.
- `model_mode=surface_wave` arms fail clearly when required local prerequisites are missing, ambiguous, or scientifically incompatible, including absent operators, incompatible coupling anchors, or unstable timestep settings for the chosen solver mode.
- The same manifest-resolution path remains shared with baseline planning so later comparison tooling can treat baseline and wave runs as sibling modes rather than separate systems.
- Regression coverage validates normalization, plan determinism, missing-prerequisite failures, and representative fixture-manifest resolution using only local artifacts.

Verification:
- `make test`
- A focused unit test that resolves a fixture manifest into `surface_wave` run plans and asserts normalized output, deterministic IDs, and clear error handling

Notes:
Assume `FW-M10-001` and the Milestone 9 planning layer are already in place. Favor one planning surface that extends the existing simulator contract rather than a parallel wave-only loader that would drift immediately. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
