Work ticket OPS-001: `make verify` does not validate the active `make meshes` prerequisite set.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: error_handling_and_operability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`make verify` is still the documented preflight before `make meshes`, but it is not authoritative for the mesh step the repo actually runs today. The verifier can still throw an uncaught exception after CAVE client construction during the `client.info` lookup, it still downgrades `.env` token-sync failures to warnings, and it never checks the `navis` dependency that the default `meshing.fetch_skeletons: true` path requires. An operator can therefore see `Access looks good.` and then fail immediately in `make meshes` on missing `cloudvolume`, `fafbseg`, `navis`, or an unshaped info-service error.

Requested Change:
Make `verify` authoritative for the active `make meshes` preflight instead of a looser CAVE/materialize probe. It should shape post-client `client.info` failures into explicit operator-facing errors, consult the current meshing config, and fail by default whenever the next `make meshes` step would immediately fail on missing auth/dependency setup. That includes the `.env` token-sync path from [src/flywire_wave/auth.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py) and `navis` when `meshing.fetch_skeletons` is enabled. If a lighter auth-only check is still wanted, require an explicit opt-in flag and label the result as partial/auth-only instead of printing `Access looks good.`

Acceptance Criteria:
- `make verify` exits non-zero for post-client info-service failures and prints a shaped auth/network/config error instead of a traceback.
- When `FLYWIRE_TOKEN` is provided, `make verify` exits non-zero if the token-sync path is unusable, including missing `cloudvolume`, missing `fafbseg`, or other secret-sync failures.
- When `meshing.fetch_skeletons` is `true`, `make verify` exits non-zero if `navis` is unavailable; when `meshing.fetch_skeletons` is `false`, `navis` is not treated as required.
- The full success path is only emitted after the same immediate dependency/auth setup that `make meshes` needs has been validated, or when the operator explicitly requested a partial/auth-only check.
- Each failing subcheck prints one actionable next step, such as install/bootstrap guidance for missing packages or token/network/config guidance for FlyWire access failures.

Verification:
- Run `make verify CONFIG=config/local.yaml` in an environment with working CAVE access and `FLYWIRE_TOKEN` set, but without `fafbseg` or with broken `cloudvolume` secret handling; it should exit non-zero with a targeted fix message.
- Run `make verify CONFIG=config/local.yaml` in an environment where the default `meshing.fetch_skeletons: true` config is active but `navis` is missing; it should exit non-zero before `make meshes` would fail.
- Run `make verify CONFIG=config/local.yaml` with an invalid datastack or forced info-service failure; it should return a shaped error, not a traceback.
- Run `make verify` against a config copy with `meshing.fetch_skeletons: false` in the same missing-`navis` environment; it should still succeed if the remaining mesh prerequisites are valid.
- Run `make verify CONFIG=config/local.yaml` in a fully provisioned environment; it should exit `0`.
