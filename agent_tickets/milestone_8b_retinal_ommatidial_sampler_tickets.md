# Milestone 8B Retinal / Ommatidial Sampler Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M8B-001 - Freeze a versioned retinal input bundle contract and ommatidial sampling design note
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: retinal contracts / manifests / docs

### Problem
Milestone 8A can define and replay canonical visual stimuli, but the repo still has no first-class contract for what the fly-facing retinal output actually is. There is no library-owned definition for retinal bundle paths, eye indexing, ommatidial ordering, coordinate frames, temporal sampling semantics, sampling-kernel metadata, or how later simulator and UI code should discover a reusable retinal recording. Without a versioned contract and a decisive design note, Milestones 8C, 9, 10, and 14 will bind themselves to ad hoc frame arrays and incompatible assumptions about what one "retinal frame" means.

### Requested Change
Define a first-class retinal input bundle contract in library code and document the design choices behind it. Centralize bundle naming, manifest metadata, and artifact discovery so later tooling can resolve sampled retinal outputs without hardcoded filenames, and add a markdown design note that compares the viable abstraction families before choosing the default. The design note should be decisive: choose the default among direct per-ommatidium irradiance, eye-image raster intermediates, and higher-level retinotopic feature maps; define the canonical world, body, head, and eye coordinate frames; specify temporal units and luminance or contrast conventions; and state which invariants later scene, simulator, and UI code must preserve.

### Acceptance Criteria
- Retinal bundle path construction and metadata serialization are centralized in library code rather than being reimplemented inside scripts.
- The chosen contract records an explicit retinal-contract version plus the metadata needed to reproduce a retinal recording deterministically, including source stimulus or scene identity, eye or lattice specification, frame timing, coordinate-frame conventions, and sampling-kernel settings.
- A dedicated markdown design note compares the supported retinal abstraction families, chooses the default, documents the coordinate and timing conventions, and names the invariants later Milestones 8C, 9, and 10 must preserve.
- `docs/pipeline_notes.md` is updated so the Milestone 8B contract sits alongside the existing subset, geometry, coupling, and operator contracts.
- Regression coverage verifies deterministic contract serialization, stable path generation, and bundle discovery for fixture retinal specs.

### Verification
- `make test`
- A focused unit test that builds fixture retinal metadata and asserts deterministic manifest or bundle serialization plus path discovery

### Notes
This ticket should land first. Keep the contract boring and explicit: one place to build retinal paths, one place to build metadata, and one in-repo design note that later tickets can cite instead of re-litigating the sampling model. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8B-002 - Build a canonical retinotopic lattice spec, eye-geometry config layer, and coordinate-transform API
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: retinal geometry / config / transforms

### Problem
The roadmap says Milestone 8B must map world-space stimuli into a fly retinotopic representation, but the repo has no canonical description of the visual sampling lattice itself. There is no typed eye-geometry or lattice spec, no stable ommatidial indexing, no left-right eye symmetry rules, and no shared API for converting among world, body, head, and eye coordinates. Without that foundation, different samplers will disagree about where detectors point, how frames should be oriented, and which detector index corresponds to which physical direction.

### Requested Change
Implement the library-owned retinal geometry layer that resolves config or manifest inputs into a normalized eye and lattice specification. The API should define the chosen lattice abstraction, canonical detector ordering, left and right eye handling, and the forward and inverse transforms among world, body, head, eye, and lattice-local coordinates. Keep the implementation explicit and testable, preserve enough metadata for scientific review, and make the config representation friendly to later scene playback and manifest entrypoints.

### Acceptance Criteria
- There is one canonical API that resolves retinal geometry config into a normalized eye or lattice specification with explicit defaults and stable indexing.
- Coordinate-transform helpers cover the world-to-body, body-to-head, head-to-eye, and eye-to-lattice conversions the sampler needs, and the documented transforms are test-covered for determinism and orientation sanity.
- The implementation records the chosen lattice resolution, detector directions or bins, per-eye conventions, and any symmetry or alias rules needed for manifest- and UI-facing discovery.
- Invalid or ambiguous geometry inputs fail clearly instead of producing silently rotated or mirrored retinal frames.
- Regression coverage validates normalization, indexing stability, representative transform compositions, and left-right consistency using local fixtures only.

### Verification
- `make test`
- A focused unit test that resolves fixture eye or lattice configs and asserts normalized output, stable detector ordering, and transform sanity checks

### Notes
Assume `FW-M8B-001` is already in place. The key deliverable is a single source of truth for retinal geometry and coordinate transforms so later sampling code does not embed its own incompatible assumptions. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8B-003 - Implement world-to-eye projection and deterministic ommatidial sampling kernels for fixture scenes and canonical stimuli
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: sampling / projection / frame synthesis

### Problem
Even with a lattice spec, Milestone 8B still lacks the actual physics-facing step that turns a world-space visual field into detector responses. The repo has no canonical projection code that evaluates a scene or stimulus from the fly’s viewpoint, applies the chosen sampling kernel or acceptance model, and produces stable per-ommatidium values. Without that, the same moving edge or scene could be interpreted differently by each downstream consumer, which would break the milestone’s requirement that the same scene convert into retinal input consistently.

### Requested Change
Implement the retinal projection and sampling layer that consumes the normalized eye or lattice spec plus a world-facing visual source and emits deterministic per-detector samples. Support the chosen default sampling model from `FW-M8B-001`, make field-of-view and out-of-bounds behavior explicit, and ensure the implementation can consume both fixture scenes and the canonical Milestone 8A stimulus representations without special-case code in each caller. Favor vectorized or cached evaluation paths so repeated frame generation does not require obviously wasteful per-detector Python loops.

### Acceptance Criteria
- A canonical API can evaluate a world-facing visual source into deterministic per-ommatidium samples using the supported eye or lattice spec.
- The sampling implementation records the realized projection or kernel settings, including any field-of-view clipping, background fill, acceptance-angle semantics, and per-eye handling required to reproduce the result.
- The same source stimulus or scene plus the same retinal config always produces the same sampled detector values and metadata.
- The implementation is structured for efficient repeated frame generation rather than ad hoc one-off projection calls.
- Regression coverage validates deterministic sampling behavior on small fixture scenes or analytic stimulus cases, including at least one boundary or out-of-field case.

### Verification
- `make test`
- A focused fixture-driven test that projects a small synthetic visual field or canonical stimulus into detector samples and asserts deterministic outputs plus boundary behavior

### Notes
Assume `FW-M8B-001` and `FW-M8B-002` have landed. Keep the math inspectable and deterministic; later simulator work will only be credible if reviewers can audit how world-space brightness becomes detector-level input. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8B-004 - Add temporal retinal frame generation and early-visual channel mapping on top of sampled ommatidia
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: retinal frames / early-visual units / simulator handoff

### Problem
Raw per-ommatidium samples are not yet a full simulator-facing retinal representation. Milestone 8B also needs a defensible answer to how sampled detector values become time-indexed retinotopic input frames or early visual units that later simulator code can consume. Right now there is no canonical temporal bundling layer, no stable indexing for frame stacks, no place to record normalization or adaptation choices, and no shared mapping from ommatidial samples into the early-unit abstraction Grant defines.

### Requested Change
Build the temporal retinal-frame generation layer that turns sampled ommatidial values into deterministic time-indexed retinal bundles using the abstraction chosen in `FW-M8B-001`. Implement the default mapping from detector samples into the chosen simulator-facing retinal representation, record the metadata needed to explain that mapping, and keep the representation extensible enough that later milestones can add richer early-visual channels without breaking the default contract. The resulting bundle should be something later baseline and wave simulators can load directly instead of reverse-engineering raw detector samples.

### Acceptance Criteria
- There is a canonical API that turns sampled ommatidial values into deterministic retinal frames or early-visual units with explicit temporal indexing and metadata.
- The resulting retinal bundle records the mapping from raw detector samples to the simulator-facing representation, including any normalization, aggregation, polarity, or channel semantics required to reproduce the output.
- Constant or repeated source input produces stable, reproducible retinal frame outputs rather than subtly drifting or shape-changing bundle structure.
- The bundle is discoverable through the contract and loadable through library helpers rather than relying on implicit script-local array conventions.
- Regression coverage validates temporal bundling, mapping semantics, and representative steady-state or motion-onset cases using local fixtures only.

### Verification
- `make test`
- A focused unit or integration-style test that builds a small sampled detector sequence and asserts deterministic retinal-frame serialization plus early-unit mapping behavior

### Notes
Assume `FW-M8B-001` through `FW-M8B-003` are already in place. The main deliverable is a stable simulator handoff: later code should be able to load "retinal input" as a named contract, not reconstruct it from scattered detector arrays. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8B-005 - Integrate the retinal sampler with canonical stimulus playback and scene-generator entrypoints
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: playback / scene integration / pipeline wiring

### Problem
Milestone 8B is not complete if the sampler only works as an isolated Python call. The roadmap explicitly says the same scene should be convertible into retinal input frames consistently, and Milestone 8C will expect a clean handoff into scene playback. Right now there is no script-thin entrypoint that loads a canonical Milestone 8A stimulus bundle or a Milestone 8C scene description, applies the retinal config, and writes a reusable retinal bundle in a deterministic place.

### Requested Change
Add the pipeline and playback integration layer that drives the retinal sampler from canonical visual sources. The implementation should accept a canonical stimulus or scene entrypoint, resolve the required camera or fly pose metadata, invoke the retinal sampling and bundling APIs, and write a reusable retinal bundle whose identity is stable for the same source plus retinal configuration. Keep the workflow local-first and deterministic so later experiment manifests and simulator runs can depend on cached retinal assets instead of replaying world semantics ad hoc.

### Acceptance Criteria
- A documented local command or script can build a retinal bundle from a canonical stimulus or scene input using only local repo artifacts.
- The output location is deterministic for the resolved source visual input plus retinal configuration, making retinal bundles easy to cache, diff, and reference from later pipeline steps.
- The integration path works through library-owned resolution and sampling APIs rather than reimplementing config parsing or projection logic inside scripts.
- The resulting metadata records the upstream source bundle or scene identity so retinal assets remain traceable back to the world-space input that generated them.
- Regression coverage exercises at least one fixture stimulus path and one fixture scene-like path, asserting deterministic bundle identity and replay behavior.

### Verification
- `make test`
- A smoke-style fixture run that records retinal bundles from representative canonical stimulus or scene inputs and asserts deterministic output paths plus metadata lineage

### Notes
Assume the earlier Milestone 8B tickets have landed and that Milestone 8A provides a canonical stimulus entrypoint. Design the public workflow so Milestone 8C can plug into it cleanly rather than inventing a second retinal-sampling path. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8B-006 - Ship offline retinal preview and QA tooling for world-view versus fly-view inspection
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: visualization / QA / developer tooling

### Problem
The milestone’s done-when clause explicitly says you should be able to visualize both the world scene and the sampled fly-view representation, but the repo currently has no standard offline inspection workflow for that. A developer could dump arrays manually, yet there is no deterministic report that shows the source view, lattice or detector coverage, the sampled retinal representation, timing context, or whether the sampler is behaving plausibly enough for later simulator and UI work.

### Requested Change
Add an offline retinal preview and QA workflow that consumes a source stimulus or scene plus a retinal bundle and emits a review-friendly report. The workflow should render the world-facing input alongside the fly-view or sampled representation, make the detector layout or sampling lattice inspectable, summarize key metadata such as field of view and timing, and surface compact pass, warn, or fail checks for obvious problems such as missing coverage, inconsistent frame counts, or invalid detector values. The goal is not to build the final UI; it is to make Milestone 8B outputs inspectable and auditable before deeper simulator work begins.

### Acceptance Criteria
- A documented local command or script can generate a retinal inspection report for one source input and retinal bundle using only local cached artifacts.
- The report includes at least a world-view preview, a fly-view or sampled retinal representation, detector or lattice layout context, timing or frame summary, and QA flags.
- Output paths are deterministic so reports can be attached to run logs or compared across runs.
- At least one smoke-style automated test generates the report from fixture assets and asserts the expected summary fields and output files.
- Docs explain how the report should be used to review Milestone 8B outputs and what a reviewer should look for when retinal coverage or sampling quality fails.

### Verification
- `make test`
- A smoke-style fixture run that generates a retinal inspection report and asserts summary fields plus deterministic output paths

### Notes
Assume the earlier Milestone 8B tickets have already landed. Favor lightweight offline artifacts such as Markdown plus images, HTML, or another review-friendly format that does not require interactive infrastructure to be useful. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.

## FW-M8B-007 - Run a Milestone 8B integration verification pass and publish a readiness report
- Status: open
- Priority: high
- Source: Milestone 8B roadmap 2026-03-21
- Area: verification / review / release readiness

### Problem
Even if the Milestone 8B build tickets land individually, the repo still needs one explicit integration pass that verifies the visual-input pieces work together as a coherent world-to-retina pipeline. Without a dedicated verification ticket, it is too easy to stop at isolated sampler success while leaving behind contract drift, transform mismatches, preview gaps, weak determinism checks, or inconsistencies between canonical stimuli, scene playback, retinal bundle generation, and the documentation later simulator work will rely on.

### Requested Change
Perform a senior-level verification pass over the completed Milestone 8B implementation and publish a concise readiness report in-repo. This pass should exercise the full local workflow on fixture assets and at least one representative canonical visual source, confirm that documentation matches shipped behavior, identify any mathematical or scientific risks that remain open, and either close gaps directly or record them as explicit follow-on issues. Treat this as an integration and audit ticket rather than a net-new feature ticket.

### Acceptance Criteria
- The full Milestone 8B workflow is executed end-to-end using the shipped commands and local assets, with results captured in a deterministic report location.
- The verification pass checks contract compatibility across retinal bundle discovery, eye or lattice configuration, coordinate transforms, projection or sampling behavior, temporal bundling, playback integration, and offline inspection tooling.
- The readiness report summarizes what was verified, what remains risky or deferred, and whether Milestone 8B is ready to support downstream scene-generation and simulator milestones.
- Any defects or documentation mismatches found during the pass are either fixed in the same ticket or recorded as explicit follow-on tickets with clear reproduction notes.
- Regression coverage or smoke automation is updated where gaps are discovered so the same integration failures are less likely to recur silently.

### Verification
- `make test`
- `python3 scripts/run_agent_tickets.py --tickets-file agent_tickets/milestone_8b_retinal_ommatidial_sampler_tickets.md --ticket-id FW-M8B-007 --dry-run --runner true`
- A documented end-to-end local verification command or short command sequence added by the implementation

### Notes
This ticket should run after the earlier Milestone 8B tickets are complete. The main deliverable is confidence: one place where a reviewer can see that the world-to-retina pipeline is integrated, documented, and ready for downstream simulator work. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
