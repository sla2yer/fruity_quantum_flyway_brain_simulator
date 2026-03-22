Work ticket FW-M8B-002: Build a canonical retinotopic lattice spec, eye-geometry config layer, and coordinate-transform API.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8B roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The roadmap says Milestone 8B must map world-space stimuli into a fly retinotopic representation, but the repo has no canonical description of the visual sampling lattice itself. There is no typed eye-geometry or lattice spec, no stable ommatidial indexing, no left-right eye symmetry rules, and no shared API for converting among world, body, head, and eye coordinates. Without that foundation, different samplers will disagree about where detectors point, how frames should be oriented, and which detector index corresponds to which physical direction.

Requested Change:
Implement the library-owned retinal geometry layer that resolves config or manifest inputs into a normalized eye and lattice specification. The API should define the chosen lattice abstraction, canonical detector ordering, left and right eye handling, and the forward and inverse transforms among world, body, head, eye, and lattice-local coordinates. Keep the implementation explicit and testable, preserve enough metadata for scientific review, and make the config representation friendly to later scene playback and manifest entrypoints.

Acceptance Criteria:
- There is one canonical API that resolves retinal geometry config into a normalized eye or lattice specification with explicit defaults and stable indexing.
- Coordinate-transform helpers cover the world-to-body, body-to-head, head-to-eye, and eye-to-lattice conversions the sampler needs, and the documented transforms are test-covered for determinism and orientation sanity.
- The implementation records the chosen lattice resolution, detector directions or bins, per-eye conventions, and any symmetry or alias rules needed for manifest- and UI-facing discovery.
- Invalid or ambiguous geometry inputs fail clearly instead of producing silently rotated or mirrored retinal frames.
- Regression coverage validates normalization, indexing stability, representative transform compositions, and left-right consistency using local fixtures only.

Verification:
- `make test`
- A focused unit test that resolves fixture eye or lattice configs and asserts normalized output, stable detector ordering, and transform sanity checks

Notes:
Assume `FW-M8B-001` is already in place. The key deliverable is a single source of truth for retinal geometry and coordinate transforms so later sampling code does not embed its own incompatible assumptions. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
