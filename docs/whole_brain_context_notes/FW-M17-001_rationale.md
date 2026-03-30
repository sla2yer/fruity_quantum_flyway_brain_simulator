# FW-M17-001 Rationale

## Design choices

This ticket freezes one contract-owned Milestone 17 vocabulary before any
larger whole-brain graph payloads or UI flows exist.

The implementation chooses a session-style contract, not a raw graph-export
contract, for three reasons:

1. Milestone 17 needs deterministic packaging and discovery more than it needs
   one final graph format.
2. The repo already uses session contracts for Milestone 14 and Milestone 16,
   so reusing that pattern keeps replay state, artifact discovery, and local
   packaging semantics aligned.
3. The scientific boundary is easier to keep honest when node roles, edge
   roles, pathway highlights, and downstream modules are first-class contract
   terms instead of ad hoc per-export annotations.

The contract is intentionally narrow:

- subset selection still owns active membership
- `coupling_bundle.v1` still owns the local synapse registry
- dashboard and showcase packages still own their own state and presentation
  surfaces
- Milestone 17 owns deterministic packaging of larger-brain context around that
  existing substrate

## Simplifications

The v1 contract intentionally stops short of a full interactive app surface.

Current simplifications:

- the package reserves `context_view_payload.json` and `context_query_catalog.json`
  instead of locking one final front-end payload schema too early
- representative node, edge, and downstream-module records are normalized in
  session metadata so tests can exercise the contract semantics without needing
  a heavier graph exporter
- discovery hooks for subset-selection artifacts use stable role ids and
  source-kind semantics even though Milestone 4 never introduced its own
  versioned Python contract module

These simplifications are deliberate. The ticket exists to freeze vocabulary
and boundaries first.

## Testing strategy

The regression coverage for this ticket focuses on contract stability rather
than future UI behavior.

The tests verify:

- deterministic contract serialization even when definitions are supplied in a
  different order and with humanized ids
- stable discovery of query profiles, overlays, and node roles
- normalization of representative session metadata, including artifact
  references, node roles, overlay ids, and downstream-module records

That keeps the tests fast and local while still proving the contract can be
trusted as a canonical Milestone 17 vocabulary layer.

## Future expansion points

Likely follow-on tickets can extend this contract without changing its core
boundary if they:

- populate `context_view_payload.json` with larger query results or view-model
  payloads
- add planners or packaging helpers that materialize whole-brain context
  sessions from shipped subset and coupling artifacts
- add more deterministic discovery hooks if later Milestone 17 work needs
  stronger bridge semantics into dashboard or showcase views
- attach richer downstream-module metadata while preserving the explicit rule
  that module records are summaries, not neuron records

If a follow-on ticket needs a different meaning for active/context boundary
status, pathway highlights, or downstream modules, it should version the
contract instead of silently widening `whole_brain_context_session.v1`.
