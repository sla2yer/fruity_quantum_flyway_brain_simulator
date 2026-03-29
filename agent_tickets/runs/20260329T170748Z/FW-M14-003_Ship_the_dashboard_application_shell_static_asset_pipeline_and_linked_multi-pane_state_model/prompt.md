Work ticket FW-M14-003: Ship the dashboard application shell, static asset pipeline, and linked multi-pane state model.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo already has deterministic static reports for several earlier milestones, but Milestone 14 needs a true interactive dashboard rather than one more isolated report page. There is currently no application shell that can load a packaged dashboard session, no shared client-side or view-model state for linked selection and replay, no five-pane layout, no deterministic way to open the dashboard from local artifacts, and no decision on how to keep the first implementation reviewable without requiring backend services. Without a real shell and state model, later pane work will either duplicate logic across HTML reports or hardcode fragile assumptions about how selection, playback, and comparison state should be synchronized.

Requested Change:
Implement the first working Milestone 14 dashboard shell around the packaged dashboard-session surface. Build the static asset or bundled-view pipeline required by the chosen UI delivery model, create the five-pane layout skeleton, and introduce one canonical linked state model that owns selected arms, selected neurons, selected readouts, active overlays, playback state, and time cursor updates across the whole application. Provide at least one documented local command or script that can generate the dashboard artifacts and open the result from local disk, while preserving deterministic packaged outputs suitable for repo fixtures and readiness audits.

Acceptance Criteria:
- A documented local command or script can build and open a Milestone 14 dashboard from packaged local artifacts without requiring live FlyWire access.
- The dashboard shell renders the five top-level panes declared by the contract and supports linked global state for selection, overlay mode, comparison mode, and replay cursor updates.
- The chosen app-shell implementation remains compatible with deterministic local packaging, meaning the review artifact can be regenerated from the same packaged session inputs with stable asset identities.
- The initial layout behaves cleanly on desktop and remains legible on smaller laptop-sized widths, even if some panes collapse into tabs or stacks in the first version.
- The implementation includes a deterministic smoke fixture or regression harness that verifies packaged app generation, global-state bootstrapping, and stable loading of representative fixture dashboard sessions.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-003_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style dashboard-build test that generates a fixture Milestone 14 dashboard artifact, loads a representative session payload, and asserts stable output paths plus expected pane and state metadata

Notes:
Assume `FW-M14-001` and `FW-M14-002` are already in place. The goal here is the durable shell and shared state model, not the full scientific richness of every pane. Do not attempt to create a git commit as part of this ticket.
