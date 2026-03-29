# FW-M14-002 Rationale

## Design Choices

This ticket adds one library-owned planner, `flywire_wave.dashboard_session_planning`, instead of another script-local directory scan. The planner accepts three entry modes:

- manifest-driven resolution for the canonical Milestone workflow
- experiment-driven resolution for local replay against already packaged analysis and validation bundles
- explicit bundle-driven resolution for future export, showcase, and debugging flows

The planner reuses existing bundle metadata contracts and discovery helpers after bundle selection. Simulator, experiment-analysis, validation, and dashboard-session metadata remain the source of truth for paths, bundle IDs, and deterministic output locations. That keeps Milestone 14 packaging aligned with Milestones 9 through 13 rather than introducing a second naming scheme.

The normalized plan is intentionally pane-oriented. It records the five pane inputs, selected arm pair, active overlay state, artifact references, and deterministic output paths in one payload so later UI code can consume a packaged session without reparsing raw repo directories.

## Testing Strategy

Regression coverage uses the existing simulator and analysis fixture stack, then adds a minimal packaged validation bundle on top. The new tests verify:

- deterministic manifest resolution and deterministic dashboard-session packaging
- convergence between experiment-driven and explicit bundle-driven entrypoints
- explicit bundle precedence over ambiguous arm/seed/condition overrides
- clear failures for missing wave-only diagnostics, insufficient morphology metadata, and mismatched paired timebases

The tests stay close to the real bundle contracts instead of mocking the planner inputs from scratch. That makes them more useful as contract-regression tests for later Milestone 14 UI work.

## Simplifications

The packaged app shell is a deterministic placeholder HTML entrypoint, not a production UI. It exists so downstream work can rely on a stable packaged surface now while FW-M14-003 owns the actual offline shell behavior.

Overlay availability is resolved from packaged artifact presence plus a small set of domain guards in the planner. It does not yet attempt pane-specific rendering readiness beyond the current Milestone 14 contract requirements.

## Future Expansion

Likely follow-up work:

- add richer overlay-readiness checks that inspect wave extension artifacts directly for morphology-specific overlays
- expose replay/export-specific planner wrappers that reuse the same normalized session plan
- tighten packaged session payload schemas once the Milestone 14 UI shell starts consuming them directly
