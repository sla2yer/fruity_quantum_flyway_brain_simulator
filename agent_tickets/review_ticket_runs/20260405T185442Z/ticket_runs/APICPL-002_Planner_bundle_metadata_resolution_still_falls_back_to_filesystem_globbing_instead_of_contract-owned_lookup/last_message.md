Implemented APICPL-002 end-to-end.

The main changes are in [experiment_comparison_analysis.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py), [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py), [experiment_analysis_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_analysis_contract.py), [validation_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_contract.py), and [simulator_result_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_result_contract.py). `discover_experiment_bundle_set()` no longer scans arm directories for `*/simulator_result_bundle.json`; it resolves expected per-run/per-condition metadata paths from contract identities, with a contract-layer compatibility lookup that preserves the existing relaxed asset-path behavior and deduplicates stray copied metadata. Dashboard planning no longer owns raw `glob("*/experiment_analysis_bundle.json")` or `glob("*/validation_bundle.json")` policy; it now goes through shared contract lookup helpers, using exact analysis/validation plan identities when available and shared lookup filters when only upstream bundle references are available.

I added regressions in [tests/test_experiment_comparison_analysis.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py) and [tests/test_dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py) to prove stale copied bundle metadata under `bundles/`, `analysis/`, and `validation/` does not change selection.

Verified:
- `python3 -m unittest tests.test_experiment_comparison_analysis -v` OK
- `python3 -m unittest tests.test_validation_planning -v` OK
- `python3 -m unittest tests.test_dashboard_session_planning -v` initially failed on this machine because system `python3` lacked `trimesh`
- `.venv/bin/python -m unittest tests.test_dashboard_session_planning -v` OK
- `PYTHONPATH=.venv/lib/python3.12/site-packages python3 -m unittest tests.test_dashboard_session_planning -v` OK

Also confirmed the high-level planner files no longer contain raw `glob(...)` calls for those three bundle metadata patterns.