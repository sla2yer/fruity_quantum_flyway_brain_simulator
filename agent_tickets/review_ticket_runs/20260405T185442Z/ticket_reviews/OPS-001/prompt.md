Review work ticket OPS-001: `make verify` is not a reliable gate for `make meshes`.
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
## OPS-001 - `make verify` is not a reliable gate for `make meshes`
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: `scripts/00_verify_access.py` / auth preflight

### Problem
`make verify` is documented as the operator preflight before the FlyWire-backed pipeline, but the script is not authoritative for the next step it is supposed to protect. It can still dump an uncaught info-service exception after client construction, and it also downgrades `fafbseg` or local-secret-sync failures to warnings while still returning success. That lets operators burn time on `make meshes` after a misleading green verify.

### Evidence
- [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59) tells operators to run `make verify` before preprocessing.
- [scripts/00_verify_access.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L118) and [scripts/00_verify_access.py:119](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L119) call the info service outside the request error-shaping used for client creation and materialize retries.
- [scripts/00_verify_access.py:166](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L166) starts the `fafbseg`/secret-sync check, [scripts/00_verify_access.py:180](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L180) catches every exception, and [scripts/00_verify_access.py:183](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L183) still prints success text and returns `0`.
- [scripts/02_fetch_meshes.py:83](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L83) and [scripts/02_fetch_meshes.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L118) depend on the same `ensure_flywire_secret` / `fafbseg` path that verify can currently waive.

### Requested Change
Make `verify` fail by default when mesh-fetch prerequisites are not usable, and shape every subcheck into explicit operator-facing statuses. If partial verification is still desired, require an explicit opt-in flag and label the result as partial rather than printing “Access looks good.”

### Acceptance Criteria
`make verify` exits non-zero when FlyWire mesh prerequisites are broken, including missing `fafbseg`, broken secret sync, or post-client info-service failures.
The script prints one actionable failure summary per failing subsystem, including the package/env fix or network/auth next step.
The success path is only emitted when the prerequisites needed by `make meshes` have actually been validated, or when the operator explicitly asked for a partial check.

### Verification
Run `make verify CONFIG=config/local.yaml` in an environment with working CAVE access but without `fafbseg` or working secret storage; it should exit non-zero with a targeted fix message.
Run `make verify CONFIG=config/local.yaml` with an invalid datastack or forced info-service failure; it should return a shaped error, not a traceback.
Run `make verify CONFIG=config/local.yaml` in a fully provisioned environment; it should still exit `0`.
