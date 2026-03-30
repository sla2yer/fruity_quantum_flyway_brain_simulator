# FW-M16-001 Rationale

## Design Choices

This ticket introduces one library-owned showcase contract instead of letting
Milestone 16 emerge from dashboard session dumps, suite plots, and export
scripts that each invent their own story vocabulary.

`flywire_wave.showcase_session_contract` freezes:

- one explicit `showcase_session.v1` bundle surface
- stable seven-step ids for the polished story
- stable preset ids, cue kinds, narrative-annotation ids, evidence-role ids,
  operator-control ids, export-target-role ids, and presentation-status ids
- metadata-backed artifact hooks for upstream dashboard sessions, suite
  rollups, Milestone 12 analysis outputs, Milestone 13 validation findings, and
  showcase-owned preset or export artifacts

Another deliberate choice is to make the ownership boundary machine-visible
instead of leaving it implied in milestone prose:

- Jack owns presentation mechanics and export surfaces
- Grant owns approval of the scientific comparison and wave-specific highlight

The scientific fallback rule is also fixed early. If the requested highlight is
not available or defensible, the contract does not permit a substitute effect.
It redirects to the reserved fallback preset and requires a visible fallback
annotation.

## Testing Strategy

Coverage is intentionally focused on the two regression risks in this ticket.

`tests/test_showcase_session_contract.py` verifies:

- deterministic contract serialization even when the contract catalogs are
  passed back in humanized and reversed order
- stable discovery of showcase steps, preset identities, artifact hooks, and
  export target roles
- deterministic fixture showcase-session metadata serialization from
  representative upstream artifact references, saved presets, and showcase-step
  records
- stable discovery of showcase steps and showcase-owned artifact roles from the
  normalized fixture metadata

That matches the point of this ticket: freeze vocabulary and discovery first so
later Milestone 16 playback or export work has one contract to depend on.

## Simplifications

This first Milestone 16 ticket stays narrow.

- It does not implement the actual scripted playback engine.
- It reserves export targets and showcase-owned artifact slots without deciding
  the final rendering stack.
- It keeps the scientific guardrail logic at the contract and metadata level
  instead of building a richer approval workflow.
- It uses compact unit fixtures rather than a full dashboard-plus-suite package
  regeneration flow.

Those simplifications keep the scope aligned with the ticket: vocabulary lock,
not full showcase implementation.

## Future Expansion Points

Likely follow-up work:

- write the actual `showcase_script.json` and `showcase_state.json` payloads
  from dashboard-session inputs
- implement export-manifest population for stills, clips, and review bundles
- add richer validation of step-to-evidence compatibility once later showcase
  tickets know which packaged analysis or validation payload slices they use
- connect the reserved fallback semantics to a real scientific approval UI or
  review workflow if Milestone 16 needs more than the current explicit
  metadata boundary
