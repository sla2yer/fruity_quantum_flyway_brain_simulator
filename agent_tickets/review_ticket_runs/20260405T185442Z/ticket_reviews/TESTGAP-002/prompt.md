Review work ticket TESTGAP-002: `validation-ladder-package` is only covered indirectly through the smoke fixture.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

This is a ticket review pass only. Do not implement code.
Earlier backlog tickets may already have changed the surrounding code.
Check whether this ticket is still accurate for the repository's current state and update it if needed.

Rules:
- Keep the same ticket ID.
- Return exactly one ticket in the same markdown ticket format.
- Update the title, priority, area, and sections if the ticket needs refinement.
- If the ticket no longer needs implementation, set `- Status: closed` and explain why.
- Do not create new tickets or broaden this ticket into a larger backlog item.
- Return only the updated single-ticket markdown and do not use code fences.

Existing Ticket:
## TESTGAP-002 - `validation-ladder-package` is only covered indirectly through the smoke fixture
- Status: open
- Priority: high
- Source: testing_and_verification_gaps review
- Area: validation ladder packaging

### Problem
The repo documents `scripts/27_validation_ladder.py package` and `make validation-ladder-package` as the path for packaging existing per-layer `validation_bundle.json` artifacts. Current verification only covers the synthetic smoke workflow, not the package path that real numerical, morphology, circuit, and task runs hand off into. A regression in duplicate-layer rejection, required-layer enforcement, input-order normalization, or baseline writing could break real ladder packaging while `make validation-ladder-smoke` and `make milestone13-readiness` still pass.

### Evidence
- The documented package workflow is in [docs/pipeline_notes.md:576](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L576) and the Make target is in [Makefile:186](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L186).
- The package implementation has explicit checks for required layers and duplicate layer IDs in [src/flywire_wave/validation_reporting.py:558](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L558) and [src/flywire_wave/validation_reporting.py:681](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L681).
- Current test coverage only runs the smoke fixture in [tests/test_validation_reporting.py:24](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_reporting.py#L24).
- Milestone 13 readiness also shells only the `smoke` subcommand in [src/flywire_wave/milestone13_readiness.py:487](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L487).

### Requested Change
Add a deterministic packaging test module, preferably [tests/test_validation_ladder_package.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_ladder_package.py), that materializes tiny local layer bundles and directly exercises `package_validation_ladder_outputs()` plus `scripts/27_validation_ladder.py package`. Include one shuffled-order success case, one duplicate-layer failure case, one missing-required-layer failure case, and one `--write-baseline` assertion.

### Acceptance Criteria
- Packaging the same layer bundles in different input orders yields the same `bundle_id`, summary bytes, and layer ordering.
- Supplying two bundles for the same `layer_id` fails clearly.
- Requiring all four ladder layers and omitting one fails clearly.
- `--write-baseline` writes a normalized regression baseline from the packaged summary.

### Verification
- `python -m unittest tests.test_validation_ladder_package -v`
- `make test`
