Work ticket FW-M9-007: Run a Milestone 9 integration verification pass and publish a readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the Milestone 9 build tickets land individually, the repo still needs one explicit integration pass that proves baseline mode is a real control simulator and not just a partially wired runtime. Without a dedicated verification ticket, it is too easy to stop at isolated engine tests while leaving behind manifest drift, weak fairness guarantees, mismatched output schemas, missing UI payloads, or hidden determinism failures that would only appear once `surface_wave` implementation starts.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 9 implementation and publish a concise readiness report in-repo. This pass should exercise the full local baseline workflow on fixture assets and at least one representative manifest path, confirm that documentation matches shipped behavior, verify that baseline outputs are comparison-ready for later wave-mode runs, and either fix any gaps directly or record them as explicit follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

Acceptance Criteria:
- The full Milestone 9 baseline workflow is executed end-to-end using the shipped command or commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across manifest planning, runtime execution, `P0` and `P1` behavior, coupling and input integration, result serialization, logging, metrics, and UI-facing payloads.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 9 is ready to support downstream `surface_wave`, metrics, and UI comparison work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_9_baseline_non_wave_simulator_tickets.md --ticket-id FW-M9-007 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 9 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that baseline mode is integrated, deterministic, comparison-ready, and prepared for the later wave engine to plug into the same workflow. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
