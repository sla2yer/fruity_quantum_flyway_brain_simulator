**Changed**

Added focused package-path regression coverage in [tests/test_validation_ladder_package.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_ladder_package.py). The new tests build tiny contract-valid local layer bundles and directly cover:
- shuffled package inputs normalizing to the same `bundle_id`, identical summary bytes, and canonical layer ordering
- duplicate `layer_id` bundle rejection
- missing required ladder layer rejection
- `scripts/27_validation_ladder.py package --write-baseline` writing the normalized regression snapshot derived from the packaged summary

Also adjusted [scripts/27_validation_ladder.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/27_validation_ladder.py) so the `package` subcommand no longer imports the smoke workflow eagerly. That makes the standalone package path runnable without pulling in smoke-only dependencies first.

**Verified**

Ran:
- `python3 -m unittest tests.test_validation_ladder_package -v`
- `make test`

Result: both passed. `make test` completed with `Ran 341 tests in 413.007s` and `OK`.