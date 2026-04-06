**Changed**

Added shared review-surface helpers in [review_surface_artifacts.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_surface_artifacts.py#L15) for three things: hook-driven packaged artifact lifting, explicit override merging, and packaged dashboard/showcase bundle-alignment validation.

Refactored the duplicated paths in [showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L165), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1065), and [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1331) so they no longer hand-maintain separate role-by-role packaged review-surface lifting blocks. Showcase and whole-brain now share the same explicit-override merge path, and whole-brain’s packaged dashboard/showcase loading and validation now reuse the centralized bundle-id checks. I also added regression coverage for mismatched packaged state bundle IDs in [tests/test_showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_showcase_session_planning.py#L693) and [tests/test_whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_whole_brain_context_planning.py#L397).

**Verified**

Ran `.venv/bin/python -m pytest tests/test_dashboard_session_planning.py tests/test_showcase_session_planning.py tests/test_whole_brain_context_planning.py` and it passed: `25 passed`.

Ran `make test` and it passed: `336 tests` total. The run printed an existing non-failing optional DB warning about `codex.data.connections_v2`, but the suite completed successfully.