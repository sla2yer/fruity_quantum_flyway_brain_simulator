Work ticket FW-M8A-005: Integrate canonical stimuli with experiment manifests, schema validation, and config discovery.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 8A roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 8A is not complete if the generators only exist as Python calls. The repo already uses config and manifest contracts to make experiments reproducible, and the example Milestone 1 manifest depends on `stimulus_family` plus `stimulus_name`. Right now there is no schema-backed way to declare canonical stimulus parameters, preserve resolved defaults, record a stimulus bundle reference, or validate that a manifest is actually pointing at a real callable stimulus configuration.

Requested Change:
Extend the experiment-manifest and config plumbing so canonical stimuli can be declared, validated, resolved, and rediscovered reproducibly. Preserve the simple top-level family and name fields where they are already in use, but add the normalized fields or compatibility shim needed to capture parameter overrides, deterministic seed behavior, contract version, and reusable bundle identity. Update schema and validation logic so bad stimulus references fail clearly, and make the resolved stimulus snapshot discoverable from downstream metadata instead of requiring consumers to reconstruct it from scattered config fragments.

Acceptance Criteria:
- Config and manifest inputs can declare a canonical stimulus by family and name plus any supported parameter overrides, and those inputs resolve through the same library registry used by the generator code.
- Validation errors are clear when a manifest references an unknown family, an unknown preset, or invalid family-specific parameters.
- The resolved stimulus spec, contract version, and bundle identity or path are recorded in a discoverable form suitable for later replay, experiment audit, and result comparison.
- Existing Milestone 1 manifest validation continues to work through backward compatibility or a documented migration path that keeps the example manifest meaningful.
- Regression coverage exercises healthy manifest resolution, malformed stimulus references, and compatibility behavior using local fixture manifests only.

Verification:
- `make test`
- A focused schema or manifest-validation test that resolves fixture experiment manifests and asserts normalized stimulus metadata plus failure modes

Notes:
Assume the earlier Milestone 8A contract and generator tickets have landed. The key deliverable is reproducibility: a standard stimulus should be something a manifest can name, validate, and rediscover exactly. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
