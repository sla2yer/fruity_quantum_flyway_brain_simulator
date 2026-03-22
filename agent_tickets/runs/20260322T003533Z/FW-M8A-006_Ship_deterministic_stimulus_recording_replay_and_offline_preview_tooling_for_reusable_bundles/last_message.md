**Changed**
- [stimulus_bundle.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_bundle.py) now owns deterministic stimulus recording and replay: it resolves canonical specs, writes a deterministic `stimulus_frames.npz`, loads/replays bundles offline from `stimulus_bundle.json`, and generates a static preview report under `<bundle>/preview/` with `index.html`, `summary.json`, and deterministic SVG frame images.
- [10_stimulus_bundle.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/10_stimulus_bundle.py) adds the thin CLI. `record` accepts `--config` or `--manifest`; `replay` accepts `--config`, `--manifest`, or `--bundle-metadata`.
- Stimulus config/manifest integration and coverage were wired through [config.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/config.py), [manifests.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/manifests.py), [milestone_1_experiment_manifest.schema.json](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/schemas/milestone_1_experiment_manifest.schema.json), [stimulus_bundle_workflow.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/stimulus_bundle_workflow.md), and the stimulus tests/fixtures including [test_stimulus_bundle_workflow.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_stimulus_bundle_workflow.py).

**Verified**
- `make test`
- `.venv/bin/python -m unittest tests.test_stimulus_bundle_workflow -v`

Both passed. The new smoke test records the same fixture stimulus twice, checks deterministic metadata/cache/preview paths and contents, then replays it offline and asserts sample-hold frame resolution.

**Commit**
- I could not stage or create the requested commit in this session because git metadata is read-only here. `git add` fails creating `.git/index.lock`, and alternate-index attempts also fail when git tries to write temporary object files into the repo database.