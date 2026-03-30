Implemented FW-M15-005 end-to-end.

Added the suite packaging/index layer in [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py) and integrated it into [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py). Each executed suite now writes a deterministic `package/` directory under the suite root with one metadata anchor, a machine-friendly `result_index.json`, reviewer CSV inventories, and an `inventory.md` report. The result index keeps failed and blocked cells visible, records direct stage status plus simulation-lineage links for base/ablation cells, and exposes discovery helpers for packaged cell records and stage artifacts without filesystem globbing.

Added regression coverage in [test_experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_packaging.py) and the companion rationale in [FW-M15-005_rationale.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/experiment_orchestration_notes/FW-M15-005_rationale.md). The new smoke fixture writes deterministic suite package metadata, indexes successful and incomplete cells, and asserts stable artifact paths and lineage fields.

Verified with:
- `python3 -m unittest tests.test_experiment_suite_packaging`
- `python3 -m unittest tests.test_experiment_suite_execution`
- `python3 -m unittest tests.test_experiment_suite_contract tests.test_experiment_suite_planning`
- `make test` (`229` tests, `OK`)

I left unrelated existing worktree changes untouched.