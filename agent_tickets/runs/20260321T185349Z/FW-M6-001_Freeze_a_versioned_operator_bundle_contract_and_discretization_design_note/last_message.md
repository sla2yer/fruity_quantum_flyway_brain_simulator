Implemented FW-M6-001.

**Changed**
- Centralized the Milestone 6 operator contract in [geometry_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L13). It now defines `operator_bundle.v1`, owns operator-path construction, adds manifest-level `_operator_contract_version`, emits per-root `operator_bundle` metadata, and provides manifest discovery for operator assets.
- Extended the asset build to emit explicit operator artifacts in [mesh_pipeline.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L129) and [mesh_pipeline.py](/home/jack/Documents/github/personal/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L756): `*_transfer_operators.npz` plus `*_operator_metadata.json`. The fine/coarse operator roles deliberately alias the existing `surface_graph` and `patch_graph` archives, so Milestone 5 consumers keep working. The legacy `*_meta.json` shim remains.
- Threaded the operator metadata through the build manifest in [03_build_wave_assets.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L130).
- Added the decisive design note in [operator_bundle_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/operator_bundle_design.md#L1): default is cotangent FEM on the simplified triangle mesh with lumped mass and zero-flux boundaries; fallback is the current uniform surface-graph Laplacian with uniform patch transfers, and the note records the conserved/damped quantities plus stability assumptions.
- Added regression coverage, including the focused fixture-based serialization/discovery test in [test_operator_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_operator_contract.py#L34), plus updates to the existing geometry, mesh-build, and config-path tests.

**Verified**
- Ran `.venv/bin/python -m unittest tests.test_operator_contract -v`
- Ran `.venv/bin/python -m unittest tests.test_mesh_pipeline_build -v`
- Ran `.venv/bin/python -m unittest tests.test_config_paths -v`
- Ran `make test` and it passed: 33 tests, 0 failures

I left unrelated preexisting worktree changes and untracked artifacts outside this ticket untouched.