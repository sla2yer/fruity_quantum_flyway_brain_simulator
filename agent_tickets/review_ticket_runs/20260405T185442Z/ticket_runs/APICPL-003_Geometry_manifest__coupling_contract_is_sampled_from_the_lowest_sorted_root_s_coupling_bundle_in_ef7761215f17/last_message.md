Implemented APICPL-003 by moving `_coupling_contract` ownership to the manifest builder instead of sampling a single root bundle. In [geometry_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L725), the header is now built from manifest-level inputs: explicit `processed_coupling_dir` wins, and if it is omitted the coupling dir is inferred from geometry record paths, not from `coupling_bundle.assets.local_synapse_registry`. The manifest writer now checks every root’s `coupling_bundle.assets.local_synapse_registry` path and status against the manifest-wide contract and raises a clear `ValueError` on any mismatch instead of serializing the lowest root’s bundle into the header.

In [coupling_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L206), `build_coupling_contract_manifest_metadata()` now only accepts explicit manifest-owned inputs (`processed_coupling_dir` and `local_synapse_registry_status`) and no longer reconstructs the global registry path/status from a sampled per-root bundle. I added regressions in [test_coupling_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_coupling_contract.py#L219) for explicit-dir precedence with a stale lower-root bundle and for multi-root status conflicts.

Verified:
- `python3 -m unittest tests.test_geometry_contract -v`
- `python3 -m unittest tests.test_coupling_contract -v`
- `python3 -m unittest tests.test_simulation_planning -v`

All passed.