# FW-M16-004 Rationale

## Design Choices

This ticket adds one canonical local showcase player in
`flywire_wave.showcase_player` and keeps the command surface in the existing
`scripts/35_showcase_session.py` entrypoint instead of creating a second
runtime script. The planner now packages a real serialized player state in
`showcase_state.json` and richer runtime metadata in `showcase_script.json`,
so later rehearsal, export, and readiness workflows can all consume the same
bundle-owned artifacts.

The player deliberately stays a thin layer on top of earlier milestone
contracts:

- `showcase_session.v1` still owns narrative step order, preset identities,
  evidence hooks, and export targets.
- `dashboard_session.v1` still owns replay semantics and the synchronized
  global interaction state.
- the player never invents a separate dashboard state model. It applies the
  selected showcase preset patch onto the packaged dashboard session state and
  then rebuilds replay state from the packaged dashboard replay model. That is
  the core desynchronization guardrail for pause, resume, seek, and step
  jumps.

Guided autoplay and presenter rehearsal intentionally share the same serialized
state shape. The only material mode difference is the `auto_advance` behavior
recorded in `runtime_mode` and `sequence_state`; the same step order, preset
resolution, checkpoint format, and synchronized dashboard-state derivation are
used in both cases.

## Testing Strategy

The new regression coverage in `tests/test_showcase_player.py` uses the
existing packaged showcase fixture flow, then exercises the player through:

- deterministic initial state discovery from a packaged showcase bundle
- direct step jump into a replay beat
- seek and replay-cursor synchronization checks against both
  `global_interaction_state` and `replay_state`
- resume from a separately serialized checkpoint
- guided autoplay advancement to later beats and then to the final summary
- reset and direct preset jump behavior
- clear failures for unsupported step jumps and incomplete packaged showcase
  state

That test complements the earlier planning tests rather than replacing them:
planning still verifies deterministic showcase assembly, while the new player
test verifies deterministic runtime control flow on the packaged result.

## Simplifications

The first version is intentionally local and deterministic:

- playback is command-driven rather than wall-clock-driven
- autoplay advances across stable step boundaries instead of trying to stream a
  real-time presentation loop
- seek only operates on beats that expose the `scrub_time` operator control
- the player writes JSON state and summaries, not a polished browser control
  surface

These simplifications keep the implementation reusable for automation and
rehearsal without introducing hidden timing behavior or browser-only state.

## Future Expansion

The cleanest follow-on paths are:

- add richer per-step dwell or cue timing metadata once Milestone 16 needs a
  smoother autoplay timeline
- connect the serialized player state to later export and capture tickets so
  saved checkpoints can directly drive stills and replay media
- expose the same state machine in the browser shell once polished rehearsal UI
  controls are needed, while continuing to serialize through the same
  showcase-owned JSON state
- add explicit comparison-toggle and export-trigger commands if later tickets
  need those controls surfaced through the same runtime layer
