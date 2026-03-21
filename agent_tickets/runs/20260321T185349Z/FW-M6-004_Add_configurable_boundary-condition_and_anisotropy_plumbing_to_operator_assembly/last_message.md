Implemented FW-M6-004 end to end.

The main changes are in [surface_operators.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/surface_operators.py), [geometry_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py), [mesh_pipeline.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py), and [03_build_wave_assets.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py). The operator path now accepts a versioned `meshing.operator_assembly` config, the bundle contract is bumped to `operator_bundle.v2`, and fine-operator metadata/archive data explicitly record boundary mode, anisotropy model, and the serialized coefficients needed to reproduce assembly. Default behavior remains `closed_surface_zero_flux` plus isotropic assembly.

Supported new semantics are:
- boundary modes: `closed_surface_zero_flux` and `boundary_vertices_clamped_zero`
- anisotropy models: `isotropic` and narrow `local_tangent_diagonal`
- serialized anisotropy data in the fine archive: per-vertex diagonal tensors, edge tangent directions, edge multipliers, and effective cotangent weights

Docs and examples were updated in [operator_bundle_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/operator_bundle_design.md), [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md), and [visual_subset.example.yaml](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/config/visual_subset.example.yaml). Regression coverage was added in [test_operator_assembly_modes.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_operator_assembly_modes.py), and the existing contract/pipeline tests were updated to assert the new payload and metadata fields.

Verified:
- `.venv/bin/python -m pytest tests/test_operator_assembly_modes.py`
- `make test`

Results:
- targeted operator assembly module: 2 passed
- full repo test suite: 39 passed

Note: the existing generated run log at `agent_tickets/runs/20260321T185349Z/.../stdout.jsonl` was also touched during execution.