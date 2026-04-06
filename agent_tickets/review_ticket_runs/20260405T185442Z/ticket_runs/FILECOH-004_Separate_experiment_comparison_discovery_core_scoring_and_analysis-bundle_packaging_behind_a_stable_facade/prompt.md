Work ticket FILECOH-004: Separate experiment comparison discovery, core scoring, and analysis-bundle packaging behind a stable facade.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: file_length_and_cohesion review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`experiment_comparison_analysis.py` is still a monolithic public entrypoint that mixes three distinct responsibilities: simulator bundle discovery and plan-alignment validation, core experiment comparison scoring or null-test evaluation, and analysis-bundle packaging for UI or offline report artifacts. The file has also become an integration surface for other workflows, so the refactor now needs to preserve the current import facade instead of treating this as a purely internal move.

Requested Change:
Keep `experiment_comparison_analysis.py` as the stable public facade, but move its implementation seams into focused modules:
- a discovery module for bundle-set discovery, condition inference, and bundle-vs-plan validation
- a core comparison module for metric aggregation, null tests, task scoring, and output-summary assembly
- a packaging module for bundle metadata writing, export payload builders, visualization catalog assembly, UI payload assembly, and offline report handoff

`execute_experiment_comparison_workflow` should remain a thin coordinator over those modules, and existing public imports should continue to work for current callers.

Acceptance Criteria:
`discover_experiment_bundle_set` and its helper stack no longer live in the same implementation file as packaging or UI export builders.

`compute_experiment_comparison_summary` lives in a core analysis module that does not import report-generation or experiment-analysis bundle packaging helpers at module import time.

Packaging code consumes normalized summary or bundle inputs and owns export writing, UI payload generation, visualization catalog generation, and offline report packaging without re-owning comparison math.

`experiment_comparison_analysis.py` remains a compatibility facade exposing the current public entrypoints used by scripts, validation flows, dashboard planning, and suite execution.

Existing workflow behavior remains intact, including package generation, offline report regeneration from local artifacts, and accepting pre-resolved plans.

Verification:
`make test`
`make smoke`
