# FW-M14-008 Rationale

## Design Choices

The Milestone 14 readiness pass is implemented as one repo-owned command,
`make milestone14-readiness`, backed by
`scripts/30_milestone14_readiness.py` and
`flywire_wave.milestone14_readiness`.

The pass deliberately audits the shipped command surface instead of only calling
library helpers. It runs:

- the focused dashboard unit suite
- `scripts/29_dashboard_shell.py build` through both manifest-driven and
  experiment-driven entrypoints
- `scripts/29_dashboard_shell.py open --no-browser` for deterministic packaged
  app-shell discovery
- `scripts/29_dashboard_shell.py export` for snapshot, metrics, and replay
  frame-sequence outputs

That keeps the readiness report aligned with what a reviewer or downstream
milestone will actually invoke from the repo.

## Testing Strategy

The readiness report combines three verification layers:

1. Focused regression tests for contract, planning, shell, pane, replay, and
   export logic.
2. A deterministic generated fixture that packages one complete local dashboard
   session under the readiness report directory.
3. A CLI-level audit that compares manifest-driven versus experiment-driven
   session resolution, reloads the packaged session through the public `open`
   path, and checks deterministic export outputs.

This ticket also closes a defect discovered during the audit: equivalent
manifest- and experiment-driven builds were landing in the same session bundle
directory while writing different payload bytes because `source_mode` leaked
into the packaged session payload and app bootstrap. That field now stays in the
in-memory planning result instead of mutating packaged session artifacts.

## Simplifications

The readiness fixture reuses the repo-owned dashboard fixture builder that was
already powering the Milestone 14 regression tests. That keeps the verification
surface deterministic and avoids creating a second slightly-different fixture
pipeline just for the readiness command.

The new `--no-browser` option on `scripts/29_dashboard_shell.py open` is also a
deliberate simplification. It gives the readiness pass and future CI-style
checks a stable way to verify packaged app-shell discovery without requiring a
GUI browser launch.

## Future Expansion Points

- Add a browser-engine smoke that drives the packaged dashboard controls through
  a real DOM runtime.
- Add a richer retinal-backed or larger-circuit stress fixture for Milestone 16
  showcase validation without slowing down the default readiness gate.
- Expand the readiness audit if later milestones add new pane-level contracts or
  export targets beyond the current snapshot, metrics, and replay surfaces.
