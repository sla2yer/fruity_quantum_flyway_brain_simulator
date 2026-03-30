**Changes**

- Added the Milestone 15 suite contract in [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py). It freezes canonical dimension IDs, required ablation-family IDs, suite-cell lineage kinds, work-item statuses, reproducibility hooks, artifact-role discovery, and normalized suite metadata/builders for upstream manifests plus downstream simulator, analysis, validation, dashboard, table, plot, and review artifacts.
- Published the design note in [experiment_orchestration_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/experiment_orchestration_design.md), the rationale note in [FW-M15-001_rationale.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/experiment_orchestration_notes/FW-M15-001_rationale.md), and added the Milestone 15 contract section to [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md).
- Added focused regression coverage in [test_experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_contract.py) and exported the new module from [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py).

**Verified**

- Focused Milestone 15 test: `.venv/bin/python -m unittest tests.test_experiment_suite_contract -v`
  Result: 3/3 tests passed.
- Full repo verification: `make test`
  Result: 221 tests passed.