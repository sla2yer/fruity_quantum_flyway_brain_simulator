Work ticket FW-M11-008: Run a Milestone 11 mixed-fidelity integration pass and publish a readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the earlier Milestone 11 tickets land, the repo still needs one explicit integration pass proving that mixed fidelity is a coherent simulator capability rather than a pile of partially compatible adapters. Without a dedicated readiness ticket, it will be too easy to stop once one surface root, one skeleton root, and one point placeholder can all run independently, while leaving behind hidden planner drift, broken cross-class routing, unreadable result bundles, or undocumented gaps between fidelity policy and executed behavior.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 11 implementation and publish a concise readiness report in-repo. The pass should exercise the full local mixed-fidelity workflow on fixture assets, verify that planning, runtime execution, cross-class coupling, result serialization, and inspection tooling agree with the published contract, and identify any remaining scientific or engineering risks that later milestones must respect. Fix any discovered contract mismatches directly where reasonable, and record the rest as explicit follow-on tickets rather than leaving them implicit.

Acceptance Criteria:
- The full Milestone 11 mixed-fidelity workflow is executed end to end using shipped local commands and fixture assets, with outputs captured in a deterministic report location.
- The verification pass checks contract compatibility across per-root fidelity planning, runtime adapter behavior, skeleton and point execution, cross-class coupling routing, mixed-class serialization, and surrogate-preservation inspection.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether mixed fidelity is ready to support downstream readouts, validation, and UI work.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same mixed-fidelity integration failures are less likely to recur silently.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_11_hybrid_morphology_classes_tickets.md --ticket-id FW-M11-008 --dry-run --runner true`
- A documented end-to-end local mixed-fidelity verification command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 11 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that surface, skeleton, and point classes coexist in one deterministic workflow and that upgrading a neuron does not require rewriting the simulator. Do not attempt to create a git commit as part of this ticket.
