# Milestone 10 Follow-On Tickets

This file is intentionally structured so it remains readable in Markdown and parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M10-FOLLOW-002 - Tune one verification-grade, non-runaway surface-wave parameter bundle for the shipped local readiness fixture
- Status: open
- Priority: high
- Source: Milestone 10 readiness follow-on 2026-03-22
- Area: wave tuning / readiness / inspection

### Problem
Milestone 10 is now integrated and deterministic enough for downstream tooling, but the shipped local readiness sweep still fails every inspected `surface_wave` run on the deterministic two-neuron octahedron fixture. The current `reference`, `recovery_probe`, and `damping_wave_speed` sweep points all land in the inspection tool's `fail` bucket, with shared-output peaks on the order of roughly `1e68` through `1e83` and explicit review notes calling out peak-to-drive ratio inflation. That means the repo has a working wave pipeline, but it still lacks one trustworthy local reference bundle that reviewers can use as the first "this runs and does not obviously blow up" anchor for later Milestone 11 through 13 work.

### Requested Change
Perform a narrow, senior-level tuning pass on the shipped local Milestone 10 readiness fixture so the repo has at least one deterministic `surface_wave` parameter bundle that passes the existing inspection workflow without runaway amplification. Prefer adjusting declared parameter presets, readiness sweep configuration, and already-contract-approved stability guardrails before touching solver semantics. If a small solver-side guardrail change is truly required, keep it minimal, explain why parameter-only tuning was insufficient, and avoid reopening the `surface_wave_model.v1` contract, fixture topology, fairness assumptions, or input-binding semantics.

The intended outcome is not biological calibration and not a brand-new model family. The intended outcome is one verification-grade local reference point that:

- remains deterministic under the shipped readiness workflow
- produces finite, bounded coupled output on the current fixture
- clears the existing inspection checks at `pass`
- is documented well enough that later metrics and mixed-fidelity work can cite it as the local non-runaway reference configuration

If needed, split the shipped sweep into two roles:

- one verification-grade reference sweep or parameter set used by readiness gating
- one exploratory sweep that may still be useful for broader local review but is not treated as the minimum trusted reference

### Acceptance Criteria
- Running `make milestone10-readiness` on the shipped local fixture produces at least one deterministic `surface_wave` inspection run with overall status `pass`.
- The chosen pass-level run is driven by a checked-in parameter bundle or sweep point that is discoverable from repo-owned config and report artifacts rather than by ad hoc CLI overrides.
- The pass-level run no longer exhibits fail-level runaway behavior on the local fixture, including the current peak-to-drive inflation class called out by the readiness report.
- The implementation preserves deterministic bundle identity and deterministic inspection output for the chosen verification-grade run when repeated with the same seed and local artifacts.
- The readiness or inspection artifacts make it obvious which sweep point or parameter bundle is the verification-grade local reference and why it is preferred over the currently failing points.
- Documentation is updated to state that the local fixture remains a readiness and stability probe, not a biological claim, while also identifying the new pass-level reference path or command.
- Regression coverage or smoke automation is updated so the repo will fail loudly if the shipped verification-grade local reference point falls back into `warn` or `fail`.

### Verification
- `make test`
- `make milestone10-readiness`
- `python scripts/15_surface_wave_inspection.py --config config/milestone_10_verification.yaml --manifest manifests/examples/milestone_1_demo.yaml --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --arm-id surface_wave_intact --sweep-spec <shipped-verification-grade-sweep-spec>`
- Confirm from the generated inspection summary that at least one shipped verification-grade run is `pass` and remains deterministic across repeat execution

### Notes
This is intentionally smaller than a general "improve the wave model" ticket. Do not expand the local fixture itself here; richer anisotropy and branch-positive fixture work already belongs to `FW-M10-FOLLOW-001`. Keep the scope centered on turning the existing shipped readiness path into one that includes a stable, non-runaway local reference point. Before finishing this ticket, stage all changes made for it and create a non-amended commit that includes those changes.
