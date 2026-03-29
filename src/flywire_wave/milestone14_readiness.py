from __future__ import annotations

import html
import importlib
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import REPO_ROOT, load_config
from .dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    APP_SHELL_INDEX_ARTIFACT_ID,
    CIRCUIT_PANE_ID,
    METADATA_JSON_KEY,
    MORPHOLOGY_PANE_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    SUPPORTED_PANE_IDS,
    TIME_SERIES_PANE_ID,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from .io_utils import ensure_dir, write_json
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)


MILESTONE14_READINESS_REPORT_VERSION = "milestone14_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_dashboard_session_contract",
    "tests.test_dashboard_session_planning",
    "tests.test_dashboard_app_shell",
    "tests.test_dashboard_scene_circuit",
    "tests.test_dashboard_morphology",
    "tests.test_dashboard_replay",
    "tests.test_dashboard_analysis",
    "tests.test_dashboard_exports",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone14-readiness",
        "scripts/30_milestone14_readiness.py",
        "scripts/29_dashboard_shell.py build",
        "scripts/29_dashboard_shell.py open --dashboard-session-metadata",
        "--no-browser",
        "milestone_14_readiness.md",
        "milestone_14_readiness.json",
    ),
    "docs/pipeline_notes.md": (
        "make milestone14-readiness",
        "scripts/30_milestone14_readiness.py",
        "scripts/29_dashboard_shell.py open --dashboard-session-metadata",
        "--no-browser",
        "milestone_14_readiness.md",
        "milestone_14_readiness.json",
    ),
}

DEFAULT_DASHBOARD_VERIFICATION = {
    "experiment_id": "milestone_1_demo_motion_patch",
    "baseline_arm_id": "baseline_p0_intact",
    "wave_arm_id": "surface_wave_intact",
    "preferred_seed": 11,
    "preferred_condition_ids": ["on_polarity", "preferred_direction"],
    "snapshot_overlay_id": PHASE_MAP_REFERENCE_OVERLAY_ID,
    "metrics_overlay_id": REVIEWER_FINDINGS_OVERLAY_ID,
    "snapshot_sample_index": 3,
    "metrics_sample_index": 2,
}

FOLLOW_ON_TICKETS = (
    {
        "ticket_id": "FW-M14-FOLLOW-001",
        "severity": "non_blocking",
        "title": "Add a browser-engine smoke that drives linked dashboard controls on packaged local sessions",
        "summary": (
            "FW-M14-008 now proves deterministic dashboard packaging, app-shell discovery, "
            "pane payload coherence, and export behavior from shipped local commands, but the "
            "verification still inspects the packaged HTML and JSON contract surface rather "
            "than exercising the JavaScript control wiring inside a real browser engine."
        ),
        "reproduction_notes": (
            "Run `make milestone14-readiness`, then inspect the generated app shell and "
            "bootstrap under the readiness fixture session bundle. The report proves the "
            "packaged control state is coherent and exportable, but it does not yet click "
            "the browser-rendered controls through a headless DOM harness."
        ),
    },
    {
        "ticket_id": "FW-M14-FOLLOW-002",
        "severity": "non_blocking",
        "title": "Promote the readiness fixture into a richer retinal-backed dashboard stress session",
        "summary": (
            "The shipped Milestone 14 readiness fixture is intentionally compact so the "
            "integration gate stays deterministic and fast. Milestone 16 showcase work should "
            "also exercise a denser circuit and a retinal-backed scene source so scene, circuit, "
            "morphology, replay, and analysis layouts are reviewed under a more presentation-like load."
        ),
        "reproduction_notes": (
            "Run `make milestone14-readiness`, then inspect "
            "`data/processed/milestone_14_verification/simulator_results/readiness/milestone_14/generated_fixture/` "
            "and the packaged dashboard session recorded in the report. The current fixture proves "
            "contract coherence on a compact stimulus-driven session with one shared readout and a small root set."
        ),
    },
)


def build_milestone14_readiness_paths(
    processed_simulator_results_dir: str | Path,
) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_14"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_14_readiness.md",
        "json_path": report_dir / "milestone_14_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
    }


def execute_milestone14_readiness_pass(
    *,
    config_path: str | Path,
    fixture_verification: Mapping[str, Any],
    python_executable: str,
    root_dir: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = Path(root_dir).resolve()
    cfg = load_config(config_path, project_root=repo_root)
    processed_simulator_results_dir = Path(
        cfg["paths"]["processed_simulator_results_dir"]
    ).resolve()
    readiness_paths = build_milestone14_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = readiness_paths["generated_fixture_dir"]
    shutil.rmtree(generated_fixture_dir, ignore_errors=True)
    ensure_dir(generated_fixture_dir)

    settings = _resolve_dashboard_verification_settings(
        cfg.get("dashboard_verification", {}),
    )
    fixture = _materialize_dashboard_readiness_fixture(
        repo_root=repo_root,
        generated_fixture_dir=generated_fixture_dir,
    )
    planning_audit = _audit_dashboard_planning(
        fixture=fixture,
        settings=settings,
    )
    workflow_audit = _audit_dashboard_workflow(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        fixture=fixture,
        settings=settings,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)

    workflow_coverage = {
        "fixture_dashboard_suite": str(fixture_verification.get("status", "")) == "pass",
        "dashboard_planning_contract": planning_audit["overall_status"] == "pass",
        "dashboard_build_and_discovery": workflow_audit["build_audit"]["overall_status"]
        == "pass",
        "pane_contract_compatibility": workflow_audit["pane_audit"]["overall_status"]
        == "pass",
        "export_workflow": workflow_audit["export_audit"]["overall_status"] == "pass",
        "documentation": documentation_audit["overall_status"] == "pass",
    }

    all_issues = (
        list(planning_audit["issues"])
        + list(workflow_audit["issues"])
        + list(documentation_audit["issues"])
    )
    blocking_issues = [
        issue for issue in all_issues if str(issue.get("severity")) == "blocking"
    ]
    review_issues = [
        issue for issue in all_issues if str(issue.get("severity")) == "review"
    ]
    fixture_status = str(fixture_verification.get("status", "skipped"))
    if fixture_status != "pass" or blocking_issues or not all(workflow_coverage.values()):
        readiness_status = READINESS_GATE_HOLD
    elif review_issues:
        readiness_status = "review"
    else:
        readiness_status = "ready"

    verification_command_sequence = _verification_command_sequence(
        summary_paths=readiness_paths,
        workflow_audit=workflow_audit,
    )
    summary = {
        "report_version": MILESTONE14_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "generated_fixture_manifest_path": str(Path(fixture["manifest_path"]).resolve()),
        "generated_fixture_config_path": str(Path(fixture["config_path"]).resolve()),
        "representative_experiment_id": str(settings["experiment_id"]),
        "documented_verification_command": "make milestone14-readiness",
        "explicit_verification_command": (
            "python scripts/30_milestone14_readiness.py "
            "--config config/milestone_14_verification.yaml"
        ),
        "verification_command_sequence": verification_command_sequence,
        "fixture_verification": dict(fixture_verification),
        "planning_audit": planning_audit,
        "workflow_audit": workflow_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": [
            "The Milestone 14 readiness pass proves deterministic local dashboard contract coherence on a compact packaged fixture. It is an engineering integration gate, not a biological validation claim.",
            "The packaged app shell and export surface are verified from shipped local commands plus packaged HTML and JSON artifacts. A later browser-engine smoke should still exercise linked controls in a real DOM runtime.",
            "The readiness fixture keeps scene, circuit, morphology, replay, and analysis coherence fast and reviewable, but Milestone 16 showcase work should add a richer retinal-backed session before performance or narrative polish claims are made.",
        ],
        "follow_on_tickets": [dict(item) for item in FOLLOW_ON_TICKETS],
        "readiness_scope_note": (
            "The shipped readiness pass exercises dashboard-session planning, manifest- "
            "and experiment-driven bundle discovery, app-shell loading, scene and circuit "
            "context packaging, morphology rendering inputs, replay and time-series "
            "synchronization, analysis-pane payload discovery, and deterministic export "
            "workflow behavior from one coherent local fixture."
        ),
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_milestones": (
                ["milestone_15_experiment_orchestration", "milestone_16_showcase_mode"]
                if readiness_status != READINESS_GATE_HOLD
                else []
            ),
            "local_dashboard_gate": readiness_status,
            "scientific_review_boundary": (
                "Milestone 14 is engineering-ready when the packaged dashboard preserves "
                "shared-versus-wave-versus-validation boundaries, synchronized replay state, "
                "and deterministic export/discovery behavior. Scientific interpretation still "
                "starts from the underlying analysis and validation bundle evidence."
            ),
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone14_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _resolve_dashboard_verification_settings(
    raw_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    settings = dict(DEFAULT_DASHBOARD_VERIFICATION)
    if isinstance(raw_settings, Mapping):
        settings.update(raw_settings)
    settings["preferred_condition_ids"] = [
        str(item) for item in settings.get("preferred_condition_ids", [])
    ]
    settings["preferred_seed"] = int(settings["preferred_seed"])
    settings["snapshot_sample_index"] = int(settings["snapshot_sample_index"])
    settings["metrics_sample_index"] = int(settings["metrics_sample_index"])
    return settings


def _materialize_dashboard_readiness_fixture(
    *,
    repo_root: Path,
    generated_fixture_dir: Path,
) -> dict[str, Any]:
    builder = _load_dashboard_fixture_builder(repo_root)
    return builder(generated_fixture_dir)


def _load_dashboard_fixture_builder(repo_root: Path):
    tests_dir = repo_root / "tests"
    src_dir = repo_root / "src"
    for path in (tests_dir, src_dir):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    for module_name in (
        "tests.test_dashboard_session_planning",
        "test_dashboard_session_planning",
    ):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        builder = getattr(module, "_materialize_dashboard_fixture", None)
        if callable(builder):
            return builder
    raise ModuleNotFoundError(
        "Could not import the repo-owned dashboard verification fixture helper from tests."
    )


def _audit_dashboard_planning(
    *,
    fixture: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    from .dashboard_session_planning import resolve_dashboard_session_plan

    manifest_plan = resolve_dashboard_session_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
    )
    experiment_plan = resolve_dashboard_session_plan(
        experiment_id=str(settings["experiment_id"]),
        config_path=fixture["config_path"],
        baseline_arm_id=str(settings["baseline_arm_id"]),
        wave_arm_id=str(settings["wave_arm_id"]),
        preferred_seed=int(settings["preferred_seed"]),
        preferred_condition_ids=list(settings["preferred_condition_ids"]),
    )

    issues: list[dict[str, Any]] = []
    manifest_payload = dict(manifest_plan["dashboard_session_payload"])
    experiment_payload = dict(experiment_plan["dashboard_session_payload"])
    manifest_state = dict(manifest_plan["dashboard_session_state"])
    experiment_state = dict(experiment_plan["dashboard_session_state"])
    if (
        manifest_plan["dashboard_session"]["session_spec_hash"]
        != experiment_plan["dashboard_session"]["session_spec_hash"]
    ):
        issues.append(
            _issue(
                severity="blocking",
                area="planning",
                summary=(
                    "Manifest-driven and experiment-driven dashboard planning resolved "
                    "to different session_spec_hash values for the same local fixture."
                ),
                reproduction_notes=(
                    "Resolve the readiness fixture through both input modes and compare "
                    "the resulting dashboard session bundle IDs."
                ),
            )
        )
    if manifest_payload != experiment_payload:
        issues.append(
            _issue(
                severity="blocking",
                area="planning",
                summary=(
                    "Manifest-driven and experiment-driven planning still emit different "
                    "packaged dashboard payloads for the same selected bundle pair."
                ),
                reproduction_notes=(
                    "Compare `dashboard_session_payload.json` after resolving the same "
                    "fixture through `--manifest` and `--experiment-id`."
                ),
            )
        )
    if manifest_state != experiment_state:
        issues.append(
            _issue(
                severity="blocking",
                area="planning",
                summary=(
                    "Manifest-driven and experiment-driven planning emit different "
                    "serialized dashboard session state for the same fixture."
                ),
                reproduction_notes=(
                    "Compare `session_state.json` after resolving the same fixture "
                    "through both planning entrypoints."
                ),
            )
        )

    pane_ids = list(manifest_plan["pane_inputs"])
    if pane_ids != list(SUPPORTED_PANE_IDS):
        issues.append(
            _issue(
                severity="blocking",
                area="planning",
                summary="Dashboard planning does not emit the five Milestone 14 panes in contract order.",
                reproduction_notes="Inspect `pane_inputs` in the resolved dashboard session plan.",
            )
        )
    if (
        manifest_plan["pane_inputs"][TIME_SERIES_PANE_ID]["replay_model"][
            "shared_timebase_status"
        ]["availability"]
        != "available"
    ):
        issues.append(
            _issue(
                severity="blocking",
                area="planning",
                summary="Dashboard replay planning failed to preserve a shared baseline-versus-wave timebase on the readiness fixture.",
                reproduction_notes="Inspect `pane_inputs.time_series.replay_model.shared_timebase_status` in the readiness plan.",
            )
        )

    return {
        "overall_status": _overall_status_from_issues(issues),
        "issues": issues,
        "manifest_source_mode": str(manifest_plan["source_mode"]),
        "experiment_source_mode": str(experiment_plan["source_mode"]),
        "session_spec_hash": str(manifest_plan["dashboard_session"]["session_spec_hash"]),
        "pane_ids": pane_ids,
        "payloads_match": manifest_payload == experiment_payload,
        "states_match": manifest_state == experiment_state,
        "available_overlay_ids": list(manifest_plan["overlay_catalog"]["available_overlay_ids"]),
        "selected_bundle_pair": dict(manifest_plan["selected_bundle_pair"]),
    }


def _audit_dashboard_workflow(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    fixture: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    manifest_build = _run_command(
        name="manifest_build",
        command=[
            python_executable,
            "scripts/29_dashboard_shell.py",
            "build",
            "--config",
            str(Path(fixture["config_path"]).resolve()),
            "--manifest",
            str(Path(fixture["manifest_path"]).resolve()),
            "--schema",
            str(Path(fixture["schema_path"]).resolve()),
            "--design-lock",
            str(Path(fixture["design_lock_path"]).resolve()),
        ],
        cwd=repo_root,
        command_path=commands_dir / "manifest_build.json",
    )
    experiment_build = _run_command(
        name="experiment_build",
        command=[
            python_executable,
            "scripts/29_dashboard_shell.py",
            "build",
            "--config",
            str(Path(fixture["config_path"]).resolve()),
            "--experiment-id",
            str(settings["experiment_id"]),
            "--baseline-arm-id",
            str(settings["baseline_arm_id"]),
            "--wave-arm-id",
            str(settings["wave_arm_id"]),
            "--preferred-seed",
            str(int(settings["preferred_seed"])),
            *[
                value
                for condition_id in settings["preferred_condition_ids"]
                for value in ("--preferred-condition-id", str(condition_id))
            ],
        ],
        cwd=repo_root,
        command_path=commands_dir / "experiment_build.json",
    )
    if manifest_build["status"] != "pass" or experiment_build["status"] != "pass":
        issues.append(
            _issue(
                severity="blocking",
                area="workflow",
                summary="The shipped dashboard build command failed during the Milestone 14 readiness pass.",
                reproduction_notes=(
                    "Inspect the command records under the readiness report `commands/` directory."
                ),
            )
        )
        return {
            "overall_status": _overall_status_from_issues(issues),
            "issues": issues,
            "build_audit": {
                "overall_status": "blocking",
                "manifest_build": manifest_build,
                "experiment_build": experiment_build,
            },
            "pane_audit": {"overall_status": "blocking"},
            "export_audit": {"overall_status": "blocking"},
        }

    manifest_summary = _require_mapping(
        manifest_build.get("parsed_summary"),
        field_name="manifest_build.parsed_summary",
    )
    experiment_summary = _require_mapping(
        experiment_build.get("parsed_summary"),
        field_name="experiment_build.parsed_summary",
    )
    metadata_path = Path(manifest_summary["metadata_path"]).resolve()
    open_result = _run_command(
        name="open_no_browser",
        command=[
            python_executable,
            "scripts/29_dashboard_shell.py",
            "open",
            "--dashboard-session-metadata",
            str(metadata_path),
            "--no-browser",
        ],
        cwd=repo_root,
        command_path=commands_dir / "open_no_browser.json",
    )

    snapshot_first = _run_export_command(
        python_executable=python_executable,
        repo_root=repo_root,
        commands_dir=commands_dir,
        name="snapshot_export_first",
        metadata_path=metadata_path,
        export_target_id="pane_snapshot_png",
        pane_id=ANALYSIS_PANE_ID,
        active_overlay_id=str(settings["snapshot_overlay_id"]),
        sample_index=int(settings["snapshot_sample_index"]),
    )
    snapshot_second = _run_export_command(
        python_executable=python_executable,
        repo_root=repo_root,
        commands_dir=commands_dir,
        name="snapshot_export_second",
        metadata_path=metadata_path,
        export_target_id="pane_snapshot_png",
        pane_id=ANALYSIS_PANE_ID,
        active_overlay_id=str(settings["snapshot_overlay_id"]),
        sample_index=int(settings["snapshot_sample_index"]),
    )
    metrics_first = _run_export_command(
        python_executable=python_executable,
        repo_root=repo_root,
        commands_dir=commands_dir,
        name="metrics_export_first",
        metadata_path=metadata_path,
        export_target_id="metrics_json",
        pane_id=ANALYSIS_PANE_ID,
        active_overlay_id=str(settings["metrics_overlay_id"]),
        sample_index=int(settings["metrics_sample_index"]),
    )
    metrics_second = _run_export_command(
        python_executable=python_executable,
        repo_root=repo_root,
        commands_dir=commands_dir,
        name="metrics_export_second",
        metadata_path=metadata_path,
        export_target_id="metrics_json",
        pane_id=ANALYSIS_PANE_ID,
        active_overlay_id=str(settings["metrics_overlay_id"]),
        sample_index=int(settings["metrics_sample_index"]),
    )
    replay_first = _run_export_command(
        python_executable=python_executable,
        repo_root=repo_root,
        commands_dir=commands_dir,
        name="replay_export_first",
        metadata_path=metadata_path,
        export_target_id="replay_frame_sequence",
        pane_id=SCENE_PANE_ID,
    )
    replay_second = _run_export_command(
        python_executable=python_executable,
        repo_root=repo_root,
        commands_dir=commands_dir,
        name="replay_export_second",
        metadata_path=metadata_path,
        export_target_id="replay_frame_sequence",
        pane_id=SCENE_PANE_ID,
    )

    metadata = load_dashboard_session_metadata(metadata_path)
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    payload = json.loads(
        bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    session_state = json.loads(
        bundle_paths[SESSION_STATE_ARTIFACT_ID].read_text(encoding="utf-8")
    )
    html_text = bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID].read_text(encoding="utf-8")
    bootstrap = _extract_embedded_json(
        html_text,
        script_id="dashboard-app-bootstrap",
    )

    build_issues: list[dict[str, Any]] = []
    if str(manifest_summary["bundle_id"]) != str(experiment_summary["bundle_id"]):
        build_issues.append(
            _issue(
                severity="blocking",
                area="build",
                summary="Manifest and experiment CLI builds resolved to different dashboard bundle IDs.",
                reproduction_notes="Compare the `build` command JSON summaries in the readiness command log.",
            )
        )
    if str(manifest_summary["bootstrap_hash"]) != str(experiment_summary["bootstrap_hash"]):
        build_issues.append(
            _issue(
                severity="blocking",
                area="build",
                summary="Manifest and experiment CLI builds still write different app bootstrap content for the same session bundle.",
                reproduction_notes="Compare `bootstrap_hash` across the manifest-driven and experiment-driven `build` command outputs.",
            )
        )
    if open_result["status"] != "pass":
        build_issues.append(
            _issue(
                severity="blocking",
                area="build",
                summary="The packaged dashboard session could not be rediscovered through the shipped `open` command.",
                reproduction_notes="Run `scripts/29_dashboard_shell.py open --dashboard-session-metadata <path> --no-browser` on the readiness fixture session metadata.",
            )
        )
    else:
        open_summary = _require_mapping(
            open_result.get("parsed_summary"),
            field_name="open_no_browser.parsed_summary",
        )
        if str(open_summary["app_shell_path"]) != str(bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID]):
            build_issues.append(
                _issue(
                    severity="blocking",
                    area="build",
                    summary="The `open --no-browser` command resolved a different app shell path than the packaged session metadata.",
                    reproduction_notes="Compare the open-command JSON summary against `dashboard_session.json` artifact discovery.",
                )
            )

    scene_context = _require_mapping(
        payload["pane_inputs"][SCENE_PANE_ID],
        field_name="payload.pane_inputs.scene",
    )
    circuit_context = _require_mapping(
        payload["pane_inputs"][CIRCUIT_PANE_ID],
        field_name="payload.pane_inputs.circuit",
    )
    morphology_context = _require_mapping(
        payload["pane_inputs"][MORPHOLOGY_PANE_ID],
        field_name="payload.pane_inputs.morphology",
    )
    time_series_context = _require_mapping(
        payload["pane_inputs"][TIME_SERIES_PANE_ID],
        field_name="payload.pane_inputs.time_series",
    )
    analysis_context = _require_mapping(
        payload["pane_inputs"][ANALYSIS_PANE_ID],
        field_name="payload.pane_inputs.analysis",
    )
    replay_model = _require_mapping(
        time_series_context["replay_model"],
        field_name="payload.pane_inputs.time_series.replay_model",
    )
    replay_state = _require_mapping(
        session_state["replay_state"],
        field_name="session_state.replay_state",
    )

    pane_issues: list[dict[str, Any]] = []
    scene_frame_times = [float(item["time_ms"]) for item in scene_context["replay_frames"]]
    time_series_times = [
        float(item)
        for item in time_series_context["shared_trace_catalog"][0]["time_ms"]
    ]
    if str(scene_context["render_status"]) != "available" or not scene_frame_times:
        pane_issues.append(
            _issue(
                severity="blocking",
                area="scene",
                summary="The readiness fixture scene pane is not renderable from packaged local artifacts.",
                reproduction_notes="Inspect `pane_inputs.scene.render_status` and `pane_inputs.scene.replay_frames` in `dashboard_session_payload.json`.",
            )
        )
    if not circuit_context["root_catalog"] or not circuit_context["connectivity_context"]["edge_catalog"]:
        pane_issues.append(
            _issue(
                severity="blocking",
                area="circuit",
                summary="The readiness fixture circuit pane is missing selected roots or packaged connectivity context.",
                reproduction_notes="Inspect `pane_inputs.circuit.root_catalog` and `connectivity_context.edge_catalog` in `dashboard_session_payload.json`.",
            )
        )
    class_counts = dict(morphology_context["fidelity_summary"]["class_counts"])
    if "surface_neuron" not in class_counts or "skeleton_neuron" not in class_counts:
        pane_issues.append(
            _issue(
                severity="blocking",
                area="morphology",
                summary="The readiness fixture morphology pane no longer exposes both surface and skeleton render paths.",
                reproduction_notes="Inspect `pane_inputs.morphology.fidelity_summary.class_counts` in the packaged dashboard payload.",
            )
        )
    scene_covers_replay_range = bool(scene_frame_times) and bool(time_series_times) and (
        float(scene_frame_times[0]) <= float(time_series_times[0])
        and float(scene_frame_times[-1]) >= float(time_series_times[-1])
    )
    if not scene_covers_replay_range:
        pane_issues.append(
            _issue(
                severity="blocking",
                area="replay",
                summary="Scene replay coverage no longer spans the shared replay time range used by the dashboard time-series pane.",
                reproduction_notes="Compare `pane_inputs.scene.replay_frames[*].time_ms` against `pane_inputs.time_series.shared_trace_catalog[*].time_ms`.",
            )
        )
    if str(replay_state["comparison_mode"]) != "paired_baseline_vs_wave":
        pane_issues.append(
            _issue(
                severity="blocking",
                area="replay",
                summary="Serialized replay state is no longer bootstrapped into paired baseline-versus-wave comparison mode.",
                reproduction_notes="Inspect `session_state.json` and the app bootstrap replay-state payload.",
            )
        )
    if (
        not analysis_context["comparison_summary_exists"]
        or not analysis_context["comparison_matrices_exists"]
        or int(analysis_context["phase_map_reference_count"]) <= 0
        or int(analysis_context["validation"]["open_finding_count"]) <= 0
    ):
        pane_issues.append(
            _issue(
                severity="blocking",
                area="analysis",
                summary="The analysis pane no longer discovers the expected packaged analysis or validation evidence from the readiness fixture.",
                reproduction_notes="Inspect the packaged analysis-pane payload under `dashboard_session_payload.json`.",
            )
        )
    if [item["pane_id"] for item in bootstrap["pane_catalog"]] != list(SUPPORTED_PANE_IDS):
        pane_issues.append(
            _issue(
                severity="blocking",
                area="app_shell",
                summary="The packaged app bootstrap no longer advertises the five Milestone 14 panes in contract order.",
                reproduction_notes="Inspect the embedded `dashboard-app-bootstrap` JSON in the packaged `app/index.html`.",
            )
        )
    if (
        str(bootstrap["overlay_catalog"]["active_overlay_id"])
        != SHARED_READOUT_ACTIVITY_OVERLAY_ID
    ):
        pane_issues.append(
            _issue(
                severity="blocking",
                area="app_shell",
                summary="The packaged app shell no longer boots with the shared-comparison overlay as the default review surface.",
                reproduction_notes="Inspect `overlay_catalog.active_overlay_id` in the embedded bootstrap JSON.",
            )
        )

    export_issues: list[dict[str, Any]] = []
    for record in (
        snapshot_first,
        snapshot_second,
        metrics_first,
        metrics_second,
        replay_first,
        replay_second,
    ):
        if record["status"] != "pass":
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary=f"The dashboard export command `{record['name']}` failed during readiness verification.",
                    reproduction_notes=(
                        "Inspect the corresponding command record under the readiness `commands/` directory."
                    ),
                )
            )
    if not export_issues:
        snapshot_one = _require_mapping(
            snapshot_first["parsed_summary"],
            field_name="snapshot_export_first.parsed_summary",
        )
        snapshot_two = _require_mapping(
            snapshot_second["parsed_summary"],
            field_name="snapshot_export_second.parsed_summary",
        )
        metrics_one = _require_mapping(
            metrics_first["parsed_summary"],
            field_name="metrics_export_first.parsed_summary",
        )
        metrics_two = _require_mapping(
            metrics_second["parsed_summary"],
            field_name="metrics_export_second.parsed_summary",
        )
        replay_one = _require_mapping(
            replay_first["parsed_summary"],
            field_name="replay_export_first.parsed_summary",
        )
        replay_two = _require_mapping(
            replay_second["parsed_summary"],
            field_name="replay_export_second.parsed_summary",
        )
        if snapshot_one != snapshot_two:
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary="Repeated pane snapshot exports are no longer deterministic.",
                    reproduction_notes="Run the packaged pane snapshot export twice and compare the metadata JSON outputs.",
                )
            )
        if metrics_one != metrics_two:
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary="Repeated metrics exports are no longer deterministic.",
                    reproduction_notes="Run the packaged metrics export twice and compare the metadata JSON outputs.",
                )
            )
        if replay_one != replay_two:
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary="Repeated replay frame-sequence exports are no longer deterministic.",
                    reproduction_notes="Run the packaged replay export twice and compare the metadata JSON outputs.",
                )
            )
        snapshot_png = Path(snapshot_one["artifact_inventory"][0]["path"]).resolve()
        metrics_json_path = Path(metrics_one["artifact_inventory"][0]["path"]).resolve()
        replay_manifest_path = Path(replay_one["artifact_inventory"][0]["path"]).resolve()
        if not snapshot_png.exists() or snapshot_png.stat().st_size <= 0:
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary="The pane snapshot export did not write a non-empty PNG artifact.",
                    reproduction_notes="Inspect the readiness snapshot export output directory under the packaged session `exports/` tree.",
                )
            )
        metrics_payload = json.loads(metrics_json_path.read_text(encoding="utf-8"))
        replay_payload = json.loads(replay_manifest_path.read_text(encoding="utf-8"))
        if str(metrics_payload["summary"]["active_overlay_id"]) != str(settings["metrics_overlay_id"]):
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary="The metrics export no longer records the requested reviewer-facing overlay identity.",
                    reproduction_notes="Inspect the metrics export summary under the packaged session `exports/` tree.",
                )
            )
        if int(replay_payload["frame_count"]) <= 0:
            export_issues.append(
                _issue(
                    severity="blocking",
                    area="export",
                    summary="The replay frame-sequence export did not emit any frames.",
                    reproduction_notes="Inspect the replay export manifest and frames directory under the packaged session `exports/` tree.",
                )
            )

    issues.extend(build_issues)
    issues.extend(pane_issues)
    issues.extend(export_issues)
    return {
        "overall_status": _overall_status_from_issues(issues),
        "issues": issues,
        "build_audit": {
            "overall_status": _overall_status_from_issues(build_issues),
            "manifest_build": manifest_build,
            "experiment_build": experiment_build,
            "open_no_browser": open_result,
            "bundle_id": str(manifest_summary["bundle_id"]),
            "metadata_path": str(metadata_path),
            "app_shell_path": str(bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID]),
            "bootstrap_hash": str(manifest_summary["bootstrap_hash"]),
        },
        "pane_audit": {
            "overall_status": _overall_status_from_issues(pane_issues),
            "pane_ids": [item["pane_id"] for item in bootstrap["pane_catalog"]],
            "scene_render_status": str(scene_context["render_status"]),
            "scene_frame_count": len(scene_frame_times),
            "circuit_root_count": len(circuit_context["root_catalog"]),
            "circuit_edge_count": len(circuit_context["connectivity_context"]["edge_catalog"]),
            "morphology_class_counts": class_counts,
            "replay_sample_count": len(time_series_times),
            "scene_covers_replay_range": scene_covers_replay_range,
            "analysis_phase_map_reference_count": int(
                analysis_context["phase_map_reference_count"]
            ),
            "analysis_open_finding_count": int(
                analysis_context["validation"]["open_finding_count"]
            ),
        },
        "export_audit": {
            "overall_status": _overall_status_from_issues(export_issues),
            "snapshot_export": snapshot_first,
            "metrics_export": metrics_first,
            "replay_export": replay_first,
        },
    }


def _run_export_command(
    *,
    python_executable: str,
    repo_root: Path,
    commands_dir: Path,
    name: str,
    metadata_path: Path,
    export_target_id: str,
    pane_id: str,
    active_overlay_id: str | None = None,
    sample_index: int | None = None,
) -> dict[str, Any]:
    command = [
        python_executable,
        "scripts/29_dashboard_shell.py",
        "export",
        "--dashboard-session-metadata",
        str(metadata_path),
        "--export-target-id",
        str(export_target_id),
        "--pane-id",
        str(pane_id),
    ]
    if active_overlay_id is not None:
        command.extend(["--active-overlay-id", str(active_overlay_id)])
    if sample_index is not None:
        command.extend(["--sample-index", str(int(sample_index))])
    return _run_command(
        name=name,
        command=command,
        cwd=repo_root,
        command_path=commands_dir / f"{name}.json",
    )


def _run_command(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    command_path: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, Any] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    parsed_summary = _parse_json_from_command_output(result.stdout)
    if parsed_summary is not None:
        payload["parsed_summary"] = parsed_summary
    write_json(payload, command_path)
    return payload


def _parse_json_from_command_output(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    if start < 0:
        return None
    candidate = stripped[start:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    for relative_path, snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        text = (repo_root / relative_path).read_text(encoding="utf-8")
        absent = [snippet for snippet in snippets if snippet not in text]
        if absent:
            missing.append(
                _issue(
                    severity="blocking",
                    area="documentation",
                    summary=(
                        f"{relative_path} is missing documented Milestone 14 readiness snippets."
                    ),
                    reproduction_notes=(
                        f"Open `{relative_path}` and add the missing snippet(s): {absent!r}."
                    ),
                )
            )
    return {
        "overall_status": _overall_status_from_issues(missing),
        "issues": missing,
    }


def _verification_command_sequence(
    *,
    summary_paths: Mapping[str, Path],
    workflow_audit: Mapping[str, Any],
) -> list[str]:
    commands = [
        "make milestone14-readiness",
        "python scripts/30_milestone14_readiness.py --config config/milestone_14_verification.yaml",
    ]
    build_audit = _require_mapping(
        workflow_audit.get("build_audit", {}),
        field_name="workflow_audit.build_audit",
    )
    metadata_path = build_audit.get("metadata_path")
    if metadata_path:
        commands.extend(
            [
                (
                    "python scripts/29_dashboard_shell.py open "
                    f"--dashboard-session-metadata {metadata_path} --no-browser"
                ),
                (
                    "python scripts/29_dashboard_shell.py export "
                    f"--dashboard-session-metadata {metadata_path} "
                    "--export-target-id pane_snapshot_png --pane-id analysis "
                    f"--active-overlay-id {PHASE_MAP_REFERENCE_OVERLAY_ID} --sample-index 3"
                ),
                (
                    "python scripts/29_dashboard_shell.py export "
                    f"--dashboard-session-metadata {metadata_path} "
                    "--export-target-id metrics_json --pane-id analysis "
                    f"--active-overlay-id {REVIEWER_FINDINGS_OVERLAY_ID} --sample-index 2"
                ),
                (
                    "python scripts/29_dashboard_shell.py export "
                    f"--dashboard-session-metadata {metadata_path} "
                    "--export-target-id replay_frame_sequence --pane-id scene"
                ),
            ]
        )
    else:
        generated_fixture_dir = Path(summary_paths["generated_fixture_dir"]).resolve()
        commands.append(
            "python scripts/29_dashboard_shell.py build "
            f"--config {generated_fixture_dir / 'simulation_config.yaml'} "
            f"--manifest {generated_fixture_dir / 'fixture_manifest.yaml'} "
            "--schema schemas/milestone_1_experiment_manifest.schema.json "
            "--design-lock config/milestone_1_design_lock.yaml"
        )
    return commands


def _render_milestone14_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = _require_mapping(
        summary[FOLLOW_ON_READINESS_KEY],
        field_name="summary.follow_on_readiness",
    )
    planning_audit = _require_mapping(
        summary["planning_audit"],
        field_name="summary.planning_audit",
    )
    workflow_audit = _require_mapping(
        summary["workflow_audit"],
        field_name="summary.workflow_audit",
    )
    build_audit = _require_mapping(
        workflow_audit["build_audit"],
        field_name="summary.workflow_audit.build_audit",
    )
    pane_audit = _require_mapping(
        workflow_audit["pane_audit"],
        field_name="summary.workflow_audit.pane_audit",
    )
    export_audit = _require_mapping(
        workflow_audit["export_audit"],
        field_name="summary.workflow_audit.export_audit",
    )
    lines = [
        "# Milestone 14 Dashboard Readiness Report",
        "",
        "## Verdict",
        "",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Local dashboard gate: `{readiness['local_dashboard_gate']}`",
        f"- Ready for downstream work: `{', '.join(readiness.get('ready_for_milestones', []))}`",
        f"- Ready for follow-on work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Verification command: `{summary['documented_verification_command']}`",
        f"- Explicit command: `{summary['explicit_verification_command']}`",
        "",
        "## Verification Surface",
        "",
        f"- Focused fixture suite: `{summary['fixture_verification']['status']}`",
        f"- Representative experiment id: `{summary['representative_experiment_id']}`",
        f"- Generated fixture manifest: `{summary['generated_fixture_manifest_path']}`",
        f"- Generated fixture config: `{summary['generated_fixture_config_path']}`",
        f"- Dashboard session metadata: `{build_audit.get('metadata_path', '')}`",
        f"- Packaged app shell: `{build_audit.get('app_shell_path', '')}`",
        "",
        "## Contract Compatibility",
        "",
        f"- Planning audit: `{planning_audit['overall_status']}`",
        f"- Build/discovery audit: `{build_audit['overall_status']}`",
        f"- Pane audit: `{pane_audit['overall_status']}`",
        f"- Export audit: `{export_audit['overall_status']}`",
        f"- Pane IDs: `{pane_audit.get('pane_ids', [])}`",
        f"- Replay sample count: `{pane_audit.get('replay_sample_count', 0)}`",
        f"- Scene frame count: `{pane_audit.get('scene_frame_count', 0)}`",
        f"- Circuit root count: `{pane_audit.get('circuit_root_count', 0)}`",
        f"- Circuit edge count: `{pane_audit.get('circuit_edge_count', 0)}`",
        f"- Morphology class counts: `{pane_audit.get('morphology_class_counts', {})}`",
        f"- Scene covers replay range: `{pane_audit.get('scene_covers_replay_range', False)}`",
        f"- Analysis phase-map references: `{pane_audit.get('analysis_phase_map_reference_count', 0)}`",
        f"- Analysis open findings: `{pane_audit.get('analysis_open_finding_count', 0)}`",
        "",
        "## Workflow Coverage",
        "",
    ]
    for key, value in summary["workflow_coverage"].items():
        lines.append(f"- {key.replace('_', ' ')}: `{value}`")
    lines.extend(
        [
            "",
            "## Command Sequence",
            "",
        ]
    )
    for command in summary["verification_command_sequence"]:
        lines.append(f"- `{command}`")
    lines.extend(
        [
            "",
            "## Remaining Risks",
            "",
        ]
    )
    for risk in summary["remaining_risks"]:
        lines.append(f"- {risk}")
    lines.extend(
        [
            "",
            "## Deferred Follow-On Tickets",
            "",
        ]
    )
    for ticket in summary["follow_on_tickets"]:
        lines.append(
            f"- `{ticket['ticket_id']}`: {ticket['title']}\n"
            f"  Reproduction: {ticket['reproduction_notes']}"
        )
    return "\n".join(lines) + "\n"


def _extract_embedded_json(html_text: str, *, script_id: str) -> dict[str, Any]:
    match = re.search(
        rf'<script id="{re.escape(script_id)}" type="application/json">(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Could not find JSON script tag {script_id!r}.")
    return json.loads(html.unescape(match.group(1)))


def _overall_status_from_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    if any(str(item.get("severity")) == "blocking" for item in issues):
        return "blocking"
    if any(str(item.get("severity")) == "review" for item in issues):
        return "review"
    return "pass"


def _issue(
    *,
    severity: str,
    area: str,
    summary: str,
    reproduction_notes: str,
) -> dict[str, Any]:
    return {
        "severity": str(severity),
        "area": str(area),
        "summary": str(summary),
        "reproduction_notes": str(reproduction_notes),
    }


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(value)


__all__ = [
    "DEFAULT_FIXTURE_TEST_TARGETS",
    "MILESTONE14_READINESS_REPORT_VERSION",
    "build_milestone14_readiness_paths",
    "execute_milestone14_readiness_pass",
]
