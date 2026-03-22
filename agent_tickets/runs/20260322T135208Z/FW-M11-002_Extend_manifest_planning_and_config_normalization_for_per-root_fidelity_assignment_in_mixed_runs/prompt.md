Work ticket FW-M11-002: Extend manifest planning and config normalization for per-root fidelity assignment in mixed runs.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The current simulation planner can resolve baseline and `surface_wave` arms, but it still assumes one morphology-state strategy per arm. In particular, the wave-side planning path hardcodes one surface-oriented state resolution, one coupling anchor resolution, and one operator inventory story for every selected root. That prevents a single run from cleanly mixing full surface neurons with skeleton approximations and point placeholders, and it leaves no canonical place to express class overrides from registry defaults, manifest arms, or future scheduler-driven promotion rules.

Requested Change:
Extend the library-owned planning layer so a manifest plus config resolves into a deterministic mixed-fidelity execution plan with explicit per-root fidelity assignment. Normalize the chosen morphology class for each selected root, validate the required local assets for that class, record the realized approximation route, and preserve stable arm ordering and result-bundle identity. The planner should support registry-default roles, arm-level overrides, and a narrow policy surface for future promotion and demotion logic without forcing every caller to invent its own class-resolution code.

Acceptance Criteria:
- There is one canonical API that resolves a manifest plus local config into normalized per-root morphology assignments for a mixed run.
- The normalized arm plan records, for each selected root, the realized morphology class, required local asset references, state and coupling resolution, and any approximation-policy provenance needed to explain why that class was chosen.
- The planner fails clearly when a requested class lacks required local prerequisites, such as missing operator bundles for surface neurons, missing usable skeleton assets for skeleton neurons, or incompatible coupling expectations for point placeholders.
- Existing baseline and pure-surface plans remain supported without forcing callers to fork into a separate planning workflow.
- Regression coverage validates deterministic per-root assignment, class override precedence, missing-prerequisite failures, and representative fixture-manifest resolution using local artifacts only.

Verification:
- `make test`
- A focused unit or integration-style test that resolves a fixture manifest into a mixed-fidelity arm plan and asserts deterministic per-root class assignment plus clear error handling

Notes:
Assume `FW-M11-001` and the Milestone 9 through Milestone 10 planning layers are already in place. Keep the first implementation strict and explicit: later tickets should inherit normalized fidelity assignments from one planner surface rather than negotiating them independently. Do not attempt to create a git commit as part of this ticket.
