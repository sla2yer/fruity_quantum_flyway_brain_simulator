Review work ticket TESTGAP-004: `make verify` has no stubbed regression coverage for auth, outage, or version handling.
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
## TESTGAP-004 - `make verify` has no stubbed regression coverage for auth, outage, or version handling
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: preprocessing readiness

### Problem
`make all` starts with `make verify`, and `scripts/00_verify_access.py` contains nontrivial classification logic for auth failures, transient materialize outages, `--require-materialize`, missing materialization version `783`, and fafbseg token syncing. None of that is protected by a local deterministic test. A regression could misclassify token failure as a temporary outage or allow the wrong materialization version through without `make test`, `make smoke`, or any readiness command noticing.

### Evidence
- The setup docs make `make verify` part of the normal access check and `make all` entry sequence in [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59) and [README.md:88](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L88).
- The verify script contains retry and exit-code logic for auth, transient HTTP/network errors, and materialization visibility in [scripts/00_verify_access.py:36](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L36), [scripts/00_verify_access.py:102](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L102), and [scripts/00_verify_access.py:127](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L127).
- Secret-sync behavior is implemented separately in [src/flywire_wave/auth.py:9](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L9).
- No test file references `scripts/00_verify_access.py` or `ensure_flywire_secret`.

### Requested Change
Add a fully local test module, preferably [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py), that stubs `caveclient`, `requests`, `fafbseg`, and `cloudvolume` and executes `scripts/00_verify_access.py` or `main()` directly. Cover at least: 401 auth failure, transient materialize outage with and without `--require-materialize`, requested materialization version not visible, and successful token-sync plus dataset selection.

### Acceptance Criteria
- Auth failure returns exit code `1` with the auth-specific guidance text.
- Transient materialize unavailability returns `0` by default and `2` with `--require-materialize`.
- Invisible materialization version returns `1` and names the requested version.
- Success path prints the configured datastack, materialization version, and fafbseg token-sync outcome.
- All of the above run without live FlyWire access.

### Verification
- `python -m unittest tests.test_verify_access -v`
- `make test`
