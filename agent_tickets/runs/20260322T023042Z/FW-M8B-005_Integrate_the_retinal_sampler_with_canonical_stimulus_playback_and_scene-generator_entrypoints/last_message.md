**Changed**
- Added a library-owned retinal integration workflow in [retinal_workflow.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_workflow.py) and a scene entrypoint resolver in [scene_playback.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/scene_playback.py).
- Added the thin CLI entrypoint [12_retinal_bundle.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/12_retinal_bundle.py) for `record` and `replay` from either a canonical stimulus config/manifest path or a scene YAML.
- Extended [retinal_sampling.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_sampling.py) so analytic visual sources can carry stable `source_id` and `source_hash`, which the workflow uses to make retinal bundle paths deterministic and pose-aware.
- Documented the local workflow in [retinal_bundle_workflow.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/retinal_bundle_workflow.md).
- Added regression coverage in [test_retinal_bundle_workflow.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_retinal_bundle_workflow.py) for one stimulus-driven path and one scene-driven path, including deterministic bundle identity, replay behavior, and lineage metadata.

**Verified**
- `make test`
- `.venv/bin/python -m unittest tests.test_retinal_bundle_workflow -v`

Both passed.

**Blocker**
- I could not stage or create the requested commit from this sandbox. `git add` failed because the repo’s `.git` area is read-only here, so no commit was created.