Work ticket FW-M9-002: Build manifest-driven simulation plans, typed baseline config normalization, and run discovery helpers.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The manifest already declares `model_mode`, `baseline_family`, topology conditions, seeds, stimuli, and must-show outputs, but the repo still has no runtime layer that turns those fields into an executable baseline simulation plan. There is no canonical API that resolves a manifest arm into normalized timing, asset references, baseline parameters, selected roots, output locations, or reproducible run IDs. Without that layer, every runner will re-parse manifests differently and later `baseline` versus `surface_wave` comparisons will drift before the simulation even starts.

Requested Change:
Implement the library-owned simulation planning layer that resolves config and manifest inputs into normalized baseline run specs. The API should consume the existing experiment-manifest structure, validate that the required local assets and config are present, normalize baseline-family parameters and runtime defaults, and expose deterministic discovery helpers for per-arm runs. Keep the representation explicit and future-proof so the same planning surface can later hand the same manifest to the wave engine without changing the manifest schema again.

Acceptance Criteria:
- There is one canonical API that resolves a manifest plus local config into normalized baseline simulation plans with explicit defaults and stable arm ordering.
- The plan records the manifest-level stimulus or retinal input reference, selected circuit or subset identity, coupling sources, timing, seed handling, baseline-family parameters, and deterministic output locations needed to launch a run.
- `model_mode=baseline` arms fail clearly when required local prerequisites are missing, ambiguous, or incompatible, instead of silently guessing at fallback behavior.
- The planning layer is structured so later `surface_wave` runs can reuse the same manifest-resolution path and extend it rather than replace it.
- Regression coverage validates normalization, plan determinism, missing-prerequisite failures, and representative fixture-manifest resolution using only local artifacts.

Verification:
- `make test`
- A focused unit test that resolves a fixture manifest into baseline run plans and asserts normalized output, deterministic IDs, and clear error handling

Notes:
Assume `FW-M9-001` is already in place. Favor script-thin entrypoints and library-owned normalization logic so the same manifest does not acquire a second incompatible execution path later. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
