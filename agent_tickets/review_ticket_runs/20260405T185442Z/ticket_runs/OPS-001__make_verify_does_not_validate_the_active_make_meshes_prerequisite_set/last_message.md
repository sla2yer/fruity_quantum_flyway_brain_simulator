**Changed**
- [scripts/00_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L100) now treats `make verify` as the authoritative `make meshes` preflight: it shapes `CAVEclient` and `client.info` failures into operator-facing auth/network/config errors, validates the loaded meshing config, fails on `.env` token-sync problems when `FLYWIRE_TOKEN` is set, always checks `fafbseg`, and only requires `navis` when `meshing.fetch_skeletons` is true. The full success path is now `Mesh preflight looks good.` only after those checks pass. An explicit `--auth-only` mode was added for a partial check, and the old materialize probe is now optional.
- [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L15) adds 9 subprocess regression tests covering shaped info-service failures, cloudvolume/token-sync failures, missing `fafbseg`, conditional `navis` requirements, invalid skeleton config, `--auth-only`, and full success.
- [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L54) help text now describes `verify` as the active mesh preflight.

**Verified**
- `./.venv/bin/python -m unittest tests.test_verify_access` passed.
- `make test` passed: 316 tests.
- I also ran stubbed `make verify CONFIG=...` simulations for:
  - token-sync failure with missing `cloudvolume`: non-zero, targeted fix message
  - missing `navis` with `fetch_skeletons: true`: non-zero, targeted fix message
  - missing `navis` with `fetch_skeletons: false`: success
  - forced info-service/datastack failure: non-zero, shaped error without traceback
  - fully provisioned stubbed environment: success

Live FlyWire/CAVE access was not exercised here; the `make verify` acceptance cases were validated with stubbed service/dependency environments.