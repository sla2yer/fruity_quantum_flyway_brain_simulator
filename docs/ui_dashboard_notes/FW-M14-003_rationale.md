# FW-M14-003 Rationale

## Design Choices

This ticket keeps the first Milestone 14 shell inside the repo's existing
offline-review model instead of introducing a backend or a separate frontend
toolchain.

The packaged dashboard now writes:

- `dashboard_session.json`
- `dashboard_session_payload.json`
- `session_state.json`
- `app/index.html`
- `app/dashboard_asset_manifest.json`
- `app/assets/dashboard_shell.<content-hash>.css`
- `app/assets/dashboard_shell.<content-hash>.js`

That keeps the app discovery anchor where `dashboard_session.v1` already
reserved it, while making the shell reviewable as deterministic local files.

The first implementation uses one shell-owned linked state model in the browser
with the same contract-facing fields the package already serializes:

- `selected_arm_pair`
- `selected_neuron_id`
- `selected_readout_id`
- `active_overlay_id`
- `comparison_mode`
- `time_cursor`

`time_cursor` continues to own `time_ms`, `sample_index`, and
`playback_state`, so replay stays coupled to one canonical cursor instead of
pane-local timers.

The shell embeds a deterministic bootstrap payload into `index.html` even
though the package also writes standalone JSON artifacts. That duplication is
intentional for the first version: it allows reliable `file://` opening from
local disk without depending on browser fetch behavior for adjacent JSON files.

## Local Command

Canonical manifest-driven build and open command:

```bash
make dashboard-open CONFIG=<path-to-config.yaml>
```

Direct script form:

```bash
python3 scripts/29_dashboard_shell.py build \
  --config <path-to-config.yaml> \
  --manifest manifests/examples/milestone_1_demo.yaml \
  --schema schemas/milestone_1_experiment_manifest.schema.json \
  --design-lock config/milestone_1_design_lock.yaml \
  --open
```

To reopen an already packaged session:

```bash
python3 scripts/29_dashboard_shell.py open \
  --dashboard-session-metadata data/processed/simulator_results/dashboard_sessions/<experiment_id>/<session_spec_hash>/dashboard_session.json
```

## Testing Strategy

Coverage is split between the planner tests from `FW-M14-002` and one new
shell-focused smoke test.

The new shell smoke test verifies:

- manifest-driven dashboard packaging still succeeds on the representative
  fixture session
- deterministic CSS and JS asset identities are regenerated with the same
  content-hashed file names
- the generated `index.html` declares all five pane shells
- the embedded bootstrap payload exposes the linked state model and expected
  packaged paths for local loading

This keeps the first shell regression surface narrow and deterministic while
still checking the parts most likely to drift during review.

## Simplifications

This ticket does not attempt full scientific pane rendering. The panes are
deliberately shell-level summaries with linked controls and bridge links back
to packaged analysis and validation reports.

The client code is plain JavaScript plus deterministic CSS copied from package
assets. There is no node-based bundler, dev server, or runtime dependency on
remote fonts or APIs.

The shell only writes a static asset manifest for the generated frontend
assets. Those assets are intentionally internal to the app directory rather
than new top-level `dashboard_session.v1` artifacts.

## Future Expansion Points

Likely next steps after this shell lands:

- replace pane summary bands with richer scene, morphology, and time-series
  visuals while keeping the same linked store
- add deterministic export writers for state snapshots, pane captures, and
  replay media
- promote selected shell summaries into reusable client-side view models once
  pane work becomes more detailed
- extend the smoke harness into a committed regression baseline if the asset
  manifest or bootstrap schema becomes a cross-ticket compatibility target
