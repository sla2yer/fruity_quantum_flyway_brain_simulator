Work ticket FW-M8A-007: Run a Milestone 8A integration verification pass and publish a readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the contract, generator, manifest, and replay tickets land individually, the repo still needs one explicit integration pass that verifies Milestone 8A works as a coherent canonical stimulus system. Without a dedicated verification ticket, it is too easy to stop at isolated generator success while leaving behind contract drift, broken manifest discovery, preview gaps, weak determinism checks, or family-specific inconsistencies that will only surface once Milestone 8B and later simulator work start depending on these stimuli.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 8A implementation and publish a concise readiness report in-repo. This pass should exercise at least one representative example from every required Milestone 8A family, confirm that manifest and config entrypoints resolve through the canonical registry, validate deterministic record and replay behavior, and check that documentation matches the shipped commands and metadata. Treat this as an integration and audit ticket rather than a net-new feature ticket, and either close gaps directly or record them as explicit follow-on issues.

Acceptance Criteria:
- The full Milestone 8A workflow is executed end-to-end using the shipped commands and local fixture assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across the stimulus registry, family generators, manifest or config resolution, recording and replay bundles, and offline preview outputs.
- The readiness report summarizes which stimulus families were exercised, what determinism or compatibility checks passed, what remains risky or deferred, and whether Milestone 8A is ready to support Milestones 8B, 8C, and later experiment orchestration.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_8a_canonical_stimulus_library_tickets.md --ticket-id FW-M8A-007 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 8A tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the canonical stimulus library is integrated, reproducible, and ready for the rest of the visual input stack. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
