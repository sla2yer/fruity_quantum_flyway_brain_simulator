# Milestone 8A Canonical Stimulus Bundle Contract And Generator Choice

This note freezes the Milestone 8A stimulus handoff so later retinal-sampling,
scene, simulator, and orchestration work can target one explicit bundle
contract, one explicit replay model, and one explicit interpretation of "the
same stimulus."

## Contract summary

The canonical Milestone 8A bundle contract is `stimulus_bundle.v1`.

The bundle owns:

- one canonical bundle ID built from canonical stimulus family, canonical
  stimulus name, and the reproducibility hash
- one authoritative metadata file that records the stimulus-contract version,
  design-note version, replay semantics, and all deterministic reproduction
  fields
- one optional cached frame archive for acceleration
- one optional preview animation for human review
- zero or more compatibility-alias records that point old names at the same
  canonical bundle

The canonical layout is:

- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/stimulus_bundle.json`
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/stimulus_frames.npz`
- `data/processed/stimuli/bundles/<stimulus_family>/<stimulus_name>/<parameter_hash>/stimulus_preview.gif`
- `data/processed/stimuli/aliases/<alias_family>/<alias_name>/<parameter_hash>.json`

Later tickets may add more sidecars, but those paths are the stable discovery
surface.

## Candidate representation families

### Pure procedural regeneration

Definition:

- store only generator descriptors, temporal sampling, conventions, and seed
- rebuild every frame on demand

Advantages:

- smallest on-disk footprint
- easiest way to preserve one authoritative semantic description
- naturally avoids cache invalidation bugs because there is no cache

Costs:

- later tooling pays generation cost every time
- offline review becomes slower because previews and retinal sampling need to
  regenerate first
- debugging cache-versus-regeneration drift is replaced with repeated compute

### Fully cached frame bundle

Definition:

- treat the serialized frame archive as the primary artifact
- the bundle is mostly an index into pre-rendered frames

Advantages:

- fastest playback for downstream tools
- easy to hand off to image-oriented samplers and UIs
- cheap to inspect without re-running the generator

Costs:

- large storage footprint
- cache invalidation becomes the core contract problem
- easy for downstream code to bind itself to one frame layout instead of the
  semantic generator description
- renaming files or changing frame dtype can accidentally change bundle
  identity

### Hybrid descriptor plus cache

Definition:

- the descriptor metadata is authoritative
- frame caches are optional accelerators derived from that descriptor
- later tooling may regenerate when the cache is absent, but not reinterpret
  the descriptor

Advantages:

- keeps one semantic source of truth
- supports cheap replay when the cache exists
- makes deterministic regeneration and offline review compatible
- keeps later milestones from binding bundle identity to one incidental frame
  serialization

Costs:

- requires explicit rules for cache authority and drift checks
- slightly more metadata than either extreme

## Decision

The default Milestone 8A representation family is
`hybrid_descriptor_plus_cache`.

Pure procedural descriptors and fully cached frame bundles remain recognized
comparison modes for debugging, ablations, or extreme storage/performance
constraints, but the authoritative Milestone 8A contract assumes:

- the metadata descriptor is the source of truth
- the cache is optional
- the same descriptor, seed, and contract version mean the same stimulus even
  if one run has a frame cache and another does not

Why this is the default:

- Milestones 8B and 8C need semantic coordinates, timing, and luminance rules,
  not just opaque frame filenames
- Milestones 9 and 15 need a compact way to refer to a reusable stimulus in
  manifests and batch runs
- deterministic regeneration matters because later sweeps will not want to
  commit every frame archive for every variant
- optional caching still matters because retinal projection and UI inspection
  will repeatedly revisit the same stimuli

## Coordinate, timing, and luminance conventions

### Spatial frame

Milestone 8A uses one canonical 2D image-plane frame:

- frame name: `visual_field_degrees_centered`
- origin: `aperture_center`
- horizontal axis: `azimuth_deg_positive_right`
- vertical axis: `elevation_deg_positive_up`
- raster samples are defined at `pixel_centers`
- the bundle records both raster size (`width_px`, `height_px`) and angular
  extent (`width_deg`, `height_deg`)

Interpretation:

- frame coordinates are centered on the stimulus aperture rather than anchored
  to a later camera or retinal lattice implementation
- later retinal or scene code may transform into other coordinate systems, but
  it must preserve the meaning of this canonical frame when claiming to replay
  the same stimulus

### Temporal sampling

Milestone 8A uses one canonical time unit and one canonical default playback
rule:

- time unit: milliseconds
- bundle time origin: `time_origin_ms`, default `0.0`
- frame step: `dt_ms`
- total duration: `duration_ms`
- frame count: `frame_count`
- sampling mode: `sample_hold`

Meaning:

- each generated frame is authoritative for the half-open interval
  `[t, t + dt_ms)`
- later simulators may integrate internally at finer timesteps, but they must
  preserve the same piecewise-constant stimulus values at the bundle frame
  boundaries unless a later contract explicitly versions a different temporal
  interpolation rule

### Luminance and contrast

Milestone 8A fixes one conservative luminance convention:

- encoding: `linear_luminance_unit_interval`
- minimum value: `0.0`
- neutral gray: `0.5`
- maximum value: `1.0`
- contrast semantics: `signed_delta_from_neutral_gray`
- positive polarity means `brighter_than_neutral`

Meaning:

- generator parameters express signed luminance deltas relative to neutral gray
- emitted frame values live in linear luminance space, not gamma-compressed
  display space
- out-of-range results are clipped into `[0.0, 1.0]`, and that clipping is part
  of the canonical replay semantics

## Determinism, hashing, and aliases

### Deterministic seeding

Every bundle records:

- one non-negative integer seed
- one RNG family, fixed today to `numpy_pcg64`
- a seed scope stating that all stochastic generator branches derive from that
  recorded seed

Rules:

- stochastic subcomponents may derive child streams internally, but only as a
  deterministic function of the recorded seed
- downstream tools may not inject extra randomness while still claiming they are
  replaying the same bundle

### Parameter hash

Milestone 8A uses one reproducibility hash:

- algorithm: `sha256`
- input: canonical JSON of the parameter snapshot, deterministic seed and RNG
  family, temporal sampling block, spatial frame block, and luminance
  convention block
- excluded inputs: cache status, preview status, artifact filenames, and
  compatibility aliases

Meaning:

- the hash names the reproducible stimulus specification, not the incidental
  cache state
- a bundle cache may be added or deleted without changing the parameter hash
- renaming a stimulus through compatibility aliases must not change the
  parameter hash

### Compatibility aliases

Aliases exist only to preserve discoverability when names change.

Rules:

- aliases point to the canonical bundle metadata path for the same parameter
  hash
- aliases may rename family and/or name, but they may not silently change seed,
  timing, spatial frame, luminance semantics, or generator parameters
- canonical metadata remains authoritative; alias records are lookup shims, not
  alternate metadata authorities

## Invariants for later milestones

Later retinal-sampling, scene, simulator, and orchestration code must preserve
these invariants when they claim to reuse or replay `stimulus_bundle.v1`:

- bundle identity is the tuple `(contract_version, stimulus_family,
  stimulus_name, parameter_hash)`
- reproducibility identity is the tuple `(contract_version, parameter_hash,
  seed, temporal_sampling, spatial_frame, luminance_convention)`
- descriptor metadata is authoritative; caches may accelerate replay but may not
  redefine pixel values, timestamps, or conventions
- alias lookup must resolve to the same canonical metadata rather than
  duplicating or mutating the canonical bundle
- retinal sampling may resample into another lattice, but it must preserve the
  same canonical time axis and the same underlying linear-luminance semantics
- simulator orchestration may store only the compact bundle reference, but it
  must resolve through the library contract rather than hardcoded filenames

The practical consequence is simple: later code may transform, cache, project,
or subsample the stimulus, but it does not get to redefine what bundle it came
from.
