Work ticket FW-M15-008: Run a Milestone 15 integration verification pass and publish an orchestration readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the earlier Milestone 15 tickets land individually, the repo still needs one explicit integration pass proving that a full suite can run from manifest-driven declarations, required ablations are reproducible, and the resulting outputs are genuinely easy to compare. Without a dedicated readiness ticket, it will be too easy to stop at isolated planner success, one successful ablation transform, or one nice-looking plot while leaving behind hidden mismatches among suite planning, batch execution, artifact indexing, aggregation, and reporting. Milestone 16 showcase work will depend on this orchestration layer being stable and reviewable.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 15 implementation and publish a concise readiness report in-repo. The pass should exercise the full local suite workflow end to end on fixture artifacts and at least one representative manifest-driven suite path, verify that the declared contract matches shipped behavior across suite planning, batch execution, ablation derivation, suite packaging, rollup computation, and reporting, and record any remaining scientific or engineering risks that later showcase or deeper scientific sweep work must respect. Fix defects or documentation drift directly where reasonable, and turn the rest into explicit follow-on tickets rather than leaving them implicit.

Acceptance Criteria:
- The full Milestone 15 suite workflow is executed end to end using shipped local commands and fixture artifacts, with outputs captured in a deterministic readiness-report location.
- The verification pass checks contract compatibility across suite-manifest resolution, deterministic work scheduling, ablation transform realization, suite artifact indexing, suite-level rollups, and report or plot generation.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 15 is ready to support Milestone 16 showcase work and larger scientific review loops.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same Milestone 15 integration failures are less likely to recur silently.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-008_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_15_experiment_orchestration_ablations_tickets.md --ticket-id FW-M15-008 --dry-run --runner true`
- A documented end-to-end local Milestone 15 suite command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 15 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that full suites run from manifest-driven declarations, required ablations are reproducible, and the resulting comparisons are deterministic and reviewable. Do not attempt to create a git commit as part of this ticket.
