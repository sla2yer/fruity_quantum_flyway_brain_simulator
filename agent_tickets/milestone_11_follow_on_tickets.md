# Milestone 11 Follow-On Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M11-FOLLOW-001 - Promote the shipped Milestone 11 readiness fixture into a richer branch-positive mixed-fidelity stress bundle
- Status: open
- Priority: high
- Source: Milestone 11 readiness follow-on 2026-03-22
- Area: verification / fixtures / mixed-fidelity policy

### Problem
The Milestone 11 readiness pass now proves that one surface root, one skeleton root, one routed point root, and one isolated point-surrogate root can coexist through planning, execution, cross-class routing, serialization, visualization, and surrogate inspection. That is the right first integration gate, but the shipped fixture is still intentionally small and synthetic: the skeleton asset is branch-free, the policy and inspection ladder exercise only one promotion candidate, and the mixed routes cover one representative loop rather than a broader delayed or branched circuit family.

### Requested Change
Expand the repo-owned Milestone 11 verification fixture into a richer but still fully local stress bundle. Keep the current deterministic three-class path as the minimum smoke surface, but add one follow-on fixture or verification mode with at least:

- a branch-positive skeleton asset
- more than one surrogate candidate for promotion review
- at least one delayed mixed route that remains visible in the shipped inspection and visualization artifacts
- enough fixture diversity that later readout and validation milestones are not forced to infer scientific confidence from one tiny loop

### Acceptance Criteria
- The repo still keeps one fast, deterministic Milestone 11 readiness command, but it gains a richer local mixed-fidelity verification fixture or mode for deeper review.
- The richer fixture remains local-artifact-only and deterministic across repeated runs.
- The richer fixture exercises branch-aware skeleton metadata, multiple surrogate roots, and at least one delayed mixed route end to end.
- Documentation distinguishes clearly between the minimum readiness gate and the broader mixed-fidelity stress review path.
- Regression coverage or smoke automation is updated so the richer fixture cannot silently drift once later milestones depend on it.

### Verification
- `make test`
- `make milestone11-readiness`
- The new richer mixed-fidelity verification command or documented short command sequence added by the implementation

### Notes
Keep this follow-on centered on fixture depth and review confidence, not on inventing a new simulator mode or reopening the Milestone 11 contract vocabulary.

## FW-M11-FOLLOW-002 - Teach mixed-fidelity inspection to regenerate coupling-compatible reference variants for promoted roots with incident edges
- Status: open
- Priority: high
- Source: Milestone 11 readiness follow-on 2026-03-22
- Area: inspection / mixed-fidelity coupling / verification

### Problem
The shipped mixed-fidelity inspection workflow now proves that a manifest-only fidelity promotion can produce a valid higher-fidelity reference arm for an isolated surrogate root. That keeps the local readiness gate deterministic and coherent, but it also exposes a remaining limitation: if the promoted root already participates in mixed-class coupling edges, the workflow still rewrites the manifest without regenerating incident coupling anchor geometry for the new morphology class.

### Requested Change
Extend the mixed-fidelity inspection workflow so it can build coupling-compatible reference variants for promoted roots that have incoming or outgoing mixed-class coupling bundles. The result should let a reviewer compare a surrogate root against a higher-fidelity reference without first hand-editing the readiness fixture to isolate that root from the routed circuit.

### Acceptance Criteria
- The inspection workflow can execute a higher-fidelity reference variant for a promoted root that has incident mixed-class coupling edges.
- The regenerated or adapted coupling assets preserve the published sign, delay, and aggregation invariants for the inspected reference run.
- The workflow remains deterministic across repeated runs on the same local fixture.
- Documentation explains the coupled-root reference behavior and any remaining limitations explicitly.
- Regression coverage is added so coupled-root promotion comparisons cannot silently regress.

### Verification
- `make test`
- `make milestone11-readiness`
- A focused mixed-fidelity inspection command or test added by the implementation that promotes a root with incident mixed-class coupling edges

### Notes
Keep the current fast readiness gate intact. This follow-on is about broadening the inspection workflow, not about replacing the minimum Milestone 11 readiness fixture.
