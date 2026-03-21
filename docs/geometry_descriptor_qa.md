# Geometry Descriptors And QA Budgets

Milestone 5 now writes two sidecars per processed morphology bundle:

- `<root_id>_descriptors.json`: cheap derived summaries for the raw mesh, simplified mesh, coarse patch graph, and optional skeleton
- `<root_id>_qa.json`: thresholded comparisons that turn those summaries into pass, warn, or fail outcomes

This note documents the first descriptor set and the default budgets so later
Milestone 6 operator work and Milestone 11 hybrid-morphology work have a shared
baseline for what currently counts as an acceptable approximation.

## Why these descriptors exist

The first pass stays deliberately pragmatic:

- counts: vertices, faces, edges, patch count, skeleton nodes, segments
- component structure: connected-component counts plus largest-component fractions
- size and extent: surface area, optional watertight volume, axis-aligned bounds, extents, centroid
- local scale proxies: mean / median / max surface edge length
- coarse occupancy: patch-size statistics, dominant-patch fraction, singleton-patch fraction, centroid extent coverage, surface-vertex coverage ratio
- skeleton summary: cable length, branch points, leaves, roots, bounds, extent

These metrics are cheap to compute locally, stable enough for regression tests,
and easy to explain. They do not try to prove physical equivalence. They answer
the narrower Milestone 5 question: did the asset builder preserve gross
connectivity, length scales, and occupancy well enough to justify later,
more-specific numerical checks?

## Default QA budgets

The build currently evaluates these thresholds from `meshing.qa_thresholds`:

| Metric | Default warn | Default fail | Blocking by default | Rationale |
| --- | ---: | ---: | :---: | --- |
| `simplified_component_count_delta` | disabled | `0.0` | yes | Simplification should not create or remove connected pieces. |
| `simplified_surface_area_rel_error` | `0.15` | `0.30` | yes | Gross area drift changes membrane-scale operator weights. |
| `simplified_extent_rel_error_max` | `0.10` | `0.20` | yes | Large extent drift changes propagation length scales. |
| `simplified_centroid_shift_fraction_of_diagonal` | `0.05` | `0.10` | no | Useful distortion signal, but not a hard blocker by itself. |
| `simplified_volume_rel_error` | `0.20` | `0.40` | no | Informative only when both meshes are watertight. |
| `coarse_component_count_delta` | disabled | `0.0` | yes | Patch graph connectivity should match the simplified surface. |
| `coarse_surface_vertex_coverage_gap` | disabled | `0.0` | yes | Every simplified vertex must map to a patch. |
| `coarse_max_patch_vertex_fraction` | `0.60` | `0.80` | no | Warn when one coarse patch dominates most of the surface. |
| `coarse_singleton_patch_fraction` | `0.25` | `0.50` | no | Warn when patchification fragments into too many singletons. |

`disabled` means the default profile has no warning band for that metric and
only treats non-zero drift as a failure.

## Blocking vs non-blocking

The QA sidecar can record `fail` for both blocking and non-blocking metrics.
The build script only exits non-zero when a failed check is marked
`blocking: true`.

Current intent:

- blocking: topological integrity and obvious gross geometry drift that would
  invalidate downstream operator construction
- non-blocking: review signals that should be surfaced to humans but may still
  produce usable artifacts for exploratory work

Teams can tighten or relax the budgets per config without changing code.

## Expected follow-up work

Milestone 6 will likely add operator-aware checks such as Laplacian-spectrum
drift, geodesic path distortion, or transfer-operator residuals. Milestone 11
may promote the skeleton summary from descriptive metadata to representation
selection logic. This document only claims a baseline, not completeness.
