# FW-M17-002 Rationale

## Design choices

This ticket adds one library-owned planner, `flywire_wave.whole_brain_context_planning`, instead of another script-local assembler. The planner accepts one primary source of truth for the active context session:

- manifest
- subset bundle inputs
- packaged dashboard session inputs
- packaged showcase session inputs
- explicit artifact references

The implementation reuses the existing subset, dashboard-session, and showcase-session discovery helpers rather than guessing filenames. That keeps Milestone 17 aligned with the package contracts already shipped in Milestones 4, 14, and 16.

The planner normalizes all source modes into the same packaged surface:

- one deterministic `whole_brain_context_session.v1` metadata bundle
- one context-view payload
- one query-catalog payload
- one context-view state payload

Output locations are derived from the contract hash and experiment id, so the same resolved plan writes to the same bundle directory every time.

## Validation strategy

The new tests cover:

- deterministic subset-driven planning and packaging
- dashboard-session inputs resolving to the default bidirectional profile
- showcase-session inputs unlocking the review-only profiles and downstream-module requests
- explicit artifact overrides winning over discovered subset inputs
- failure handling for missing synapse evidence, unsupported query-profile combinations, and dashboard/subset mismatches

The whole-brain planner also validates local artifact compatibility before packaging:

- active root identities must resolve and stay stable
- subset manifest and subset stats must agree with the resolved active roots when present
- requested query profiles must be supported by the resolved artifacts
- dashboard and showcase links must stay traceable to the same active subset
- local synapse evidence must exist and include at least the root-id columns needed to prove active/context connectivity

## Simplifications

Milestone 17 planning is intentionally packaging-first.

- The representative context currently records the active anchors and the deterministic UI/query defaults, not a fully expanded whole-brain query result.
- Showcase linkage validates that showcase focus roots stay inside the resolved subset instead of forcing the current showcase focus to equal the entire subset.
- Synapse evidence loading is tolerant of older local fixture files that carry the required pre/post root identity columns but omit broader provenance columns that later pipeline stages may use.

## Future expansion

Likely follow-on work:

- add a dedicated CLI wrapper once downstream query execution is ready to consume the packaged surface directly
- expand representative context generation from anchor-only records to budgeted upstream/downstream preview nodes and edges
- attach richer downstream-module payloads once the query engine materializes them
- promote more artifact-override paths into higher-level readiness and export workflows
