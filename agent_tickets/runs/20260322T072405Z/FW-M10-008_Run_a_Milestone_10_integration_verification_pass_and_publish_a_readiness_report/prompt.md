Work ticket FW-M10-008: Run a Milestone 10 integration verification pass and publish a readiness report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 10 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even if the individual Milestone 10 build tickets land, the repo still needs one explicit integration pass that proves the wave engine is a coherent simulator mode rather than a collection of disconnected solver components. Without a dedicated readiness ticket, it is too easy to stop at isolated solver success while leaving behind manifest drift, hidden contract mismatches, weak stability checks, broken result-bundle compatibility, or undocumented gaps between the single-neuron kernel, coupled execution, visual-input integration, and sweep tooling.

Requested Change:
Perform a senior-level verification pass over the completed Milestone 10 implementation and publish a concise readiness report in-repo. This pass should exercise the full local `surface_wave` workflow on fixture assets and at least one representative manifest path, confirm that documentation matches shipped behavior, verify that outputs remain comparison-ready for baseline mode, identify any numerical or scientific risks that remain open, and either fix those gaps directly or record them as explicit follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

Acceptance Criteria:
- The full Milestone 10 `surface_wave` workflow is executed end to end using the shipped commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across wave-model discovery, manifest planning, single-neuron solver behavior, recovery and nonlinearity modes, anisotropy and branching options, coupling execution, canonical input integration, result serialization, and parameter-sweep or inspection tooling.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 10 is ready to support downstream mixed-fidelity, metrics, validation, and UI milestones.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

Verification:
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_10_surface_wave_engine_tickets.md --ticket-id FW-M10-008 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

Notes:
This ticket should run after the earlier Milestone 10 tickets are complete. The main deliverable is confidence: one place where a reviewer can see that `surface_wave` mode is integrated, deterministic, scientifically reviewable, and ready for downstream milestones. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
