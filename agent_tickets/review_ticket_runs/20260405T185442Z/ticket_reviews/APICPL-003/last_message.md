## APICPL-003 - Geometry manifest `_coupling_contract` is sampled from the lowest sorted root's `coupling_bundle` instead of manifest inputs
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: geometry manifest / coupling contract

### Problem
The manifest-level coupling header is no longer sensitive to dict insertion order, because roots are sorted numerically before sampling. But it is still synthesized from exactly one per-root `coupling_bundle`: the lowest root ID that has one. That makes the global contract depend on sampled per-root metadata instead of explicit manifest-owned inputs. Because the header builder reconstructs `processed_coupling_dir` from that sampled bundle's `local_synapse_registry.path`, stale or mixed per-root coupling metadata can silently override the caller-provided coupling directory and rewrite the manifest-wide registry path/status that simulation planning treats as authoritative.

### Evidence
- [src/flywire_wave/geometry_contract.py#L732](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L732) seeds `_coupling_contract` from `_first_coupling_bundle_metadata`, and [src/flywire_wave/geometry_contract.py#L855](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L855) selects the first `coupling_bundle` after sorting root IDs numerically.
- [src/flywire_wave/coupling_contract.py#L213](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L213) parses the sampled bundle, [src/flywire_wave/coupling_contract.py#L216](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L216) rebuilds the manifest header directory from that bundle's `local_synapse_registry.path`, and [src/flywire_wave/coupling_contract.py#L300](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L300) shows that each per-root bundle carries its own `local_synapse_registry` path/status.
- [src/flywire_wave/simulation_planning.py#L2983](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2983) loads `_coupling_contract`, [src/flywire_wave/simulation_planning.py#L2993](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2993) resolves `_coupling_contract.local_synapse_registry.path`, and [src/flywire_wave/simulation_planning.py#L3003](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3003) gates planning on that header status rather than a cross-root consistency check.
- [tests/test_geometry_contract.py#L119](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_contract.py#L119) and [tests/test_coupling_contract.py#L130](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_coupling_contract.py#L130) cover single-root happy paths only; there is no regression that exercises conflicting per-root coupling metadata or verifies that explicit `processed_coupling_dir` wins.

### Requested Change
Make `_coupling_contract` a manifest-owned record derived from explicit manifest inputs. The manifest writer should not infer the global `local_synapse_registry` location/status from a sampled root bundle, and an explicit `processed_coupling_dir` must not be overridden by per-root metadata. If per-root `coupling_bundle.assets.local_synapse_registry` entries disagree with the manifest-wide coupling location or readiness status, fail manifest construction with a clear error instead of serializing the lowest root's bundle into the header.

### Acceptance Criteria
- `_coupling_contract.local_synapse_registry.path` is derived from explicit manifest input when `processed_coupling_dir` is supplied, even if per-root `coupling_bundle_metadata` is present.
- Adding or removing a lower-root record with stale `coupling_bundle.assets.local_synapse_registry` metadata does not rewrite the manifest-wide coupling header.
- Conflicting per-root `local_synapse_registry` path or status values cause geometry manifest writing to fail clearly.
- Regression coverage includes a multi-root manifest with conflicting bundle metadata and a case where sampled bundle metadata disagrees with the explicit `processed_coupling_dir`.

### Verification
`python3 -m unittest tests.test_geometry_contract -v`; `python3 -m unittest tests.test_coupling_contract -v`; `python3 -m unittest tests.test_simulation_planning -v`