# Milestone 8B Retinal Input Bundle Contract And Ommatidial Sampling Choice

This note freezes the Milestone 8B handoff between world-facing visual sources
and fly-facing retinal input so later scene, simulator, and UI work can target
one explicit bundle contract, one explicit meaning of a retinal frame, and one
explicit set of coordinate and timing conventions.

## Contract summary

The canonical Milestone 8B retinal contract is `retinal_input_bundle.v1`.

The bundle owns:

- one canonical bundle ID built from upstream source identity plus the retinal
  sampling-spec hash
- one authoritative metadata file that records the retinal-contract version,
  design-note version, source identity, eye ordering, ommatidial ordering,
  frame timing, coordinate conventions, sampling-kernel settings, signal
  conventions, and the simulator-facing early-visual mapping
- one optional sampled frame archive for deterministic local replay

The canonical layout is:

- `config.paths.processed_retinal_dir/bundles/<source_kind>/<source_family>/<source_name>/<source_hash>/<retinal_spec_hash>/retinal_input_bundle.json`
- `config.paths.processed_retinal_dir/bundles/<source_kind>/<source_family>/<source_name>/<source_hash>/<retinal_spec_hash>/retinal_frames.npz`

`retinal_input_bundle.v1` intentionally keeps the surface small. More sidecars
may be added later, but those paths are the stable discovery surface for the
retinal recording itself.

## Candidate abstraction families

### Direct per-ommatidium irradiance

Definition:

- each sampled frame stores one irradiance value per eye and per ommatidium
- later consumers can derive temporal filters, feature maps, or UI rasters from
  this detector-level representation

Advantages:

- closest to the fly-facing sampling event the later simulator actually needs
- keeps bundle identity tied to stable detector ordering rather than a display
  raster convention
- easiest representation to compare across simulator, QA, and UI consumers
- avoids silently baking later feature-extraction assumptions into the contract

Costs:

- less convenient for human preview than an image-like raster
- later UIs need a detector-layout-aware rendering step

### Eye-image raster intermediates

Definition:

- first resample each eye into an image grid, then treat that raster as the
  retinal handoff

Advantages:

- easy to display and debug visually
- fits commodity image tooling well

Costs:

- introduces one extra resampling layer before the simulator ever sees the
  input
- binds bundle identity to a raster layout that the fly does not physically
  observe
- makes detector indexing and acceptance kernels harder to audit

### Higher-level retinotopic feature maps

Definition:

- treat motion-energy channels, contrast filters, or other early visual feature
  maps as the primary retinal output

Advantages:

- can align directly with some later model families
- compact for task-specific baselines

Costs:

- bakes model assumptions into the contract too early
- blocks fair comparisons between different simulator or front-end pipelines
- loses the detector-level input that later QA and ablation work needs

## Decision

The default Milestone 8B abstraction is `direct_per_ommatidium_irradiance`.

`retinal_input_bundle.v1` serializes only that family. Eye-image rasters and
higher-level feature maps remain valid derived views or future-contract options,
but they are not the authoritative handoff in this version.

Why this is the default:

- Milestones 8C, 9, and 10 need one unambiguous detector-level definition of
  “the same retinal input”
- later simulators should share one source of truth before they add their own
  filtering or state abstractions
- UI code can always render detector values into a view, but it cannot recover
  omitted detector semantics from an arbitrary raster or feature stack

## What one retinal frame means

One canonical retinal frame is a dense `time x eye x ommatidium` sample table
with:

- eye axis order fixed by the recorded `eye_order`, default `[left, right]`
- eye indexing fixed by `axis_index_matches_eye_order`
- ommatidial ordering fixed by `stable_eye_local_ommatidium_index`
- one shared `ommatidium_count_per_eye` recorded in the bundle metadata
- value semantics fixed to `per_ommatidium_linear_irradiance`

Meaning:

- frame `t` is the binocular detector snapshot for one sample-hold time bin
- later simulator and UI code may reshape or render the data, but they may not
  silently reorder the eye axis or ommatidial axis while still claiming they
  are consuming the same bundle

## Default simulator-facing mapping

Milestone 8B now also fixes one default simulator handoff on top of those
frames:

- simulator representation: `early_visual_unit_stack`
- tensor layout: dense `time x eye x unit x channel`
- unit semantics: one early-visual unit per eye-local ommatidium
- default channel order: `["irradiance"]`
- mapping family: `identity_per_ommatidium`

Meaning:

- unit index `u` for one eye is the same physical detector as ommatidium index
  `u` in that eye's detector table
- aggregation is identity, adaptation is `none`, and normalization is limited
  to clipping into the recorded signal-convention bounds
- the extra channel axis is reserved explicitly so later milestones can append
  richer early-visual channels without changing the default irradiance channel
  meaning

## Coordinate conventions

All Cartesian frames are right-handed.

### World frame

- frame name: `world_cartesian`
- origin: `scene_defined_world_origin`
- axes: `+x forward`, `+y left`, `+z up`

### Body frame

- frame name: `fly_body`
- origin: `thorax_center`
- axes: `+x anterior`, `+y left`, `+z dorsal`

### Head frame

- frame name: `fly_head`
- origin: `head_center`
- axes: `+x anterior`, `+y left`, `+z dorsal`
- zero-pose alignment: aligned with the body frame

### Eye frame

- frame name: `compound_eye_local`
- origin: `eye_center`
- axes: `+z optical_axis_outward`, `+x dorsal`, `+y completes_right_handed_frame`
- positive azimuth is toward `+y`
- positive elevation is toward `+x`

Meaning:

- later geometry code may choose any internal transform implementation it wants
  as long as it lands on these same external frame semantics
- left and right eyes may have different rigid transforms from the head frame,
  but they must share the same local eye-axis naming and angular sign
  conventions

## Timing and signal conventions

### Temporal sampling

Milestone 8B uses the same conservative timing convention as Milestone 8A:

- time unit: milliseconds
- frame timing block records `time_origin_ms`, `dt_ms`, `duration_ms`, and
  `frame_count`
- sampling mode: `sample_hold`

Meaning:

- retinal frame `k` is authoritative for the half-open interval
  `[time_origin_ms + k * dt_ms, time_origin_ms + (k + 1) * dt_ms)`
- later simulators may integrate internally at finer timesteps, but they must
  preserve the same piecewise-constant bundle values at the retinal frame
  boundaries unless a later contract revision says otherwise

### Signal convention

Milestone 8B fixes one conservative detector-value convention:

- encoding: `linear_irradiance_unit_interval`
- minimum value: `0.0`
- neutral value: `0.5`
- maximum value: `1.0`
- contrast semantics: `signed_delta_from_neutral_gray`
- positive polarity means `brighter_than_neutral`

Meaning:

- the detector values preserve the Milestone 8A linear luminance convention
  rather than introducing display gamma or simulator-specific normalization
- out-of-range sampling results must be clipped into `[0.0, 1.0]`, and that
  clipping is part of the contract

## Sampling-kernel semantics

The default Milestone 8B sampling kernel is
`gaussian_acceptance_weighted_mean`.

Every bundle records:

- kernel family
- acceptance angle in degrees
- support radius in degrees
- kernel normalization rule
- out-of-field policy and background fill value

Meaning:

- later samplers may optimize the implementation, but the realized detector
  values must remain equivalent to the recorded kernel settings
- out-of-field handling is never implicit; the background fill behavior is part
  of the reproducibility contract

## Invariants later milestones must preserve

Later scene, simulator, and UI milestones must preserve these invariants when
they claim to reuse `retinal_input_bundle.v1`:

- bundle identity is the tuple `(contract_version, source_kind, source_family,
  source_name, source_hash, retinal_spec_hash)`
- the authoritative source identity recorded in `source_reference` must not be
  replaced with an ad hoc file path or unnamed frame stack
- `direct_per_ommatidium_irradiance` remains the source-of-truth handoff even
  if a downstream consumer also builds rasters or feature maps
- eye ordering and ommatidial ordering are explicit contract fields, not
  consumer-defined guesses
- world, body, head, and eye frame semantics may not be mirrored or rotated
  silently between stages
- time stays in milliseconds with sample-hold semantics unless a later contract
  revision explicitly supersedes this one
- detector values stay in the recorded linear-irradiance convention; later
  contrast or adaptation transforms must be explicit derived steps
