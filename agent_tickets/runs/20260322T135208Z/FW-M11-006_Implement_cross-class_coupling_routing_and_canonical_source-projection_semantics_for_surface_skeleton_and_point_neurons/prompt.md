Work ticket FW-M11-006: Implement cross-class coupling routing and canonical source-projection semantics for surface, skeleton, and point neurons.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 7 defined a fallback-aware coupling contract, but the live simulator still lacks execution-time routing between mixed morphology classes. Today the wave runtime assumes surface patch clouds on both sides of a coupling component, while a real Milestone 11 run must support combinations such as surface-to-skeleton, skeleton-to-surface, skeleton-to-point, and point-to-surface without changing the scientific sign, delay, and aggregation semantics. Without a canonical router, mixed-fidelity execution will either ignore class mismatches or quietly mutate coupling meaning across code paths.

Requested Change:
Build the library-owned coupling router that converts normalized coupling assets into executable source-projection and target-injection operations across all supported morphology-class pairs. Preserve the Milestone 7 sign, delay, aggregation, and fallback hierarchy semantics while making the class-to-class translation explicit and testable. The router should explain which representation pair was realized for each executed component and fail clearly when a requested cross-class route is unsupported or scientifically disallowed.

Acceptance Criteria:
- A canonical runtime layer can execute coupling between the supported morphology-class pairs using the normalized hybrid plan and existing coupling assets.
- Sign handling, delay handling, aggregation, and fallback behavior remain aligned with the Milestone 7 coupling contract rather than being redefined separately for each class pair.
- Runtime metadata records the realized source class, target class, projection route, and any fallback or blocked reason for each executed coupling component or component family.
- Unsupported or ambiguous cross-class routes fail clearly instead of silently dropping the connection or mutating it into an unrelated approximation.
- Regression coverage validates deterministic execution for representative surface-to-skeleton, skeleton-to-point, and point-to-surface or point-to-skeleton fixture cases using local artifacts only.

Verification:
- `make test`
- A focused mixed-coupling test module that exercises representative class-pair routes and asserts deterministic routing metadata plus sign and delay preservation

Notes:
Assume `FW-M11-001` through `FW-M11-005` and the Milestone 7 coupling pipeline are already in place. Keep the first router explicit and auditable: later work can broaden approximation families, but this ticket should make the realized translation path obvious for every executed edge. Do not attempt to create a git commit as part of this ticket.
