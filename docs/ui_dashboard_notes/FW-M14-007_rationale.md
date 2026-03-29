# FW-M14-007 Rationale

## Design Choices

This ticket adds one library-owned analysis normalization layer and one
library-owned export layer instead of asking the browser shell to infer meaning
from raw bundle directories.

`flywire_wave.dashboard_analysis` now builds a contract-backed analysis pane
context from packaged Milestone 12 and Milestone 13 outputs, including:

- task-summary cards and comparison cards
- matrix-like comparison views
- phase-map references
- ablation summaries when packaged groups advertise ablation content
- validation summaries and reviewer findings

That keeps the dashboard aligned with the existing packaging work. The pane
consumes packaged JSON referenced by the active dashboard session and does not
reparse simulator result directories from JavaScript.

The pane is intentionally split into visibly separate bands:

- `shared_comparison` content for fair experiment-versus-experiment comparison
- `wave_only_diagnostic` content for wave-specific interpretation
- `validation_evidence` content for reviewer-oriented findings and status
- `unavailable` or `inapplicable` overlay states when the requested overlay
  does not belong to the current pane or was not packaged

`flywire_wave.dashboard_exports` provides the first canonical export path for
the dashboard. Exports are deterministic because they are written under a
session-relative hashed directory:

- `exports/<pane-or-session>/<export-target-id>/<export-spec-hash>/`

The export hash is derived from the packaged bundle identity plus the normalized
dashboard interaction state. Re-running the same export request produces the
same output path and metadata record.

The first replay-oriented export stays honest: this ticket writes a
deterministic frame sequence plus a manifest instead of pretending to ship a
fully encoded video container. That keeps the export path reproducible and easy
to validate in local tests.

Local export commands are now explicit:

- `make dashboard-export DASHBOARD_SESSION_METADATA=/abs/path/dashboard_session_metadata.json DASHBOARD_EXPORT_ARGS="--export-target-id pane_snapshot_png --pane-id analysis"`
- `make dashboard-export DASHBOARD_SESSION_METADATA=/abs/path/dashboard_session_metadata.json DASHBOARD_EXPORT_ARGS="--export-target-id metrics_json --pane-id analysis --active-overlay-id reviewer_findings"`
- `./.venv/bin/python scripts/29_dashboard_shell.py export --dashboard-session-metadata /abs/path/dashboard_session_metadata.json --export-target-id replay_frame_sequence --pane-id scene`

## Testing Strategy

Coverage is split across planner/package tests, analysis normalization tests,
and deterministic export smoke coverage.

`tests/test_dashboard_analysis.py` verifies:

- the packaged session exposes a normalized analysis pane context without raw
  bundle rescans
- overlay normalization keeps shared comparison, wave-only diagnostics,
  validation overlays, and inapplicable overlays explicit
- the packaged shell bootstrap carries the richer analysis context and export
  target catalog

`tests/test_dashboard_exports.py` acts as the requested smoke workflow. It
builds a representative fixture dashboard session, drives one analysis overlay
selection, and executes three export paths:

- still-image snapshot export from the analysis pane
- metrics export from the analysis pane
- replay-oriented frame-sequence export from the scene pane

The test asserts deterministic artifact discovery, stable export metadata
paths, artifact inventory records, and expected summary fields such as active
overlay identity, open finding count, phase-map reference count, and replay
frame count.

Existing dashboard planner and shell tests continue to exercise the packaged
session path, which helps catch linkage regressions outside the new analysis
pane module.

## Simplifications

The first analysis pane is still a deterministic offline HTML surface. It does
not attempt richer browser-side state persistence or DOM screenshot capture.

Still-image export renders deterministic review images from normalized pane
state rather than trying to snapshot a live browser session. That keeps export
behavior reproducible under test and usable in non-interactive environments.

Replay export currently supports deterministic frame sequences for panes with a
clear replay model. This ticket does not yet encode `.mp4` or `.webm`
containers.

Ablation summaries are discovered from packaged group metadata using a narrow
heuristic. That is sufficient for the first catalog, but later packaging work
can provide a stronger ablation-specific contract when needed.

## Future Expansion Points

Likely follow-up work:

- add more analysis overlay families once later milestones package denser
  scientific evidence
- expose richer export UX in the shell on top of the new export metadata layer
- support morphology- and circuit-specific replay exports where a canonical
  replay model is available
- replace frame-sequence-only replay output with optional encoded video
  artifacts while preserving the same deterministic manifest contract
- strengthen ablation payload discovery with dedicated packaged fields instead
  of the current group-label heuristic
