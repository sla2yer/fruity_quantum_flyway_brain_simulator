Work ticket FILECOH-001: Reduce `simulation_planning.py` to manifest orchestration by extracting analysis and asset/runtime planning.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: file_length_and_cohesion review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`simulation_planning.py` is still the single owner for manifest validation and normalization, readout-analysis planning, geometry/coupling asset readiness, surface-wave execution planning, and mixed-fidelity resolution. The module remains a central dependency for multiple planning and validation workflows, so routine changes to one seam still pull unrelated planning logic into the same file and review surface. The same cohesion problem shows up in tests: cross-suite fixture writers are still embedded in `test_simulation_planning.py` and imported by other test modules.

Requested Change:
Keep `resolve_manifest_simulation_plan` as the manifest-orchestration entrypoint, but move readout-analysis planning into a dedicated analysis-planning module, move geometry/coupling readiness and asset resolution into a dedicated asset-resolution module, and move surface-wave execution plus mixed-fidelity planning into a dedicated runtime-planning module. `resolve_manifest_readout_analysis_plan` and `resolve_manifest_mixed_fidelity_plan` should remain available as thin entrypoints or compatibility wrappers so downstream callers do not need a flag-day import change.

Acceptance Criteria:
`simulation_planning.py` is reduced to manifest-level orchestration, shared normalization, and thin public wrappers, while readout-analysis planning, circuit asset readiness, and surface-wave or mixed-fidelity planning live in narrower modules with explicit imports. The public planning entrypoints continue to return the same shapes expected by current callers. Shared fixture writers are moved out of `test_simulation_planning.py` into a dedicated test support module, and tests that currently import from another test file switch to that support module instead.

Verification:
`make test`
`make validate-manifest`
`make smoke`
