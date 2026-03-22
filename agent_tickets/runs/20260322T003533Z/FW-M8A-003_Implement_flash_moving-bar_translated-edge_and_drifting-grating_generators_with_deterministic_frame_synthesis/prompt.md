Work ticket FW-M8A-003: Implement flash, moving-bar, translated-edge, and drifting-grating generators with deterministic frame synthesis.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The roadmap explicitly calls for flashes, moving bars, drifting gratings, and translated edge patterns, yet the repo has no canonical generator implementation for any of them. The existing Milestone 1 manifest names a moving-edge stimulus, but there is no shared generation layer that defines how onset timing, polarity, aperture, speed, spatial frequency, contrast, or phase should map into actual frames. Without this, every downstream consumer will end up reinterpreting the same stimulus differently.

Requested Change:
Implement the first wave of canonical lab-stimulus generators using the normalized spec and contract established in `FW-M8A-001` and `FW-M8A-002`. Add generator implementations for flashes, moving bars, translated edge patterns, and drifting gratings, along with the family-specific metadata needed to replay or inspect them later. Make the rendering semantics explicit for background intensity, polarity, onset and offset timing, direction, velocity, aperture or mask handling, grating phase, spatial frequency, contrast, and edge sharpness. Preserve a stable compatibility path for the current `moving_edge` naming.

Acceptance Criteria:
- Flashes, moving bars, translated edge patterns, and drifting gratings can each be instantiated through the canonical registry and sampled into deterministic frame outputs or equivalent replayable field evaluators.
- The implemented generators record the family-specific metadata needed to explain how each stimulus was rendered, including direction, motion speed, polarity, contrast, aperture, and phase-related fields where applicable.
- Frame generation obeys the documented timing and spatial conventions from the design note and keeps intensity or contrast values within the declared bounds.
- Existing `moving_edge` references continue to work through a compatibility alias or a documented migration shim that keeps current Milestone 1 assets valid.
- Regression coverage exercises one or more fixture examples per family and asserts deterministic output, frame-shape invariants, timing semantics, and compatibility behavior.

Verification:
- `make test`
- A fixture-driven test suite that renders one or more examples for each implemented family and asserts metadata plus deterministic frame or sample outputs

Notes:
Land this before the more complex radial and rotational motion families. These generators are the likely first vertical-slice stimuli, so keep them inspectable and well documented rather than overly clever. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
