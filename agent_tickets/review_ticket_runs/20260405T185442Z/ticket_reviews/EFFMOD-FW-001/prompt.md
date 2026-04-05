Review work ticket EFFMOD-FW-001: Stop rereading the raw synapse snapshot during registry and subset materialization.
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
## EFFMOD-FW-001 - Stop rereading the raw synapse snapshot during registry and subset materialization
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: registry

### Problem
The normal `make registry -> make select` flow reparses the raw synapse snapshot multiple times even though the code already has a normalized synapse table in memory or on disk. That is the largest CSV in this pipeline, so repeated `pandas` loads and normalization passes directly increase local preprocessing cost. The current API shape also makes reuse hard because `materialize_synapse_registry()` only accepts config and always reloads the raw source.

### Evidence
- [registry.py:360](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L360) loads `synapse_df = _load_synapse_table(source_paths.synapses)` and then still calls `materialize_synapse_registry(...)` at [registry.py:410](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L410).
- [registry.py:307](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L307) shows `materialize_synapse_registry()` immediately calling `_load_synapse_table(...)` again at [registry.py:319](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L319).
- [registry.py:582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L582) shows `_load_synapse_table()` doing a full `pd.read_csv(path)` plus schema normalization.
- [selection.py:279](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L279) calls `materialize_synapse_registry()` again for the active preset, so `make select` can trigger another full raw-snapshot read just to refresh the subset-scoped registry.

### Requested Change
Split synapse-registry loading from synapse-registry scoping/writing. `build_registry()` should be able to pass the already-normalized synapse table into the materialization path, and active subset refresh should filter either that canonical table or the already-written canonical registry instead of rereading the raw snapshot.

### Acceptance Criteria
- `build_registry()` reads and normalizes the raw synapse snapshot at most once per invocation.
- Active-preset subset refresh can rewrite the scoped synapse registry without forcing another raw CSV parse when the canonical local registry already exists.
- Provenance and scope metadata stay unchanged.

### Verification
- `make test`
- `.venv/bin/python -m unittest tests.test_registry tests.test_selection -v`
