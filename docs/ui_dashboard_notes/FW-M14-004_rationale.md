# FW-M14-004 Rationale

## Design Choices

This ticket keeps the scene and circuit panes contract-backed instead of
introducing a browser-only scene graph or a second circuit data model.

The new library helper, `flywire_wave.dashboard_scene_circuit`, does two jobs:

- normalize scene replay context from `stimulus_bundle.v1` or
  `retinal_input_bundle.v1`
- normalize circuit context from the geometry manifest plus the local synapse
  registry and coupling edge references already carried by the selected assets

For the scene pane, the packaged dashboard payload now carries a renderable
frame sequence derived from the canonical input bundle. Stimulus bundles prefer
their recorded frame cache when available and fall back to descriptor-backed
regeneration when the cache is absent. Retinal bundles use the packaged frame
archive and report an unavailable layer cleanly when that archive is missing.

The browser shell renders those packaged frames directly from the embedded
payload, so the scene pane stays usable from `file://` without depending on
fetching local `.npz` files from JavaScript.

For the circuit pane, the payload now distinguishes:

- the selected-root catalog that can drive global neuron selection
- a connectivity context node and edge catalog that can include one-hop peers
  when the local synapse registry exposes them
- explicit linked-selection payloads for click and hover behavior

That preserves the existing root identity, cell type, project role, geometry
manifest, and coupling-bundle vocabulary instead of inventing UI-only aliases.

The shell keeps hover state transient and browser-local. `selected_neuron_id`
remains the serialized contract state, while `hovered_neuron_id` and
`hover_source_pane_id` stay in the app-shell state model so later panes can
respond consistently without mutating `dashboard_session.v1`.

## Testing Strategy

Coverage is split across planner-level and package-level assertions.

The new `tests/test_dashboard_scene_circuit.py` verifies:

- deterministic stimulus-scene frame discovery and payload normalization on the
  fixture dashboard session
- deterministic circuit-context normalization, including connectivity edges and
  linked-selection payloads
- clean unavailable-layer handling for retinal scene context when the frame
  archive is removed
- packaged bootstrap coverage showing the scene and circuit linkage data is
  carried through to the offline shell

Existing dashboard planner and shell tests continue to run so the new pane
payloads are exercised inside the full session packaging path rather than only
through isolated helper tests.

## Simplifications

The first scene renderer ships grayscale downsampled frames in the packaged
payload instead of a richer image codec or a client-side `.npz` loader.

The first circuit pane uses a restrained SVG graph, roster cards, and metadata
cards rather than a maximal graph-visualization stack. Context peers are
hoverable, but only selected-subset roots are selectable because later
dashboard panes still operate on the active subset contract.

Connectivity weighting currently uses synapse-row counts from the local synapse
registry. It does not try to infer more detailed signed or delayed coupling
strength semantics than the existing Milestone 7 local artifacts explicitly
provide.

## Future Expansion Points

Likely follow-up work:

- move scene payload packaging from embedded base64 frames to a dedicated
  dashboard-owned replay asset if larger sessions make the bootstrap too heavy
- add richer scene overlays for retinal detector annotations or stimulus-space
  landmarks
- let the circuit pane surface more registry metadata when broader neuron or
  connectivity registries are packaged alongside the selected subset
- reuse the linked hover state in the morphology, time-series, and analysis
  panes for stronger coordinated highlighting once those panes gain richer
  visuals
