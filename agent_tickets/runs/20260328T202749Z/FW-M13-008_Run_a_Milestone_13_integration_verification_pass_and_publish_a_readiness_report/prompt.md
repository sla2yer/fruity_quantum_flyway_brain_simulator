Work ticket FW-M13-008: Run a Milestone 13 integration verification pass and publish a readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 13 roadmap 2026-03-26

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the individual Milestone 13 tickets land, the repo still needs one explicit integration pass proving that the validation ladder is a coherent, reusable capability rather than a stack of disconnected checks. Without a dedicated readiness ticket, it will be too easy to stop at isolated validator success while leaving behind hidden contract mismatches, broken report discovery, unreviewable failure output, or task-level conclusions that are no longer traceable back to the lower ladder layers.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 13 implementation and publish a concise readiness report in-repo. The pass should exercise the full validation ladder end to end on local fixtures and at least one representative manifest path, verify that the declared contract matches shipped behavior across numerical, morphology, circuit, and task layers, confirm that findings are packaged for regression use, and record any remaining scientific or engineering risks that later milestones must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

Acceptance Criteria:
- The full Milestone 13 validation workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic report location.
- The verification pass checks contract compatibility across validation-plan resolution, numerical-sanity validators, morphology-sanity validators, circuit-sanity validators, task-sanity validators, packaged exports, and regression-command discovery.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 13 is ready to support downstream dashboard and experiment-orchestration work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 13 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_13_validation_ladder_tickets.md --ticket-id FW-M13-008 --dry-run --runner true`
- A documented end-to-end local Milestone 13 validation command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 13 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the full validation ladder is deterministic, actionable, and fit to catch regressions before later milestones build on it. Do not attempt to create a git commit as part of this ticket.
