# FW-M14-001 Rationale

## Design Choices

This ticket adds one library-owned contract module instead of letting Milestone
14 vocabulary live in future UI code, HTML reports, or script-local JSON. The
module owns:

- the five pane IDs
- the first overlay categories and overlay IDs
- the comparison-mode IDs
- the export target IDs
- the global interaction-state schema
- the metadata-backed artifact-hook roles that bridge simulator, analysis,
  validation, and dashboard-package assets

The delivery model is intentionally `self_contained_static_app`. That matches
the repo's existing offline-review bias while still leaving room for a richer
interactive shell later.

The contract also preserves the fairness boundary that Milestone 12 and
Milestone 13 already established:

- shared comparison content stays tied to shared readouts
- wave-only diagnostics stay labeled as diagnostics
- validation evidence stays reviewer-oriented instead of being recast as one
  more metric panel

## Testing Strategy

The regression coverage is centered on the contract surface introduced here:

- deterministic dashboard-contract serialization and round-tripping
- stable pane, overlay, export-target, and artifact-hook discovery
- normalization of representative fixture dashboard-session metadata with
  reordered artifact references and humanized IDs
- deterministic session metadata serialization plus discovery of both upstream
  and dashboard-package artifact references

That keeps the test surface narrow but still proves later Milestone 14 tickets
have one stable vocabulary to build on.

## Simplifications

This ticket does not implement the dashboard planner, app shell, pane rendering,
or export executors. It only reserves their contract vocabulary and package
slots.

The packaged dashboard assets are intentionally minimal:

- metadata
- reserved session payload
- serialized session state
- reserved app-shell entrypoint

That is enough to lock discovery and naming now without pretending that the
later UI stack has already landed.

## Future Expansion Points

Later Milestone 14 tickets can build on this contract by adding:

- manifest- or bundle-driven dashboard planning
- packaged pane payloads and deterministic app-shell generation
- richer overlay catalogs per pane
- session-aware export writers for stills, metrics, and replay media
- readiness and smoke workflows for the full packaged dashboard

Those additions should keep the IDs and fairness boundaries frozen here unless a
real contract change is needed.
