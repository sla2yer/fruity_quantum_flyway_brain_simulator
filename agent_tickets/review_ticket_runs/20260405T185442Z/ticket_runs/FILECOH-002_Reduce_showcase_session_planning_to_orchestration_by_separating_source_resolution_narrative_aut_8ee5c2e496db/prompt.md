Work ticket FILECOH-002: Reduce showcase session planning to orchestration by separating source resolution, narrative authoring, validation, and packaging.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: file_length_and_cohesion review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`showcase_session_planning.py` is still the main concentration point for four distinct concerns: resolving upstream showcase inputs, authoring narrative and preset content, validating rehearsal and dashboard-state patches, and assembling or writing package outputs. The repo now has a dedicated `showcase_session_contract.py`, so the remaining cohesion issue is specifically in the planner or orchestration layer rather than the contract-definition layer.

Requested Change:
Keep `showcase_session_contract.py` as the authority for contract and metadata helpers, and refactor `showcase_session_planning.py` so the top-level planner only composes separate collaborators for source and upstream artifact resolution, narrative or preset or step authoring, presentation-state and rehearsal/dashboard patch validation, and output or export-manifest assembly plus package writing. Move reusable showcase fixture materialization into a dedicated helper surface instead of importing it from peer test modules.

Acceptance Criteria:
A top-level showcase planner remains, but source resolution lives outside the narrative and packaging code path. Preset, narrative-context, and step generation no longer live in the same module as output-location, export-manifest, and package-writing helpers. Presentation-state, rehearsal-metadata, and dashboard-state patch validation live in a validation-focused module or helper surface instead of beside story authoring. Showcase tests no longer import `_materialize_dashboard_fixture` or `_materialize_packaged_suite_fixture` from peer test modules. The refactor does not move or duplicate contract metadata logic that is already owned by `showcase_session_contract.py`.

Verification:
`make test`
`make smoke`
