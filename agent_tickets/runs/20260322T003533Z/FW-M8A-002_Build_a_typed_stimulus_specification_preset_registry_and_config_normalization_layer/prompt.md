Work ticket FW-M8A-002: Build a typed stimulus specification, preset registry, and config normalization layer.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even with a bundle contract, the repo still has no stable way to ask for a standard stimulus from config. A caller would have to pass untyped dictionaries, duplicate defaults, and guess family-specific parameter names. That would make `stimulus_family` and `stimulus_name` little more than labels instead of a reproducible input contract, and it would make later experiment orchestration fragile whenever a family adds a new parameter or compatibility alias.

Requested Change:
Implement the library-owned stimulus specification layer that resolves config or manifest inputs into normalized, typed stimulus specs. The API should accept a family identifier, named preset, and optional overrides, then return a normalized spec with explicit defaults, units, duration, frame timing, spatial extent, and deterministic seed behavior. Keep the implementation YAML-friendly and manifest-friendly, reserve stable family identifiers for every Milestone 8A family, and preserve compatibility with the existing `moving_edge` naming used by the Milestone 1 example manifest.

Acceptance Criteria:
- There is one canonical API that resolves `stimulus_family`, `stimulus_name`, and parameter overrides into a normalized stimulus spec and registry entry.
- Family-specific parameter validation fails clearly for missing, misspelled, or out-of-range values instead of deferring errors until frame generation.
- Named presets and aliases are discoverable through library code and stable enough for manifests, config examples, and later UI tooling to reference directly.
- The resolved spec captures explicit defaults for timing, spatial extent, background level, polarity or contrast semantics, and deterministic seed handling.
- Regression coverage validates normalization, alias handling, parameter overrides, and clear failure modes using fixture configs only.

Verification:
- `make test`
- A focused unit test that resolves several fixture stimulus configs, including a Milestone 1 `moving_edge` compatibility case, and asserts normalized output plus validation errors

Notes:
Assume `FW-M8A-001` is already in place. The main goal is to make standard stimuli truly callable from config rather than merely selectable by a string label. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
