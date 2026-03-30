Work ticket FW-M15-004: Implement canonical ablation transform families for the required Milestone 15 manipulations.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 15 names a concrete ablation set, but the repo still has no canonical software surface for realizing those manipulations reproducibly. Right now there is no deterministic transform layer that can take one base suite cell and derive the required variants for no waves, waves only on chosen cell classes, no lateral coupling, shuffled synapse locations, shuffled morphology, coarser geometry, or altered sign or delay assumptions. Without explicit transform semantics, later runs will quietly mean different things when two people say they ran the same ablation, and the resulting comparisons will be hard to interpret or reproduce.

Requested Change:
Build the library-owned ablation transform layer for Milestone 15. It should derive normalized ablation variants from a base suite cell or normalized experiment plan, attach explicit ablation provenance, and keep any ablation-specific RNG or perturbation seed separate from the simulator seed so the causal effect of the ablation remains auditable. The implementation should support the full required roadmap set and should make it obvious where the first version intentionally simplifies a perturbation family, such as bounding the first altered sign or delay assumption modes to a documented subset rather than pretending the whole scientific design space is already covered.

Acceptance Criteria:
- Each required Milestone 15 ablation family has a stable software identity and one deterministic transform path from a base suite cell to a realized ablation variant.
- The implementation supports the roadmap-required ablations: no waves, waves only on chosen cell classes, no lateral coupling, shuffled synapse locations, shuffled morphology, coarser geometry, and altered sign or delay assumptions.
- Every realized ablation variant carries explicit provenance describing which transform was applied, which inputs were perturbed, and which ablation-specific RNG seed or deterministic perturbation policy was used.
- The transform layer fails clearly when an ablation cannot be realized because required prerequisites are missing, such as unavailable cell-class assignments, absent coupling bundles, unavailable geometry variants, or unsupported sign or delay modes.
- Regression coverage includes representative fixture cases for each required ablation family plus at least one clear failure case for a missing prerequisite or unsupported perturbation request.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- Focused fixture-driven tests that realize each required ablation family from deterministic base plans and assert stable provenance plus clear failure behavior

Notes:
Assume `FW-M15-001` through `FW-M15-003`, the Milestone 6 geometry contract, the Milestone 7 coupling contract, and the Milestone 9 through Milestone 12 planning surfaces are already in place. Grant owns deciding which ablations are scientifically most diagnostic; this ticket makes those declared manipulations reproducible in software. Do not attempt to create a git commit as part of this ticket.
