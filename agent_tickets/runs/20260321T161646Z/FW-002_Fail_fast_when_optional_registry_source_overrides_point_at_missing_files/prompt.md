Work ticket FW-002: Fail fast when optional registry source overrides point at missing files.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: repo review 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
If a user explicitly sets an override such as `paths.connections_csv` and the file does not exist, the registry builder silently treats the source as absent and continues. That can quietly produce an incomplete registry and empty connectivity outputs even though the config was clearly asking for that input.

Requested Change:
Update registry source resolution so explicit override paths are validated strictly. If the user provided an override and the file is missing, raise a clear configuration error instead of silently downgrading to a missing optional source. Keep auto-discovery behavior for genuinely optional, non-overridden inputs.

Acceptance Criteria:
- Explicit override paths for optional inputs fail with a clear error when the target file is missing.
- Auto-discovery still works for optional sources when no override is provided.
- Regression coverage exercises both the failing override case and the still-valid auto-discovery case.
- Error text names the config key and the missing file path.

Verification:
- `make test`
- A focused unit test for optional override validation in registry source resolution
