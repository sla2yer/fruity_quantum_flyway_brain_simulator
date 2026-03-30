**Changed**

Canonical Milestone 15 ablation realizations now live in [experiment_ablation_transforms.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_ablation_transforms.py#L64). The module gives each required family one stable transform identity and deterministic realization path, carries explicit provenance, and keeps ablation perturbation seeds separate from simulator seeds. It covers `no_waves`, `waves_only_selected_cell_classes`, `no_lateral_coupling`, `shuffle_synapse_locations`, `shuffle_morphology`, `coarsen_geometry`, `altered_sign_assumptions`, and `altered_delay_assumptions`, with the first-pass sign/delay modes intentionally bounded and documented.

That realization surface is now threaded through suite planning/execution and simulation/runtime planning: seeded suite cells carry `ablation_realization` in [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1479), materialized configs inject it in [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1067), simulation planning applies it before asset hashing in [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L517), and the runtime layers consume sign/delay and synapse-shuffle perturbations in [surface_wave_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/surface_wave_execution.py#L827) and [hybrid_morphology_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/hybrid_morphology_runtime.py#L2095). I also added the rationale note at [FW-M15-004_rationale.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/experiment_orchestration_notes/FW-M15-004_rationale.md) and focused regression coverage in [test_experiment_ablation_transforms.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_ablation_transforms.py#L84).

**Verified**

Ran focused regression checks for all required families plus failure cases:
- `python3 -m unittest tests.test_experiment_ablation_transforms`
- `python3 -m unittest tests.test_experiment_suite_planning`
- `python3 -m unittest tests.test_experiment_suite_execution`
- `python3 -m unittest tests.test_simulation_planning`

Ran repo verification:
- `make test`

Result: all tests passed, including `make test` with `228` tests passing.