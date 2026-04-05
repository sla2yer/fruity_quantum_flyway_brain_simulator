Review work ticket APICPL-003: Geometry manifest `_coupling_contract` header is derived from whichever root record sorts first.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

This is a ticket review pass only. Do not implement code.
Earlier backlog tickets may already have changed the surrounding code.
Check whether this ticket is still accurate for the repository's current state and update it if needed.

Rules:
- Keep the same ticket ID.
- Return exactly one ticket in the same markdown ticket format.
- Update the title, priority, area, and sections if the ticket needs refinement.
- If the ticket no longer needs implementation, set `- Status: closed` and explain why.
- Do not create new tickets or broaden this ticket into a larger backlog item.
- Return only the updated single-ticket markdown and do not use code fences.

Existing Ticket:
## APICPL-003 - Geometry manifest `_coupling_contract` header is derived from whichever root record sorts first
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: geometry / coupling manifest contract

### Problem
The manifest-level coupling header is treated as the authoritative global seam for `synapse_registry.csv`, but it is currently synthesized from one per-root `coupling_bundle`. That makes a global contract depend on record order and allows stale or mixed per-root coupling metadata to silently rewrite the header that simulation planning trusts.

### Evidence
- `[src/flywire_wave/geometry_contract.py#L732](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L732)` seeds `_coupling_contract` from `_first_coupling_bundle_metadata`, and `[src/flywire_wave/geometry_contract.py#L852](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L852)` returns the first root’s `coupling_bundle`.
- `[src/flywire_wave/coupling_contract.py#L213](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L213)` then overrides the caller-provided `processed_coupling_dir` with the path embedded in that sampled bundle metadata.
- `[src/flywire_wave/simulation_planning.py#L2978](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2978)` through `[src/flywire_wave/simulation_planning.py#L3003](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3003)` consume `_coupling_contract.local_synapse_registry` as the authoritative plan input.

### Requested Change
Make manifest-level coupling metadata a canonical manifest-owned record built from explicit manifest inputs, not from a sampled root bundle. If per-root coupling bundles disagree about the shared coupling registry location or status, manifest writing should fail instead of serializing whichever root happens to come first.

### Acceptance Criteria
`_coupling_contract.local_synapse_registry` is stable under root reordering, and inconsistent per-root coupling metadata cannot produce a misleading manifest header.

### Verification
`python3 -m unittest tests.test_coupling_contract -v`; `python3 -m unittest tests.test_simulation_planning -v`; add regressions that swap record order and that inject conflicting per-root coupling metadata.
