Work ticket OPS-002: Core CLI entrypoints still raise raw startup `ModuleNotFoundError` instead of bootstrap guidance.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: error_handling_and_operability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo now has partial dependency shaping inside `verify`, but the core preflight and pipeline scripts still import declared packages before any operator-facing error handling runs. When the active interpreter has not been bootstrapped into the repo environment, operators still get raw `ModuleNotFoundError` tracebacks instead of a concise message naming the missing package and pointing back to `make bootstrap`. Because the Makefile prefers `.venv/bin/python` when it exists, this is now mainly a first-run or bypassed-interpreter failure mode, but it still affects the documented recovery path.

Requested Change:
Add a shared startup dependency guard for the core operator entrypoints so missing declared packages are caught before module-level imports explode. At minimum, `verify`, `select`, `meshes`, and `assets` should fail with one concise operator-facing message that names the missing package and points to `make bootstrap`, regardless of whether the missing dependency is `python-dotenv`, `networkx`, `tqdm`, or `trimesh`.

Acceptance Criteria:
`make verify`, `make select`, `make meshes`, and `make assets` fail with concise operator messages when the active interpreter is missing required Python packages.

Those ordinary missing-package cases exit nonzero without emitting a Python traceback.

The shaped message names the missing package and points operators to `make bootstrap` or the equivalent install command.

At least one automated test covers the startup missing-import path for `verify`, and at least one automated test covers the same behavior for a pipeline command such as `select`, `meshes`, or `assets`.

Verification:
In an interpreter without `python-dotenv`, run `PYTHON=python3 make verify CONFIG=config/local.yaml` or `python3 scripts/00_verify_access.py --config config/local.yaml`; the command should fail without a traceback and should point to `make bootstrap`.

In an interpreter without `networkx`, run `PYTHON=python3 make select CONFIG=config/local.yaml`; the command should fail with an actionable dependency message instead of a raw import traceback.

In an interpreter without `python-dotenv`, `tqdm`, or `trimesh`, run `PYTHON=python3 make meshes CONFIG=config/local.yaml` and `PYTHON=python3 make assets CONFIG=config/local.yaml`; both commands should fail without a traceback and should point to `make bootstrap`.

Re-run `./.venv/bin/python -m unittest tests.test_verify_access -v` together with the new missing-dependency startup tests and confirm the shaped error path is covered.
