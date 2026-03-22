**Changed**
- Added a new projector layer in [retinal_sampling.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_sampling.py) with:
  - `RetinalProjector` for cached repeated frame generation
  - `AnalyticVisualFieldSource` for fixture scenes
  - direct support for canonical Milestone 8A stimuli via `ResolvedStimulusSpec`, `StimulusRenderResult`, or config-like stimulus mappings
  - deterministic Gaussian acceptance-kernel realization, explicit field-of-view clipping, background fill, and per-eye projection metadata
- Exported the module in [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py).
- Added focused regression coverage in [test_retinal_sampling.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_retinal_sampling.py) for:
  - deterministic repeated sampling on a canonical translated-edge stimulus
  - fixture visual-field projection with partial and full out-of-field behavior

**Verified**
- `./.venv/bin/python -m pytest -q tests/test_retinal_sampling.py`
- `./.venv/bin/python -m pytest -q tests/test_retinal_sampling.py tests/test_retinal_geometry.py tests/test_retinal_contract.py`
- `make test`
  - Result: `84` tests passed

**Git**
- I could not stage or commit because `.git` is read-only in this sandbox. `git add ...` failed with:
  - `fatal: Unable to create '/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/.git/index.lock': Read-only file system`
- When `.git` is writable, the intended commit is:

```bash
git add src/flywire_wave/__init__.py src/flywire_wave/retinal_sampling.py tests/test_retinal_sampling.py \
  src/flywire_wave/config.py src/flywire_wave/manifests.py src/flywire_wave/retinal_contract.py \
  src/flywire_wave/retinal_geometry.py docs/pipeline_notes.md docs/retinal_bundle_design.md \
  tests/test_config_paths.py tests/test_retinal_contract.py tests/test_retinal_geometry.py \
  tests/fixtures/retinal_geometry_cases.yaml tests/fixtures/retinal_geometry_config_fixture.yaml
git commit -m "FW-M8B-003 Implement retinal projection and ommatidial sampling"
```