Work ticket FW-M14-004: Implement the scene pane and circuit pane with synchronized subset, connectivity, and scene-context inspection.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 14 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 14 explicitly says the dashboard should show what the fly sees and how the active subset sits in connectivity context, yet the repo currently exposes those ideas only through upstream bundles and separate reports. There is no unified pane that can replay the relevant scene or retinal view in sync with simulator time, and there is no linked circuit pane that lets a reviewer inspect the active subset, its key connectivity neighborhood, and neuron metadata while staying anchored to the same experiment story. Without these panes, the dashboard will fail at the most basic narrative requirement: a reviewer still will not understand what input drove the run or which circuit elements are being highlighted.

Requested Change:
Implement the Milestone 14 scene pane and circuit pane on top of the packaged dashboard-session inputs. The scene pane should present the canonical scene or fly-view representation that matches the selected dashboard session and time cursor, while the circuit pane should present the active root subset together with the most relevant connectivity context, neuron metadata, and selection affordances needed to drive the rest of the dashboard. Keep the two panes synchronized with the global selection and replay state, and make sure they consume the existing stimulus, retinal, selection, and coupling-related contracts rather than introducing a competing data model.

Acceptance Criteria:
- The scene pane renders a synchronized view of the selected input context for the current session and time cursor using packaged local artifacts rather than ad hoc screenshots.
- The circuit pane exposes the active subset and connectivity context in a form that supports clicking or otherwise selecting neurons and immediately updating the rest of the dashboard state.
- Selection and hover behavior in the scene or circuit pane propagates through the shared dashboard state so later morphology, trace, and analysis panes can respond consistently.
- Circuit metadata shown in the pane remains grounded in the existing selection, registry, and coupling contracts rather than inventing a separate UI-only naming scheme.
- The implementation includes deterministic fixture coverage for scene-frame discovery, circuit-context normalization, linked-selection payloads, and clear handling of cases where certain context layers are unavailable.
- A companion rationale note is added at `docs/ui_dashboard_notes/FW-M14-004_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused integration-style test that builds a fixture dashboard session with scene and circuit inputs and asserts deterministic pane payloads plus linked neuron-selection behavior

Notes:
Assume `FW-M14-001` through `FW-M14-003` and the Milestone 8A, 8B, and 7 bundle contracts are already in place. Favor a presentation that helps a reviewer orient quickly, even if the first circuit pane uses a disciplined hybrid of graph, table, and metadata cards rather than a maximal graph-visualization feature set. Do not attempt to create a git commit as part of this ticket.
