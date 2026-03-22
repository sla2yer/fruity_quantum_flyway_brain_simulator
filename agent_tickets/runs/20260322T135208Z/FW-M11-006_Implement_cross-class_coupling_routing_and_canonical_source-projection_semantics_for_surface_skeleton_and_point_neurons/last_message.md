Implemented FW-M11-006 in [src/flywire_wave/hybrid_morphology_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/hybrid_morphology_runtime.py). The mixed-morphology runtime now resolves selected edge bundles into explicit executable routing components across `surface_neuron`, `skeleton_neuron`, and `point_neuron`, applies source projection and target injection on the realized local representation, preserves bundle sign/delay/aggregation semantics, and records route metadata per component family and per executed event. Unsupported anchor/class combinations now fail clearly during route resolution instead of being deferred or silently ignored.

I also updated the existing hybrid runtime regression in [tests/test_hybrid_morphology_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_hybrid_morphology_runtime.py) and added a focused routing module at [tests/test_mixed_coupling_routing.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_mixed_coupling_routing.py). The new tests cover deterministic `surface->skeleton`, `skeleton->point`, and `point->surface` execution plus a clear unsupported-route failure case.

Verified with:
- `./.venv/bin/python -m unittest tests.test_mixed_coupling_routing -v`
- `make test`

`make test` passed: 144 tests, 0 failures. The suite emitted the existing optional Codex DB warning for data version `783`, but completed successfully.