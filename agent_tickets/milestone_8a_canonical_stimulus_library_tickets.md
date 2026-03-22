# Milestone 8A Canonical Stimulus Library Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M8A-001 - Freeze a versioned stimulus bundle contract and canonical generator design note
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: stimuli / contracts / docs

### Problem
The repo currently exposes only lightweight stimulus identifiers such as `stimulus_family` and `stimulus_name` in the example experiment manifest, but it has no first-class contract for what a canonical visual stimulus actually is. There is no library-owned definition for stimulus coordinates, luminance semantics, temporal sampling, seeded randomness, cacheable artifacts, replay metadata, or how later milestones should discover a reusable stimulus bundle. Without a versioned contract and a decisive design note, Milestones 8B, 8C, 9, and 15 will end up binding themselves to ad hoc frame layouts and incompatible assumptions about what it means to "replay the same stimulus."

### Requested Change
Define a first-class canonical stimulus bundle contract in library code and document the design choices behind it. Centralize bundle naming, metadata, and discovery so later tooling can resolve a stimulus without hardcoded filenames, and add a markdown design note that compares the viable representation families before choosing the default. The design note should be decisive: choose the default between pure procedural regeneration, fully cached frame bundles, and a hybrid descriptor-plus-cache model; define the canonical spatial coordinate frame and temporal units; specify luminance or contrast conventions; and state how deterministic seeding, parameter hashing, and compatibility aliases must work.

### Acceptance Criteria
- Stimulus bundle path construction and metadata serialization are centralized in library code rather than being reimplemented inside scripts.
- The chosen contract records an explicit stimulus-contract version plus the metadata needed to reproduce a stimulus deterministically, including timing, spatial frame, luminance conventions, and parameter snapshot or hash.
- A dedicated markdown design note compares the supported representation strategies, chooses the default, documents the coordinate and timing conventions, and names the invariants later retinal-sampling and simulator code must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 8A contract sits alongside the existing subset, geometry, and operator contracts.
- Regression coverage verifies deterministic contract serialization, stable path generation, and bundle discovery for fixture stimulus specs.

### Verification
- `make test`
- A focused unit test that builds fixture stimulus metadata and asserts deterministic manifest or bundle serialization plus path discovery

### Notes
This ticket should land first. Keep the contract implementation boring and explicit: one place to build paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the representation model. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8A-002 - Build a typed stimulus specification, preset registry, and config normalization layer
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: stimuli / config / API design

### Problem
Even with a bundle contract, the repo still has no stable way to ask for a standard stimulus from config. A caller would have to pass untyped dictionaries, duplicate defaults, and guess family-specific parameter names. That would make `stimulus_family` and `stimulus_name` little more than labels instead of a reproducible input contract, and it would make later experiment orchestration fragile whenever a family adds a new parameter or compatibility alias.

### Requested Change
Implement the library-owned stimulus specification layer that resolves config or manifest inputs into normalized, typed stimulus specs. The API should accept a family identifier, named preset, and optional overrides, then return a normalized spec with explicit defaults, units, duration, frame timing, spatial extent, and deterministic seed behavior. Keep the implementation YAML-friendly and manifest-friendly, reserve stable family identifiers for every Milestone 8A family, and preserve compatibility with the existing `moving_edge` naming used by the Milestone 1 example manifest.

### Acceptance Criteria
- There is one canonical API that resolves `stimulus_family`, `stimulus_name`, and parameter overrides into a normalized stimulus spec and registry entry.
- Family-specific parameter validation fails clearly for missing, misspelled, or out-of-range values instead of deferring errors until frame generation.
- Named presets and aliases are discoverable through library code and stable enough for manifests, config examples, and later UI tooling to reference directly.
- The resolved spec captures explicit defaults for timing, spatial extent, background level, polarity or contrast semantics, and deterministic seed handling.
- Regression coverage validates normalization, alias handling, parameter overrides, and clear failure modes using fixture configs only.

### Verification
- `make test`
- A focused unit test that resolves several fixture stimulus configs, including a Milestone 1 `moving_edge` compatibility case, and asserts normalized output plus validation errors

### Notes
Assume `FW-M8A-001` is already in place. The main goal is to make standard stimuli truly callable from config rather than merely selectable by a string label. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8A-003 - Implement flash, moving-bar, translated-edge, and drifting-grating generators with deterministic frame synthesis
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: stimuli / frame synthesis / core lab patterns

### Problem
The roadmap explicitly calls for flashes, moving bars, drifting gratings, and translated edge patterns, yet the repo has no canonical generator implementation for any of them. The existing Milestone 1 manifest names a moving-edge stimulus, but there is no shared generation layer that defines how onset timing, polarity, aperture, speed, spatial frequency, contrast, or phase should map into actual frames. Without this, every downstream consumer will end up reinterpreting the same stimulus differently.

### Requested Change
Implement the first wave of canonical lab-stimulus generators using the normalized spec and contract established in `FW-M8A-001` and `FW-M8A-002`. Add generator implementations for flashes, moving bars, translated edge patterns, and drifting gratings, along with the family-specific metadata needed to replay or inspect them later. Make the rendering semantics explicit for background intensity, polarity, onset and offset timing, direction, velocity, aperture or mask handling, grating phase, spatial frequency, contrast, and edge sharpness. Preserve a stable compatibility path for the current `moving_edge` naming.

### Acceptance Criteria
- Flashes, moving bars, translated edge patterns, and drifting gratings can each be instantiated through the canonical registry and sampled into deterministic frame outputs or equivalent replayable field evaluators.
- The implemented generators record the family-specific metadata needed to explain how each stimulus was rendered, including direction, motion speed, polarity, contrast, aperture, and phase-related fields where applicable.
- Frame generation obeys the documented timing and spatial conventions from the design note and keeps intensity or contrast values within the declared bounds.
- Existing `moving_edge` references continue to work through a compatibility alias or a documented migration shim that keeps current Milestone 1 assets valid.
- Regression coverage exercises one or more fixture examples per family and asserts deterministic output, frame-shape invariants, timing semantics, and compatibility behavior.

### Verification
- `make test`
- A fixture-driven test suite that renders one or more examples for each implemented family and asserts metadata plus deterministic frame or sample outputs

### Notes
Land this before the more complex radial and rotational motion families. These generators are the likely first vertical-slice stimuli, so keep them inspectable and well documented rather than overly clever. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8A-004 - Implement looming, expansion-contraction flow, and rotating-flow generators on the same canonical visual field contract
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: stimuli / optic flow / radial motion

### Problem
Milestone 8A also calls for looming stimuli plus expansion, contraction, and rotating flow, but those families are more sensitive to coordinate choices than simple translated patterns. If they are bolted on later without the same field contract, later retinal sampling and scene tooling will have to guess how centers of motion, angular velocity, radial speed, clipping, and polarity should behave. That would undermine the point of having a canonical stimulus library.

### Requested Change
Implement the canonical generator families for looming, expansion or contraction flow, and rotating flow using the same normalized field and timing conventions as the simpler generators. The implementation should support explicit motion centers, radial or angular velocity parameters, polarity, apertures or masks, looming size-growth semantics, and the metadata needed to distinguish inward versus outward or clockwise versus counterclockwise motion. Keep the resulting outputs deterministic, inspectable, and ready for later retinal sampling without hidden coordinate transforms.

### Acceptance Criteria
- Looming, expansion or contraction flow, and rotating flow are each instantiable through the canonical registry and produce deterministic replayable outputs using the shared coordinate contract.
- Each generated stimulus records the parameters required to explain the motion field, including motion center, sign or direction, velocity units, growth schedule where applicable, and clipping or aperture behavior.
- The implemented families respect the documented spatial origin, axis orientation, and temporal conventions established earlier rather than inventing family-specific coordinate systems.
- Regression coverage includes fixture cases that validate symmetry or directional sanity checks, center-of-motion behavior, and deterministic serialization or frame output.
- The implementation stays library-owned and avoids duplicating motion-field logic across CLI wrappers or one-off notebooks.

### Verification
- `make test`
- A focused fixture test suite that instantiates the radial and rotational motion families and asserts motion metadata plus deterministic sample outputs

### Notes
Assume `FW-M8A-001` through `FW-M8A-003` are already in place. Favor explicit metadata and easily auditable rendering rules over compressed or opaque representations. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8A-005 - Integrate canonical stimuli with experiment manifests, schema validation, and config discovery
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: manifests / schema / experiment reproducibility

### Problem
Milestone 8A is not complete if the generators only exist as Python calls. The repo already uses config and manifest contracts to make experiments reproducible, and the example Milestone 1 manifest depends on `stimulus_family` plus `stimulus_name`. Right now there is no schema-backed way to declare canonical stimulus parameters, preserve resolved defaults, record a stimulus bundle reference, or validate that a manifest is actually pointing at a real callable stimulus configuration.

### Requested Change
Extend the experiment-manifest and config plumbing so canonical stimuli can be declared, validated, resolved, and rediscovered reproducibly. Preserve the simple top-level family and name fields where they are already in use, but add the normalized fields or compatibility shim needed to capture parameter overrides, deterministic seed behavior, contract version, and reusable bundle identity. Update schema and validation logic so bad stimulus references fail clearly, and make the resolved stimulus snapshot discoverable from downstream metadata instead of requiring consumers to reconstruct it from scattered config fragments.

### Acceptance Criteria
- Config and manifest inputs can declare a canonical stimulus by family and name plus any supported parameter overrides, and those inputs resolve through the same library registry used by the generator code.
- Validation errors are clear when a manifest references an unknown family, an unknown preset, or invalid family-specific parameters.
- The resolved stimulus spec, contract version, and bundle identity or path are recorded in a discoverable form suitable for later replay, experiment audit, and result comparison.
- Existing Milestone 1 manifest validation continues to work through backward compatibility or a documented migration path that keeps the example manifest meaningful.
- Regression coverage exercises healthy manifest resolution, malformed stimulus references, and compatibility behavior using local fixture manifests only.

### Verification
- `make test`
- A focused schema or manifest-validation test that resolves fixture experiment manifests and asserts normalized stimulus metadata plus failure modes

### Notes
Assume the earlier Milestone 8A contract and generator tickets have landed. The key deliverable is reproducibility: a standard stimulus should be something a manifest can name, validate, and rediscover exactly. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8A-006 - Ship deterministic stimulus recording, replay, and offline preview tooling for reusable bundles
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: playback / serialization / developer tooling

### Problem
The milestone’s done-when clause explicitly says stimuli must be recordable and replayable, but the repo currently has no standard workflow that turns a resolved stimulus spec into a reusable local artifact. A developer could rerun the generator code manually, yet there is no deterministic output directory, no static preview artifact, no replay harness, and no guarantee that "the same stimulus" today will still mean the same thing when Milestone 8B or later experiment runs depend on it.

### Requested Change
Add a script-thin recording and replay workflow that consumes a canonical stimulus spec, writes a reusable local stimulus bundle, and generates an offline preview artifact. The workflow should serialize the metadata needed for exact reuse, persist either the canonical cached frame sequence or the documented hybrid representation chosen in `FW-M8A-001`, and provide a replay path that can drive later retinal or experiment code without recomputing semantics ad hoc. Output paths should be deterministic, and the preview should make it easy to inspect timing and spatial content for one or more representative frames.

### Acceptance Criteria
- A documented local command or script can build a reusable stimulus bundle from config or manifest input and replay it offline with no live external dependencies.
- The output location is deterministic for the resolved stimulus identity, making bundles easy to cache, diff, and reference from later pipeline steps.
- The bundle includes enough metadata to reproduce the stimulus exactly, including timing, normalized parameters, contract version, and whichever cached data the chosen representation model requires.
- A static preview artifact is generated in a review-friendly format such as Markdown plus images, HTML, or another lightweight offline format.
- At least one smoke-style automated test generates a fixture stimulus bundle twice and asserts deterministic metadata, replay behavior, and preview output paths.

### Verification
- `make test`
- A smoke-style fixture run that records and replays one or more canonical stimuli and asserts deterministic bundle contents plus preview outputs

### Notes
Assume `FW-M8A-001` through `FW-M8A-005` are already in place. Keep the workflow lightweight and local-first so later milestones can depend on cached stimulus assets without needing a heavier rendering stack. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8A-007 - Run a Milestone 8A integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 8A roadmap 2026-03-21
- Area: verification / review / release readiness

### Problem
Even if the contract, generator, manifest, and replay tickets land individually, the repo still needs one explicit integration pass that verifies Milestone 8A works as a coherent canonical stimulus system. Without a dedicated verification ticket, it is too easy to stop at isolated generator success while leaving behind contract drift, broken manifest discovery, preview gaps, weak determinism checks, or family-specific inconsistencies that will only surface once Milestone 8B and later simulator work start depending on these stimuli.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 8A implementation and publish a concise readiness report in-repo. This pass should exercise at least one representative example from every required Milestone 8A family, confirm that manifest and config entrypoints resolve through the canonical registry, validate deterministic record and replay behavior, and check that documentation matches the shipped commands and metadata. Treat this as an integration and audit ticket rather than a net-new feature ticket, and either close gaps directly or record them as explicit follow-on issues.

### Acceptance Criteria
- The full Milestone 8A workflow is executed end-to-end using the shipped commands and local fixture assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across the stimulus registry, family generators, manifest or config resolution, recording and replay bundles, and offline preview outputs.
- The readiness report summarizes which stimulus families were exercised, what determinism or compatibility checks passed, what remains risky or deferred, and whether Milestone 8A is ready to support Milestones 8B, 8C, and later experiment orchestration.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_8a_canonical_stimulus_library_tickets.md --ticket-id FW-M8A-007 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 8A tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the canonical stimulus library is integrated, reproducible, and ready for the rest of the visual input stack. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
