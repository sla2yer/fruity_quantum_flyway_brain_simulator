Work ticket FW-003: Enforce registry membership before building processed wave assets.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: repo review 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`scripts/03_build_wave_assets.py` currently allows selected root IDs that are absent from the neuron registry. The command succeeds and writes assets whose manifest metadata fields are blank, which weakens provenance and breaks the assumption that selected IDs were validated upstream.

Requested Change:
Make the processed-asset builder enforce the same registry-membership contract as the mesh-fetch step. If any selected root ID is missing from the registry, fail early with a precise error message instead of emitting incomplete metadata.

Acceptance Criteria:
- The asset build step errors clearly when any selected root ID is not present in the neuron registry.
- The error reports how many root IDs are missing and includes a small sample.
- Happy-path asset building with fully registered root IDs still works.
- Regression coverage exists for both the failure case and the happy path.

Verification:
- `make test`
- A unit or integration-style test that reproduces the current silent-success case and asserts it now fails
