Work ticket TESTGAP-002: `validation-ladder package` edge cases and baseline writing still lack direct coverage.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: testing_and_verification_gaps review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repository now exercises packaged-ladder success behavior through the deterministic smoke fixture, but it still does not directly test the standalone `package` path or its package-specific failure modes. Current coverage does not prove that shuffled input order is normalized, that duplicate layer bundles are rejected, that missing required layers fail clearly, or that `scripts/27_validation_ladder.py package --write-baseline` writes the expected normalized regression snapshot.

Requested Change:
Add focused direct regression coverage for `package_validation_ladder_outputs()` and `scripts/27_validation_ladder.py package`, using tiny local layer bundles. Keep the scope limited to the currently untested package-path behaviors rather than duplicating the existing smoke happy path.

Acceptance Criteria:
- Packaging the same layer bundles in different input orders yields the same `bundle_id`, identical summary bytes, and normalized layer ordering.
- Supplying two bundles for the same `layer_id` fails clearly.
- Requiring the full ladder layer set and omitting one layer fails clearly.
- Running `scripts/27_validation_ladder.py package ... --write-baseline ...` writes the normalized regression baseline derived from the packaged summary.

Verification:
- `python -m unittest tests.test_validation_reporting -v` or `python -m unittest tests.test_validation_ladder_package -v`
- `make test`
