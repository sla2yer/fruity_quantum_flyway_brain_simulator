Work ticket FW-M9-005: Integrate canonical input streams and Milestone 7 coupling bundles into baseline simulation runs.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 9 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Even with a stepping engine and neuron models, Milestone 9 is still incomplete unless the baseline simulator can run the actual connectome-constrained circuit with the repo’s canonical inputs. Right now there is no baseline-side integration path that consumes the selected-root roster, local coupling bundles, topology condition, and canonical time-varying input stream and turns them into recurrent per-neuron updates. Without that integration, the baseline mode is only a toy dynamical system rather than the matched circuit control the roadmap calls for.

Requested Change:
Implement the input and connectivity integration layer that drives the baseline simulator from the repo’s canonical assets. The implementation should resolve the selected circuit, ingest the relevant Milestone 7 coupling bundles, apply the intact or shuffled topology condition from the manifest plan, and feed the simulator with the canonical time-varying input stream expected by the visual-input stack. Keep the integration deterministic, cache-friendly, and asset-contract-aware so the same circuit and same input can later be run through `baseline` and `surface_wave` modes without changing the data handoff surface.

Acceptance Criteria:
- A canonical API can construct one executable baseline circuit run from selected roots, coupling bundles, topology condition, and a canonical input stream using only local repo artifacts.
- Recurrent accumulation, coupling signs, aggregation, and any supported delay or integration-current semantics are applied through library-owned coupling or planning logic rather than reimplemented ad hoc inside the step loop.
- The same resolved circuit and input asset identity always produce the same baseline wiring and drive schedule for a given seed and config.
- Missing or inconsistent prerequisites fail clearly, including absent coupling assets, incompatible root rosters, or unusable input timing.
- Regression coverage validates deterministic circuit execution on small fixture circuits, including at least one intact-versus-shuffled or delay-sensitive case.

Verification:
- `make test`
- A focused integration-style test that runs a small fixture circuit with canonical input and coupling assets and asserts deterministic recurrent state updates

Notes:
Assume the earlier Milestone 9 tickets are already in place and that the relevant local input contracts from upstream milestones exist or have fixture stand-ins. The key deliverable is a matched-circuit control path, not a one-off current injection demo. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
