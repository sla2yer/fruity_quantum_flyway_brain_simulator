Work ticket FW-M10-004: Add recovery, nonlinearity, anisotropy, and branching-aware wave mechanics with explicit guardrails.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
A purely linear propagation kernel is not enough to satisfy the roadmap's required model ingredients. Milestone 10 explicitly calls for recovery or refractory behavior, nonlinearities, optional anisotropy, and optional branching effects, yet the repo currently has no disciplined way to represent any of those in a scientifically reviewable form. If they are added ad hoc inside the step loop, the team will not be able to tell whether a changed output came from the intended model family, a hidden numerical trick, or a morphology-specific tuning loophole.

Requested Change:
Extend the wave-solver core with the additional model mechanics required by the chosen Milestone 10 family. Implement the documented recovery or refractory state evolution, the chosen nonlinearity or saturation behavior, optional anisotropy that consumes the Milestone 6 operator metadata or anisotropy settings, and a narrow but real branching-aware modifier path grounded in existing geometry descriptors rather than freeform heuristics. Make the supported combinations explicit, validate them during planning or initialization, and expose enough runtime metadata and diagnostics that later sweep and validation tooling can distinguish intended model features from disabled or identity modes.

Acceptance Criteria:
- The chosen `surface_wave` family can run with documented recovery or refractory behavior and nonlinear response enabled through normalized config rather than hidden internal constants.
- Optional anisotropy and branching-aware modifiers are real implemented modes with test coverage, while identity anisotropy and disabled branching reproduce the simpler solver behavior within documented tolerances.
- Invalid or scientifically disallowed parameter combinations fail clearly instead of silently mutating into another realized model.
- Runtime metadata records which optional mechanics were active for a run, including recovery mode, nonlinearity mode, anisotropy mode, and branching modifier mode.
- Regression coverage validates representative recovery dynamics, bounded nonlinear behavior, anisotropy identity equivalence, and at least one branch-sensitive fixture case using local assets only.

Verification:
- `make test`
- A focused solver test module that exercises recovery dynamics, nonlinear bounds, anisotropy identity behavior, and a small branch-sensitive fixture case

Notes:
Assume `FW-M10-001` through `FW-M10-003` are already in place. Keep the first branching and anisotropy extensions intentionally narrow and explicit so they remain scientifically auditable. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
