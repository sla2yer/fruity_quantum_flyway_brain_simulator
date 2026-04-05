# Overengineering And Abstraction Load Review Prompt

You are performing a focused code review of the FlyWire Wave Pipeline repository. Stay in review mode. Do not edit code.

## Repo Context

This repo is a concrete single-repo pipeline plus offline local review surfaces, not a generalized platform. It builds wave-ready assets from FlyWire/Codex inputs, then runs manifest-driven local simulation, analysis, and packaging workflows. The codebase is beyond a toy prototype, but its real extension points are still limited: config path overrides, optional Codex CSV inputs, selection presets, two executable model modes (`baseline` and `surface_wave`), and CLI-runner choice for the ticket tooling.

Use that context to separate necessary domain complexity from optional engineering ceremony. Be skeptical of abstractions that speculate about future backends, plugin ecosystems, or generalized orchestration layers that the repo does not currently need.

## Objective

Find senior-level issues where the code carries unnecessary abstraction, indirection, configurability, or architectural ceremony that is not paying for itself in this repository as it exists today.

## Focus

- Abstractions introduced before there is a real second use case in the current repo, especially around the main preprocessing path in `src/flywire_wave/config.py`, `src/flywire_wave/registry.py`, `src/flywire_wave/selection.py`, `src/flywire_wave/mesh_pipeline.py`, and the matching `scripts/00_verify_access.py` through `scripts/03_build_wave_assets.py`.
- Wrapper layers that add hops without clarifying ownership on the manifest-driven execution path, especially in `src/flywire_wave/manifests.py`, `src/flywire_wave/simulation_planning.py`, `src/flywire_wave/simulator_execution.py`, `src/flywire_wave/experiment_comparison_analysis.py`, and nearby `*_contract.py` or `*_planning.py` modules.
- Generalization that makes the common local flow harder to understand in milestone/readiness and packaging surfaces such as `milestone*_readiness.py`, `dashboard_*`, `showcase_*`, and `whole_brain_context_*`.
- Factories, registries, plugin seams, or config surfaces that exceed the repo’s actual needs today. Real active extension points are limited; abstractions beyond them need strong justification.
- Architecture that hides straightforward behavior behind too many hops in the review-ticket pipeline, especially `src/flywire_wave/review_prompt_tickets.py`, `src/flywire_wave/agent_tickets.py`, and `scripts/run_review_prompt_tickets.py`.
- Cases where a smaller, flatter design would make the happy path easier for future maintainers without removing real capability.

## Exclude

- Necessary complexity caused by FlyWire/Codex normalization, optional source-file handling, provenance/materialization metadata, subset selection rules, synapse mapping, mesh sanitization, sparse operator assembly, or simulation math.
- Manifest/schema/design-lock validation and explicit artifact-contract metadata when they are actively protecting determinism, file compatibility, or offline reproducibility.
- Thin CLI wrappers in `scripts/` that simply expose one library entry point. Only flag them when wrapper-on-wrapper layering creates real indirection.
- Complexity that exists because the repo is intentionally file-backed and offline-first once artifacts are built.
- Issues that are mainly about performance, testing, or file size.
- Superficial complaints about modules named `*_registry`, `*_contract`, `*_planning`, or `*_readiness`. Do not assume the name itself is evidence of overengineering.

## Ignore By Default

- Generated or cached outputs in `data/interim/`, `data/processed/`, `agent_tickets/review_runs/`, `agent_tickets/runs/`, `.venv/`, `.pytest_cache/`, `src/flywire_wave.egg-info/`, and temporary `tmp_*` directories.
- Vendored upstream code in `flywire_codex/`.
- Raw snapshot contents in `data/raw/codex/` unless a ticket depends on how code handles those file shapes.

## Review Process

1. Trace the real happy paths first: `make registry -> make select -> make meshes -> make assets`, `make simulate -> make compare-analysis`, and `make review-tickets`.
2. Ask whether each abstraction reduces current change cost for one of those flows or merely anticipates more backends, modes, packages, or users than the repo currently has.
3. Prefer tickets where removal, flattening, narrowing, or inlining would make the code easier to follow now, not just in theory.
4. Avoid “make it simpler” tickets unless you can point to the exact abstraction tax being paid now: extra hops, duplicated indirection, unused variability, or needless ceremony.
5. Treat documented contract boundaries and deterministic bundle metadata as justified unless there is still a redundant layer on top of them.

## Ticketing Rules

- Create one ticket per issue.
- Use stable ticket IDs with an aspect-specific prefix, for example `OVR-001`.
- Explain why the abstraction is unnecessary for the repo in its current state: a concrete pipeline with local deterministic verification, not a multi-backend framework.
- Cite concrete evidence with file paths and 1-based line references when possible, for example `src/flywire_wave/module.py:42`.
- Recommend the smallest simplification that would materially improve clarity.
- In `Verification`, prefer documented local commands when relevant: `make test`, `make validate-manifest`, and `make smoke`. For simulator or surface-wave paths, `make milestone9-readiness` or `make milestone10-readiness` are appropriate when relevant.
- Avoid defaulting to token/network-dependent checks such as `make verify`, `make meshes`, or `make all` unless the ticket is specifically about those FlyWire-backed paths and the verification truly requires them.
- If no strong issues are present, say no tickets are recommended.

## Output Format

Return only markdown. No code fences.

Use this structure:

# Overengineering And Abstraction Load Review Tickets

## <ticket-id> - <title>
- Status: open
- Priority: high|medium|low
- Source: overengineering_and_abstraction_load review
- Area: <module / subsystem>

### Problem
<what abstraction or indirection is unnecessary>

### Evidence
<specific files, lines, and why the abstraction tax is real>

### Requested Change
<what should be flattened, narrowed, or removed>

### Acceptance Criteria
<observable completion criteria>

### Verification
<tests or checks that should still pass after simplification>
