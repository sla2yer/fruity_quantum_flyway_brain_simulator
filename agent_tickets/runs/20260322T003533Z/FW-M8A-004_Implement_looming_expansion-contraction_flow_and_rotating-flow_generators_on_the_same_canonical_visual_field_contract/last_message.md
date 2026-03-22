Implemented the Milestone 8A motion families on the existing canonical visual-field contract. The main changes are in [stimulus_registry.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_registry.py#L566), [stimulus_generators.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_generators.py#L211), [stimulus_generators.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_generators.py#L673), [stimulus_generator_cases.yaml](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/fixtures/stimulus_generator_cases.yaml#L179), and [test_stimulus_motion_generators.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_stimulus_motion_generators.py#L18).

What changed:
- Added canonical looming, radial-flow, and rotating-flow renderers using the same centered degree-frame and sample-hold timing rules as the earlier families.
- Extended the registry for radial and rotating flow with explicit carrier parameters so replay is auditable: radial spatial frequency, angular cycle count, phase, waveform, motion sign/direction, and annulus bounds.
- Recorded family metadata for motion center, velocity units, growth schedule, sign/direction, and mask handling.
- Added deterministic fixture cases plus focused tests for looming growth, radial outward/inward replay, clockwise/counterclockwise replay, shifted motion centers, and deterministic samples.

Verified:
- `./.venv/bin/python -m unittest tests.test_stimulus_generators tests.test_stimulus_motion_generators -v`
- `make test`
- Result: all passed, including the full suite (`71` tests).

I could not complete the requested `git add`/commit step here because this sandbox blocks writes to the repo Git index. The failure was:
- `fatal: Unable to create '/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/.git/index.lock': Read-only file system`

If you want to finish that last step outside the sandbox, run:
```bash
git add src/flywire_wave/stimulus_generators.py \
        src/flywire_wave/stimulus_registry.py \
        tests/fixtures/stimulus_generator_cases.yaml \
        tests/test_stimulus_motion_generators.py
git commit -m "FW-M8A-004 implement looming and flow generators"
```