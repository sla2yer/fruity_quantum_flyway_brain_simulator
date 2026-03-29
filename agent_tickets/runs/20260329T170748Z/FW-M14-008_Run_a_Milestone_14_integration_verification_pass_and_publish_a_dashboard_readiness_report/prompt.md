Work ticket FW-M14-008: Run a Milestone 14 integration verification pass and publish a dashboard readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the individual Milestone 14 tickets land, the repo still needs one explicit integration pass proving that the new dashboard is a coherent, reviewable interface rather than a stack of disconnected pane demos. Without a dedicated readiness ticket, it will be too easy to stop at isolated rendering success while leaving behind hidden contract mismatches, broken bundle discovery, desynchronized replay state, misleading overlay boundaries, or export paths that only work on one hand-crafted fixture. Milestone 15 experiment orchestration and Milestone 16 showcase mode will both depend on this interface being stable and trustworthy.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 14 implementation and publish a concise readiness report in-repo. The pass should exercise the full local dashboard workflow end to end on fixture artifacts and at least one representative manifest or experiment path, verify that the declared dashboard contract matches shipped behavior across scene, circuit, morphology, time-series, and analysis panes, confirm that replay and comparison state stay synchronized, and record any remaining product, scientific, or engineering risks that Milestones 15 and 16 must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

Acceptance Criteria:
- The full Milestone 14 dashboard workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic readiness-report location.
- The verification pass checks contract compatibility across dashboard-session planning, packaged session discovery, app-shell loading, scene-pane rendering, circuit inspection, morphology rendering, replay and time-series synchronization, analysis-pane payload discovery, and export workflow behavior.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 14 is ready to support Milestone 15 experiment orchestration and Milestone 16 showcase mode.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 14 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_14_ui_analysis_dashboard_tickets.md --ticket-id FW-M14-008 --dry-run --runner true`
- A documented end-to-end local Milestone 14 dashboard verification command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 14 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the dashboard is deterministic, understandable, comparison-ready, and fit to support the next milestones. Do not attempt to create a git commit as part of this ticket.
