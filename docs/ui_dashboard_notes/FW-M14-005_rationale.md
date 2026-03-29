# FW-M14-005 Rationale

## Design Choices

This ticket adds one morphology-specific normalization layer instead of pushing
geometry discovery and overlay interpretation into the browser shell.

`flywire_wave.dashboard_morphology` builds a contract-backed pane context from:

- the packaged circuit/root catalog
- simulator bundle morphology discovery helpers
- shared readout payload discovery
- packaged wave-only root state exports

That keeps Milestone 14 aligned with the earlier bundle contracts. The pane
does not guess file names or scan directories directly.

Mixed-fidelity rendering is intentionally truth-preserving:

- surface roots render a simplified surface mesh when a usable local mesh is
  packaged
- surface roots fall back to a surface patch proxy when wave state exists but a
  renderable mesh is missing
- skeleton roots render deterministic polylines from the packaged SWC
- point roots stay displayable as explicit point fallbacks

The UI labels the chosen representation and its truth note so a reduced-fidelity
fallback is visible rather than being presented as fabricated surface detail.

Overlay handling stays visibly partitioned by scope:

- `shared_readout_activity` is labeled `shared_comparison`
- `wave_patch_activity` is labeled `wave_only_diagnostic`
- overlays owned by other panes are marked `inapplicable`

The browser shell renders a small SVG morphology stage from the normalized
render model instead of loading raw mesh files in JavaScript. That keeps the
offline `file://` dashboard self-contained and deterministic for fixture tests.

## Testing Strategy

Coverage is split between planner/package tests and morphology-focused fixture
tests.

`tests/test_dashboard_morphology.py` verifies:

- a representative packaged session exposes both a surface-resolved render
  model and a reduced-fidelity skeleton render model
- overlay view-model resolution normalizes shared-comparison and wave-only
  overlay state consistently
- unsupported overlays are reported as inapplicable with clear guidance
- point-fallback sessions remain displayable when no mesh or skeleton geometry
  is packaged

`tests/test_dashboard_session_planning.py` extends the fixture pipeline so the
dashboard uses deterministic geometry and mixed-fidelity wave-state exports
without hardcoded lookups. The dashboard shell and scene/circuit tests continue
to exercise the full packaged session path, which catches linkage regressions in
the offline app bootstrap.

## Simplifications

The first morphology pane is a deterministic 2D SVG renderer, not a full 3D
camera stack. Camera focus is normalized and exposed in the payload, but the
shell currently uses that metadata for linked focus/readout state instead of a
true orbital camera.

Surface rendering uses a projected simplified mesh or patch proxy. It does not
attempt hidden-surface removal, volumetric shading, or client-side mesh loading.

Wave-only overlay support is intentionally narrow in this ticket. The pane
ships one baseline shared-comparison overlay and one wave-only diagnostic
family, with unavailable and inapplicable states made explicit.

## Future Expansion Points

Likely follow-up work:

- replace the SVG stage with a richer canvas or WebGL renderer while preserving
  the same morphology view-model contract
- add more contract-approved overlay families, including validation-oriented
  evidence when that data has a clear morphology mapping
- support multi-neuron camera framing and denser linked hover behavior across
  circuit, morphology, and time-series panes
- add richer surface diagnostics when later wave bundles package more detailed
  per-patch topology or phase-local metadata
