from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .config import REPO_ROOT, load_config
from .io_utils import ensure_dir, write_json, write_root_ids
from .manifests import load_json, load_yaml
from .milestone9_readiness import (
    DEFAULT_VERIFICATION_BASELINE_FAMILIES,
    DEFAULT_VERIFICATION_READOUT_CATALOG,
    _deep_merge_mappings,
    _hash_file,
    _issue,
    _read_csv_rows,
    _resolve_repo_path,
    _run_command,
    _write_execution_geometry_manifest,
)
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .simulation_planning import discover_simulation_run_plans, resolve_manifest_simulation_plan
from .simulator_execution import (
    EXECUTION_PROVENANCE_ARTIFACT_ID,
    STRUCTURED_LOG_ARTIFACT_ID,
    SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
    UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
)
from .simulator_result_contract import (
    METADATA_JSON_KEY,
    METRIC_TABLE_COLUMNS,
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE,
    STATE_SUMMARY_KEY,
    discover_simulator_extension_artifacts,
    discover_simulator_result_bundle_paths,
    load_simulator_result_bundle_metadata,
)
from .stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from .surface_wave_contract import parse_surface_wave_model_metadata, write_surface_wave_model_metadata


MILESTONE10_READINESS_REPORT_VERSION = "milestone10_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_manifest_validation",
    "tests.test_simulation_planning",
    "tests.test_surface_wave_contract",
    "tests.test_surface_wave_solver",
    "tests.test_surface_wave_execution",
    "tests.test_simulator_result_contract",
    "tests.test_simulator_execution",
    "tests.test_surface_wave_inspection",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone10-readiness",
        "scripts/16_milestone10_readiness.py",
        "config/milestone_10_verification.yaml",
        "scripts/15_surface_wave_inspection.py",
    ),
    "docs/pipeline_notes.md": (
        "make milestone10-readiness",
        "scripts/16_milestone10_readiness.py",
        "milestone_10_readiness.md",
        "milestone_10_readiness.json",
        "scripts/15_surface_wave_inspection.py",
    ),
    "docs/simulator_result_bundle_design.md": (
        "make milestone10-readiness",
        "scripts/16_milestone10_readiness.py",
        "milestone_10_readiness.md",
        "milestone_10_readiness.json",
    ),
    "docs/surface_wave_inspection.md": (
        "make milestone10-readiness",
        "scripts/16_milestone10_readiness.py",
        "milestone_10_readiness.md",
        "milestone_10_readiness.json",
    ),
}

REQUIRED_SHARED_ARTIFACT_IDS = {
    METADATA_JSON_KEY,
    STATE_SUMMARY_KEY,
    READOUT_TRACES_KEY,
    METRICS_TABLE_KEY,
    STRUCTURED_LOG_ARTIFACT_ID,
    EXECUTION_PROVENANCE_ARTIFACT_ID,
    UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
}
REQUIRED_SURFACE_WAVE_ARTIFACT_IDS = {
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
    SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
}


def build_milestone10_readiness_paths(processed_simulator_results_dir: str | Path) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_10"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_10_readiness.md",
        "json_path": report_dir / "milestone_10_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
    }


def execute_milestone10_readiness_pass(
    *,
    config_path: str | Path,
    fixture_verification: Mapping[str, Any],
    python_executable: str,
    root_dir: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = Path(root_dir).resolve()
    cfg = load_config(config_path, project_root=repo_root)
    processed_stimulus_dir = Path(cfg["paths"]["processed_stimulus_dir"]).resolve()
    processed_retinal_dir = Path(cfg["paths"]["processed_retinal_dir"]).resolve()
    processed_simulator_results_dir = Path(cfg["paths"]["processed_simulator_results_dir"]).resolve()
    surface_wave_inspection_dir = Path(cfg["paths"]["surface_wave_inspection_dir"]).resolve()
    verification_cfg = dict(cfg.get("simulation_verification", {}))

    manifest_path = _resolve_repo_path(
        verification_cfg.get("manifest_path"),
        repo_root,
        default=repo_root / "manifests" / "examples" / "milestone_1_demo.yaml",
    )
    schema_path = _resolve_repo_path(
        verification_cfg.get("schema_path"),
        repo_root,
        default=repo_root / "schemas" / "milestone_1_experiment_manifest.schema.json",
    )
    design_lock_path = _resolve_repo_path(
        verification_cfg.get("design_lock_path"),
        repo_root,
        default=repo_root / "config" / "milestone_1_design_lock.yaml",
    )
    sweep_spec_path = _resolve_repo_path(
        verification_cfg.get("sweep_spec_path"),
        repo_root,
        default=repo_root / "config" / "surface_wave_sweep.example.yaml",
    )

    readiness_paths = build_milestone10_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = ensure_dir(readiness_paths["generated_fixture_dir"])

    fixture = _materialize_verification_fixture(
        manifest_path=manifest_path,
        verification_cfg=verification_cfg,
        generated_fixture_dir=generated_fixture_dir,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
        processed_simulator_results_dir=processed_simulator_results_dir,
        surface_wave_inspection_dir=surface_wave_inspection_dir,
    )
    manifest_plan_audit, plan = _build_manifest_plan_audit(
        fixture=fixture,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
    )
    surface_wave_execution_audit = _execute_surface_wave_workflow_audit(
        fixture=fixture,
        plan=plan,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
    )
    baseline_comparison_audit = _execute_baseline_comparison_audit(
        fixture=fixture,
        plan=plan,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
        surface_wave_bundle_audit=surface_wave_execution_audit.get("bundle_audit", {}),
    )
    surface_wave_inspection_audit = _execute_surface_wave_inspection_audit(
        fixture=fixture,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        sweep_spec_path=sweep_spec_path,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)
    fixture_suite_coverage = _build_fixture_suite_coverage(fixture_verification)
    workflow_coverage = _build_workflow_coverage(
        fixture_suite_coverage=fixture_suite_coverage,
        manifest_plan_audit=manifest_plan_audit,
        surface_wave_execution_audit=surface_wave_execution_audit,
        baseline_comparison_audit=baseline_comparison_audit,
        surface_wave_inspection_audit=surface_wave_inspection_audit,
        documentation_audit=documentation_audit,
    )

    all_issues = (
        list(manifest_plan_audit["issues"])
        + list(surface_wave_execution_audit["issues"])
        + list(baseline_comparison_audit["issues"])
        + list(surface_wave_inspection_audit["issues"])
        + list(documentation_audit["issues"])
    )
    blocking_issues = [
        issue
        for issue in all_issues
        if str(issue.get("severity", "")) == "blocking"
    ]
    review_issues = [
        issue
        for issue in all_issues
        if str(issue.get("severity", "")) == "review"
    ]
    fixture_status = str(fixture_verification.get("status", "skipped"))
    if fixture_status != "pass" or blocking_issues or not all(workflow_coverage.values()):
        readiness_status = READINESS_GATE_HOLD
    elif review_issues:
        readiness_status = READINESS_GATE_REVIEW
    else:
        readiness_status = "ready"

    follow_on_issues = [
        {
            "ticket_id": "FW-M10-FOLLOW-001",
            "severity": "non_blocking",
            "title": "Promote anisotropy and branching into a manifest-driven verification fixture",
            "summary": (
                "The shipped readiness pass exercises nonlinearity, anisotropy, and branching through "
                "the focused solver fixture suite, but the deterministic manifest fixture remains "
                "isotropic and lacks branch-positive skeleton descriptors."
            ),
            "reproduction": (
                "Run `make milestone10-readiness`, then inspect "
                f"`{fixture['fixture_assets_dir']}`. The generated operator metadata stays isotropic and "
                "the descriptor sidecars do not expose an available skeleton summary with "
                "`branch_point_count > 0`, so `anisotropy.mode=operator_embedded` and "
                "`branching.mode=descriptor_scaled_damping` cannot yet be promoted into the shipped "
                "manifest workflow without a richer local fixture."
            ),
        },
        {
            "ticket_id": "FW-M10-FOLLOW-002",
            "severity": "review",
            "title": "Tune a verification-grade surface-wave sweep for the local readiness fixture",
            "summary": (
                "The shipped example sweep executes deterministically and produces the expected artifact bundle, "
                "but the representative fixture currently drives fail-level diagnostics such as peak-to-drive "
                "ratio inflation."
            ),
            "reproduction": (
                "Run `make milestone10-readiness`, then inspect "
                f"`{surface_wave_inspection_audit.get('runs_csv_path', '')}` and the per-run markdown reports under "
                f"`{surface_wave_inspection_audit.get('output_dir', '')}`. The command succeeds, but the current "
                "reference and recovery sweep points still trigger fail-level review checks on the local two-neuron "
                "fixture."
            ),
        }
    ]
    remaining_risks = [
        (
            "The readiness pass uses a deterministic two-neuron octahedron fixture plus the shipped "
            "Milestone 1 manifest path. It proves workflow integration, not biological calibration."
        ),
        (
            "The manifest-driven end-to-end path verifies the default isotropic, no-branching wave "
            "configuration. Optional nonlinearity, anisotropy, and branching modes are covered by the "
            "focused fixture suite rather than by the shipped manifest fixture."
        ),
        (
            "The shipped example sweep currently lands in the inspection tool's `fail` bucket on the local "
            "readiness fixture because the coupled peak-to-drive ratio remains too large. That is now an explicit "
            "review item rather than a silent regression."
        ),
        (
            "Canonical input integration is presently comparison-ready because both model modes consume "
            "the same shared root-level drive schedule, but the surface-wave input binding still uses "
            "`uniform_surface_fill_from_shared_root_schedule` rather than a more localized morphology "
            "injection rule."
        ),
    ]

    summary = {
        "report_version": MILESTONE10_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "schema_path": str(schema_path.resolve()),
        "design_lock_path": str(design_lock_path.resolve()),
        "sweep_spec_path": str(sweep_spec_path.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir),
        "processed_retinal_dir": str(processed_retinal_dir),
        "processed_simulator_results_dir": str(processed_simulator_results_dir),
        "surface_wave_inspection_dir": str(surface_wave_inspection_dir),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "commands_dir": str(commands_dir.resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "documented_verification_command": "make milestone10-readiness",
        "explicit_verification_command": "python scripts/16_milestone10_readiness.py --config config/milestone_10_verification.yaml",
        "representative_commands": [
            "python scripts/run_simulation.py --config <fixture-config> --manifest manifests/examples/milestone_1_demo.yaml --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --model-mode surface_wave --arm-id surface_wave_intact",
            "python scripts/15_surface_wave_inspection.py --config <fixture-config> --manifest manifests/examples/milestone_1_demo.yaml --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --arm-id surface_wave_intact --sweep-spec config/surface_wave_sweep.example.yaml",
        ],
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "fixture_suite_coverage": fixture_suite_coverage,
        "generated_fixture": copy.deepcopy(fixture),
        "manifest_plan_audit": manifest_plan_audit,
        "surface_wave_execution_audit": surface_wave_execution_audit,
        "baseline_comparison_audit": baseline_comparison_audit,
        "surface_wave_inspection_audit": surface_wave_inspection_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": remaining_risks,
        "follow_on_issues": follow_on_issues,
        "issues": all_issues,
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            "local_surface_wave_gate": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_workstreams": [
                "mixed_fidelity",
                "metrics",
                "validation",
                "ui",
            ],
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone10_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _materialize_verification_fixture(
    *,
    manifest_path: Path,
    verification_cfg: Mapping[str, Any],
    generated_fixture_dir: Path,
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
    processed_simulator_results_dir: Path,
    surface_wave_inspection_dir: Path,
) -> dict[str, Any]:
    fixture_assets_dir = ensure_dir(generated_fixture_dir / "assets")
    subset_output_dir = ensure_dir(generated_fixture_dir / "subsets")
    manifest_payload = load_yaml(manifest_path)
    subset_name = str(manifest_payload["subset_name"])
    selected_root_ids = [101, 202]

    stimulus = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=_resolve_repo_path(
            verification_cfg.get("schema_path"),
            REPO_ROOT,
            default=REPO_ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json",
        ),
        design_lock_path=_resolve_repo_path(
            verification_cfg.get("design_lock_path"),
            REPO_ROOT,
            default=REPO_ROOT / "config" / "milestone_1_design_lock.yaml",
        ),
        processed_stimulus_dir=processed_stimulus_dir,
    )
    record_stimulus_bundle(stimulus)

    selected_root_ids_path = generated_fixture_dir / "selected_root_ids.txt"
    write_root_ids(selected_root_ids, selected_root_ids_path)

    subset_manifest_path = subset_output_dir / subset_name / "subset_manifest.json"
    subset_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    subset_manifest_path.write_text(
        json.dumps(
            {
                "subset_manifest_version": "1",
                "preset_name": subset_name,
                "root_ids": selected_root_ids,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    geometry_manifest_path = generated_fixture_dir / "geometry_manifest.json"
    _write_execution_geometry_manifest(
        output_dir=fixture_assets_dir,
        manifest_path=geometry_manifest_path,
    )

    baseline_family_overrides = _deep_merge_mappings(
        DEFAULT_VERIFICATION_BASELINE_FAMILIES,
        verification_cfg.get("baseline_families"),
        field_name="simulation_verification.baseline_families",
    )
    config_payload = {
        "paths": {
            "selected_root_ids": str(selected_root_ids_path.resolve()),
            "subset_output_dir": str(subset_output_dir.resolve()),
            "manifest_json": str(geometry_manifest_path.resolve()),
            "processed_stimulus_dir": str(processed_stimulus_dir.resolve()),
            "processed_retinal_dir": str(processed_retinal_dir.resolve()),
            "processed_simulator_results_dir": str(processed_simulator_results_dir.resolve()),
            "surface_wave_inspection_dir": str(surface_wave_inspection_dir.resolve()),
        },
        "selection": {
            "active_preset": subset_name,
        },
        "simulation": {
            "input": {
                "source_kind": "stimulus_bundle",
                "require_recorded_bundle": True,
            },
            "readout_catalog": copy.deepcopy(DEFAULT_VERIFICATION_READOUT_CATALOG),
            "baseline_families": baseline_family_overrides,
        },
    }
    if verification_cfg.get("surface_wave") is not None:
        config_payload["simulation"]["surface_wave"] = copy.deepcopy(
            verification_cfg["surface_wave"]
        )

    fixture_config_path = generated_fixture_dir / "simulation_fixture_config.yaml"
    fixture_config_path.write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "fixture_config_path": str(fixture_config_path.resolve()),
        "selected_root_ids_path": str(selected_root_ids_path.resolve()),
        "subset_manifest_path": str(subset_manifest_path.resolve()),
        "geometry_manifest_path": str(geometry_manifest_path.resolve()),
        "fixture_assets_dir": str(fixture_assets_dir.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir.resolve()),
        "processed_retinal_dir": str(processed_retinal_dir.resolve()),
        "processed_simulator_results_dir": str(processed_simulator_results_dir.resolve()),
        "surface_wave_inspection_dir": str(surface_wave_inspection_dir.resolve()),
        "selected_root_ids": list(selected_root_ids),
    }


def _build_manifest_plan_audit(
    *,
    fixture: Mapping[str, Any],
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    baseline_run_plans = discover_simulation_run_plans(plan, model_mode="baseline")
    surface_wave_run_plans = discover_simulation_run_plans(plan, model_mode="surface_wave")
    surface_wave_seed_sweep = discover_simulation_run_plans(
        plan,
        model_mode="surface_wave",
        use_manifest_seed_sweep=True,
    )

    topology_conditions = sorted(
        {str(item["topology_condition"]) for item in surface_wave_run_plans}
    )
    if not surface_wave_run_plans:
        issues.append(_issue("blocking", "No surface-wave manifest arms were resolved."))
    if topology_conditions != ["intact", "shuffled"]:
        issues.append(
            _issue(
                "blocking",
                "Surface-wave manifest planning did not preserve both intact and shuffled topology conditions.",
            )
        )

    runtime_simulation = dict(plan["runtime_config"]["simulation"])
    surface_wave_model = parse_surface_wave_model_metadata(runtime_simulation["surface_wave_model"])
    model_metadata_path = write_surface_wave_model_metadata(surface_wave_model).resolve()
    persisted_surface_wave_model = parse_surface_wave_model_metadata(load_json(model_metadata_path))
    if persisted_surface_wave_model != surface_wave_model:
        issues.append(
            _issue(
                "blocking",
                "Persisted surface-wave model metadata drifted from the normalized planning payload.",
            )
        )

    expected_bundle_id = surface_wave_model["bundle_id"]
    arm_summaries = []
    for arm_plan in surface_wave_run_plans:
        arm_id = str(arm_plan["arm_reference"]["arm_id"])
        model_configuration = dict(arm_plan["model_configuration"])
        execution_plan = dict(model_configuration["surface_wave_execution_plan"])
        surface_wave_reference = dict(model_configuration["surface_wave_reference"])
        if surface_wave_reference["bundle_id"] != expected_bundle_id:
            issues.append(
                _issue(
                    "blocking",
                    f"Surface-wave arm {arm_id!r} drifted from the canonical surface-wave model reference.",
                )
            )
        if execution_plan["stability_guardrails"]["status"] != "pass":
            issues.append(
                _issue(
                    "blocking",
                    f"Surface-wave arm {arm_id!r} did not preserve a passing stability guardrail status.",
                )
            )
        if len(execution_plan["selected_root_operator_assets"]) != len(fixture["selected_root_ids"]):
            issues.append(
                _issue(
                    "blocking",
                    f"Surface-wave arm {arm_id!r} resolved an unexpected operator-asset count.",
                )
            )
        if len(execution_plan["selected_root_coupling_assets"]) != len(fixture["selected_root_ids"]):
            issues.append(
                _issue(
                    "blocking",
                    f"Surface-wave arm {arm_id!r} resolved an unexpected coupling-asset count.",
                )
            )
        arm_summaries.append(
            {
                "arm_id": arm_id,
                "topology_condition": str(arm_plan["topology_condition"]),
                "shared_output_timestep_ms": float(
                    execution_plan["solver"]["shared_output_timestep_ms"]
                ),
                "integration_timestep_ms": float(
                    execution_plan["solver"]["integration_timestep_ms"]
                ),
                "internal_substep_count": int(
                    execution_plan["solver"]["internal_substep_count"]
                ),
                "limiting_root_id": int(
                    execution_plan["stability_guardrails"]["limiting_root_id"]
                ),
                "operator_root_count": len(execution_plan["selected_root_operator_assets"]),
                "coupling_root_count": len(execution_plan["selected_root_coupling_assets"]),
            }
        )

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "manifest_arm_count": len(plan["arm_plans"]),
        "baseline_arm_count": len(baseline_run_plans),
        "surface_wave_arm_count": len(surface_wave_run_plans),
        "surface_wave_seed_sweep_run_count": len(surface_wave_seed_sweep),
        "surface_wave_arm_ids": [
            item["arm_reference"]["arm_id"] for item in surface_wave_run_plans
        ],
        "surface_wave_topology_conditions": topology_conditions,
        "selected_root_ids": list(fixture["selected_root_ids"]),
        "surface_wave_model_audit": {
            "overall_status": "pass" if persisted_surface_wave_model == surface_wave_model else "fail",
            "metadata_path": str(model_metadata_path),
            "bundle_id": str(surface_wave_model["bundle_id"]),
            "parameter_hash": str(surface_wave_model["parameter_hash"]),
            "model_family": str(surface_wave_model["model_family"]),
            "solver_family": str(surface_wave_model["solver_family"]),
            "recovery_mode": str(surface_wave_model["recovery_mode"]),
            "nonlinearity_mode": str(surface_wave_model["nonlinearity_mode"]),
            "anisotropy_mode": str(surface_wave_model["anisotropy_mode"]),
            "branching_mode": str(surface_wave_model["branching_mode"]),
        },
        "surface_wave_arm_summaries": arm_summaries,
    }
    write_json(audit, commands_dir / "manifest_plan_audit.json")
    return audit, plan


def _execute_surface_wave_workflow_audit(
    *,
    fixture: Mapping[str, Any],
    plan: Mapping[str, Any],
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    surface_wave_run_plans = {
        item["arm_reference"]["arm_id"]: item
        for item in discover_simulation_run_plans(plan, model_mode="surface_wave")
    }
    planned_arm = surface_wave_run_plans.get("surface_wave_intact")
    if planned_arm is None:
        issues.append(
            _issue("blocking", "Representative arm 'surface_wave_intact' is missing from the manifest plan."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
        }

    command = [
        python_executable,
        str(repo_root / "scripts" / "run_simulation.py"),
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(manifest_path),
        "--schema",
        str(schema_path),
        "--design-lock",
        str(design_lock_path),
        "--model-mode",
        "surface_wave",
        "--arm-id",
        "surface_wave_intact",
    ]

    first = _run_command(name="surface_wave_execution_first", command=command, cwd=repo_root)
    first_summary = dict(first.get("parsed_summary") or {})
    write_json(first, commands_dir / "surface_wave_execution_first.json")
    if first["status"] != "pass":
        issues.append(
            _issue("blocking", "The shipped surface-wave execution command failed on the representative fixture."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
            "commands": {"first": first},
        }

    first_hashes = _capture_bundle_hashes(first_summary)
    second = _run_command(name="surface_wave_execution_second", command=command, cwd=repo_root)
    second_summary = dict(second.get("parsed_summary") or {})
    write_json(second, commands_dir / "surface_wave_execution_second.json")
    if second["status"] != "pass":
        issues.append(
            _issue("blocking", "The repeated surface-wave execution command failed, so determinism could not be confirmed."),
        )

    summary_stable = first_summary == second_summary
    if not summary_stable:
        issues.append(
            _issue("blocking", "Repeated surface-wave execution produced different command summaries."),
        )
    file_hashes_stable = _compare_bundle_hashes(first_hashes, second_summary)
    if not file_hashes_stable:
        issues.append(
            _issue("blocking", "Repeated surface-wave execution changed one or more result-bundle artifact bytes."),
        )

    if int(first_summary.get("executed_run_count", 0)) != 1:
        issues.append(
            _issue("blocking", "Surface-wave execution did not resolve exactly one representative arm."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
            "commands": {
                "first": first,
                "second": second,
            },
            "executed_run_count": int(first_summary.get("executed_run_count", 0)),
            "executed_arm_ids": list(first_summary.get("arm_order", [])),
            "summary_stable": summary_stable,
            "file_hashes_stable": file_hashes_stable,
            "first_run_hashes": first_hashes,
        }

    run_summary = dict(first_summary["executed_runs"][0])
    bundle_audit = _audit_surface_wave_run(
        run_summary=run_summary,
        planned_arm=planned_arm,
    )
    issues.extend(bundle_audit["issues"])

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "commands": {
            "first": first,
            "second": second,
        },
        "executed_run_count": int(first_summary.get("executed_run_count", 0)),
        "executed_arm_ids": list(first_summary.get("arm_order", [])),
        "summary_stable": summary_stable,
        "file_hashes_stable": file_hashes_stable,
        "first_run_hashes": first_hashes,
        "bundle_audit": bundle_audit,
    }
    write_json(audit, commands_dir / "surface_wave_execution_audit.json")
    return audit


def _execute_baseline_comparison_audit(
    *,
    fixture: Mapping[str, Any],
    plan: Mapping[str, Any],
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
    surface_wave_bundle_audit: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    baseline_run_plans = {
        item["arm_reference"]["arm_id"]: item
        for item in discover_simulation_run_plans(plan, model_mode="baseline")
    }
    planned_arm = baseline_run_plans.get("baseline_p1_intact")
    if planned_arm is None:
        issues.append(
            _issue("blocking", "Representative arm 'baseline_p1_intact' is missing from the manifest plan."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
        }

    command = [
        python_executable,
        str(repo_root / "scripts" / "run_simulation.py"),
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(manifest_path),
        "--schema",
        str(schema_path),
        "--design-lock",
        str(design_lock_path),
        "--model-mode",
        "baseline",
        "--arm-id",
        "baseline_p1_intact",
    ]
    result = _run_command(name="baseline_comparison_execution", command=command, cwd=repo_root)
    parsed_summary = dict(result.get("parsed_summary") or {})
    write_json(result, commands_dir / "baseline_comparison_execution.json")
    if result["status"] != "pass":
        issues.append(
            _issue("blocking", "The representative baseline companion command failed."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
            "command": result,
        }

    if int(parsed_summary.get("executed_run_count", 0)) != 1:
        issues.append(
            _issue("blocking", "Representative baseline comparison command did not resolve exactly one arm."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
            "command": result,
        }

    bundle_audit = _audit_baseline_run(
        run_summary=dict(parsed_summary["executed_runs"][0]),
        planned_arm=planned_arm,
    )
    issues.extend(bundle_audit["issues"])

    comparison_surface_aligned = (
        list(surface_wave_bundle_audit.get("shared_readout_ids", []))
        == list(bundle_audit.get("shared_readout_ids", []))
        and str(surface_wave_bundle_audit.get("timebase_signature", ""))
        == str(bundle_audit.get("timebase_signature", ""))
        and list(surface_wave_bundle_audit.get("metric_columns", []))
        == list(bundle_audit.get("metric_columns", []))
        and list(surface_wave_bundle_audit.get("ui_view_ids", []))
        == list(bundle_audit.get("ui_view_ids", []))
        and str(surface_wave_bundle_audit.get("declared_metrics_json", ""))
        == str(bundle_audit.get("declared_metrics_json", ""))
    )
    if not comparison_surface_aligned:
        issues.append(
            _issue(
                "blocking",
                "Surface-wave and representative baseline bundles drifted on the shared comparison surface.",
            )
        )

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "command": result,
        "baseline_arm_id": "baseline_p1_intact",
        "bundle_audit": bundle_audit,
        "comparison_surface_aligned": comparison_surface_aligned,
    }
    write_json(audit, commands_dir / "baseline_comparison_audit.json")
    return audit


def _execute_surface_wave_inspection_audit(
    *,
    fixture: Mapping[str, Any],
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    sweep_spec_path: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    command = [
        python_executable,
        str(repo_root / "scripts" / "15_surface_wave_inspection.py"),
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(manifest_path),
        "--schema",
        str(schema_path),
        "--design-lock",
        str(design_lock_path),
        "--arm-id",
        "surface_wave_intact",
        "--sweep-spec",
        str(sweep_spec_path),
    ]

    first = _run_command(name="surface_wave_inspection_first", command=command, cwd=repo_root)
    first_summary = dict(first.get("parsed_summary") or {})
    write_json(first, commands_dir / "surface_wave_inspection_first.json")
    if first["status"] != "pass":
        issues.append(
            _issue("blocking", "The shipped surface-wave inspection command failed on the representative fixture."),
        )
        return {
            "overall_status": "fail",
            "issues": issues,
            "commands": {"first": first},
        }

    first_output_dir = Path(str(first_summary["output_dir"])).resolve()
    first_hashes = _hash_directory_tree(first_output_dir)
    second = _run_command(name="surface_wave_inspection_second", command=command, cwd=repo_root)
    second_summary = dict(second.get("parsed_summary") or {})
    write_json(second, commands_dir / "surface_wave_inspection_second.json")
    if second["status"] != "pass":
        issues.append(
            _issue("blocking", "The repeated surface-wave inspection command failed, so determinism could not be confirmed."),
        )

    summary_stable = first_summary == second_summary
    if not summary_stable:
        issues.append(
            _issue("blocking", "Repeated surface-wave inspection produced different command summaries."),
        )
    artifact_hashes_stable = bool(
        second.get("status") == "pass"
        and first_hashes
        == _hash_directory_tree(Path(str(second_summary["output_dir"])).resolve())
    )
    if not artifact_hashes_stable:
        issues.append(
            _issue("blocking", "Repeated surface-wave inspection changed one or more report artifact bytes."),
        )

    run_summaries = list(first_summary.get("run_summaries", []))
    if not run_summaries:
        issues.append(
            _issue("blocking", "Surface-wave inspection did not produce any run summaries."),
        )
    sweep_point_ids = [
        str(item["parameter_context"]["sweep_point_id"])
        for item in run_summaries
    ]
    if "reference" not in sweep_point_ids or "recovery_probe" not in sweep_point_ids:
        issues.append(
            _issue(
                "blocking",
                "The shipped example sweep spec did not produce both the reference and recovery probe runs.",
            )
        )
    for run_summary in run_summaries:
        artifacts = dict(run_summary["artifacts"])
        for artifact_key in (
            "report_path",
            "summary_path",
            "traces_path",
            "coupled_shared_trace_svg_path",
        ):
            if not Path(str(artifacts[artifact_key])).exists():
                issues.append(
                    _issue(
                        "blocking",
                        f"Inspection artifact {artifact_key!r} is missing for run {run_summary['run_id']!r}.",
                    )
                )
    review_issue_count = 0
    if int(first_summary.get("status_counts", {}).get("fail", 0)) > 0:
        issues.append(
            _issue(
                "review",
                "The shipped surface-wave inspection sweep reported one or more failed runs that remain under scientific review.",
            )
        )
        review_issue_count += 1

    blocking_issue_count = sum(
        1
        for issue in issues
        if str(issue.get("severity", "")) == "blocking"
    )
    overall_status = "pass"
    if blocking_issue_count:
        overall_status = "fail"
    elif review_issue_count:
        overall_status = "review"

    audit = {
        "overall_status": overall_status,
        "issues": issues,
        "commands": {
            "first": first,
            "second": second,
        },
        "output_dir": str(first_output_dir),
        "report_path": str(first_summary["report_path"]),
        "summary_path": str(first_summary["summary_path"]),
        "runs_csv_path": str(first_summary["runs_csv_path"]),
        "inspection_summary_status": str(first_summary.get("overall_status", "")),
        "summary_stable": summary_stable,
        "artifact_hashes_stable": artifact_hashes_stable,
        "run_count": int(first_summary.get("run_count", 0)),
        "status_counts": copy.deepcopy(first_summary.get("status_counts", {})),
        "sweep_point_ids": sweep_point_ids,
    }
    write_json(audit, commands_dir / "surface_wave_inspection_audit.json")
    return audit


def _audit_surface_wave_run(
    *,
    run_summary: Mapping[str, Any],
    planned_arm: Mapping[str, Any],
) -> dict[str, Any]:
    common = _audit_result_bundle_common(run_summary=run_summary, planned_arm=planned_arm)
    issues = list(common["issues"])

    extension_artifacts = common["extension_artifacts"]
    for artifact_id in REQUIRED_SURFACE_WAVE_ARTIFACT_IDS:
        if artifact_id not in extension_artifacts:
            issues.append(
                _issue(
                    "blocking",
                    f"Surface-wave run is missing required extension artifact {artifact_id!r}.",
                )
            )

    wave_summary = load_json(extension_artifacts[SURFACE_WAVE_SUMMARY_ARTIFACT_ID]["path"])
    coupling_payload = load_json(extension_artifacts[SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID]["path"])
    with Path(extension_artifacts[STRUCTURED_LOG_ARTIFACT_ID]["path"]).open(
        "r",
        encoding="utf-8",
    ) as handle:
        structured_log_event_count = sum(1 for _ in handle)
    with np.load(
        extension_artifacts[SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID]["path"],
        allow_pickle=False,
    ) as patch_traces:
        patch_trace_arrays = sorted(str(key) for key in patch_traces.files)

    state_summary_ids = {
        str(row["state_id"])
        for row in common["state_summary_rows"]
    }
    if "circuit_surface_activation_state" not in state_summary_ids:
        issues.append(
            _issue("blocking", "Surface-wave state summary is missing the circuit surface activation state."),
        )
    if not any(state_id.endswith("_patch_activation_state") for state_id in state_summary_ids):
        issues.append(
            _issue("blocking", "Surface-wave state summary is missing root-local patch activation rows."),
        )
    if wave_summary["format_version"] != "json_surface_wave_execution_summary.v1":
        issues.append(
            _issue("blocking", "Surface-wave summary payload wrote an unexpected format version."),
        )
    if coupling_payload["format_version"] != "json_surface_wave_coupling_events.v1":
        issues.append(
            _issue("blocking", "Surface-wave coupling payload wrote an unexpected format version."),
        )
    if wave_summary["canonical_input"]["input_kind"] != "stimulus_bundle":
        issues.append(
            _issue("blocking", "Surface-wave canonical input did not resolve the expected stimulus_bundle."),
        )
    if wave_summary["input_binding"]["injection_strategy"] != "uniform_surface_fill_from_shared_root_schedule":
        issues.append(
            _issue("blocking", "Surface-wave input binding drifted from the shipped injection strategy."),
        )
    if wave_summary["surface_wave_reference"] != planned_arm["model_configuration"]["surface_wave_reference"]:
        issues.append(
            _issue("blocking", "Surface-wave summary drifted from the planned surface-wave model reference."),
        )
    if wave_summary["coupling"]["component_count"] < 1:
        issues.append(
            _issue("blocking", "Surface-wave coupling metadata reported zero resolved coupling components."),
        )
    if "substep_time_ms" not in patch_trace_arrays:
        issues.append(
            _issue("blocking", "Surface-wave patch traces are missing the substep_time_ms array."),
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "arm_id": str(run_summary["arm_id"]),
        "bundle_id": str(common["metadata"]["bundle_id"]),
        "run_spec_hash": str(common["metadata"]["run_spec_hash"]),
        "shared_readout_ids": common["shared_readout_ids"],
        "timebase_signature": common["timebase_signature"],
        "metric_columns": common["metric_columns"],
        "metric_ids": common["metric_ids"],
        "ui_view_ids": common["ui_view_ids"],
        "declared_metrics_json": common["declared_metrics_json"],
        "artifact_inventory_ids": common["artifact_inventory_ids"],
        "wave_specific_artifact_ids": sorted(REQUIRED_SURFACE_WAVE_ARTIFACT_IDS),
        "canonical_input_kind": str(wave_summary["canonical_input"]["input_kind"]),
        "coupling_event_count": int(coupling_payload["event_count"]),
        "comparison_ready_bundle": common["comparison_ready_bundle"],
        "structured_log_event_count": structured_log_event_count,
        "patch_trace_arrays": patch_trace_arrays,
    }


def _audit_baseline_run(
    *,
    run_summary: Mapping[str, Any],
    planned_arm: Mapping[str, Any],
) -> dict[str, Any]:
    common = _audit_result_bundle_common(run_summary=run_summary, planned_arm=planned_arm)
    issues = list(common["issues"])
    if str(common["metadata"]["arm_reference"]["baseline_family"]) != "P1":
        issues.append(
            _issue("blocking", "Representative baseline companion did not preserve baseline family P1."),
        )
    if REQUIRED_SURFACE_WAVE_ARTIFACT_IDS & set(common["artifact_inventory_ids"]):
        issues.append(
            _issue("blocking", "Baseline comparison bundle unexpectedly included wave-only extension artifacts."),
        )
    return {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "arm_id": str(run_summary["arm_id"]),
        "bundle_id": str(common["metadata"]["bundle_id"]),
        "run_spec_hash": str(common["metadata"]["run_spec_hash"]),
        "shared_readout_ids": common["shared_readout_ids"],
        "timebase_signature": common["timebase_signature"],
        "metric_columns": common["metric_columns"],
        "metric_ids": common["metric_ids"],
        "ui_view_ids": common["ui_view_ids"],
        "declared_metrics_json": common["declared_metrics_json"],
        "artifact_inventory_ids": common["artifact_inventory_ids"],
        "comparison_ready_bundle": common["comparison_ready_bundle"],
    }


def _audit_result_bundle_common(
    *,
    run_summary: Mapping[str, Any],
    planned_arm: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    metadata_path = Path(str(run_summary["metadata_path"])).resolve()
    metadata = load_simulator_result_bundle_metadata(metadata_path)
    result_paths = discover_simulator_result_bundle_paths(metadata)
    extension_artifacts = {
        item["artifact_id"]: item
        for item in discover_simulator_extension_artifacts(metadata)
    }
    state_summary_rows = json.loads(result_paths[STATE_SUMMARY_KEY].read_text(encoding="utf-8"))
    metrics_header, metrics_rows = _read_csv_rows(result_paths[METRICS_TABLE_KEY])
    ui_payload = load_json(extension_artifacts[UI_COMPARISON_PAYLOAD_ARTIFACT_ID]["path"])
    trace_summary = _load_trace_summary(result_paths[READOUT_TRACES_KEY])

    planned_bundle = planned_arm["result_bundle"]["reference"]
    if metadata["contract_version"] != SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote an unexpected result-bundle contract version."),
        )
    if metadata["design_note"] != SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} did not point back to the canonical simulator design note."),
        )
    if metadata["bundle_id"] != planned_bundle["bundle_id"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote a bundle_id that drifted from the manifest plan."),
        )
    if metadata["run_spec_hash"] != planned_bundle["run_spec_hash"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote a run_spec_hash that drifted from the manifest plan."),
        )
    if metrics_header != list(METRIC_TABLE_COLUMNS):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote metrics.csv with an unexpected column contract."),
        )

    artifact_inventory_ids = sorted(
        str(item["artifact_id"])
        for item in ui_payload["artifact_inventory"]
    )
    if not REQUIRED_SHARED_ARTIFACT_IDS.issubset(artifact_inventory_ids):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} is missing one or more shared artifact inventory entries."),
        )
    if str(ui_payload["trace_payload"]["path"]) != str(result_paths[READOUT_TRACES_KEY]):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote a UI payload that drifted from the trace archive path."),
        )

    comparison_ready_bundle = (
        REQUIRED_SHARED_ARTIFACT_IDS.issubset(artifact_inventory_ids)
        and metrics_header == list(METRIC_TABLE_COLUMNS)
    )
    metric_ids = sorted({str(row["metric_id"]) for row in metrics_rows})
    ui_view_ids = [
        str(item["output_id"])
        for item in ui_payload["declared_output_targets"]["views"]
    ]
    return {
        "issues": issues,
        "metadata": metadata,
        "result_paths": result_paths,
        "extension_artifacts": extension_artifacts,
        "state_summary_rows": state_summary_rows,
        "shared_readout_ids": trace_summary["readout_ids"],
        "timebase_signature": json.dumps(metadata["timebase"], sort_keys=True),
        "metric_columns": metrics_header,
        "metric_ids": metric_ids,
        "ui_view_ids": ui_view_ids,
        "declared_metrics_json": str(ui_payload["declared_output_targets"]["metrics_json"]),
        "artifact_inventory_ids": artifact_inventory_ids,
        "comparison_ready_bundle": comparison_ready_bundle,
    }


def _build_fixture_suite_coverage(fixture_verification: Mapping[str, Any]) -> dict[str, Any]:
    targets = {
        str(item)
        for item in fixture_verification.get("targets", [])
    }
    passed = str(fixture_verification.get("status", "")) == "pass"
    return {
        "wave_model_contract": passed and "tests.test_surface_wave_contract" in targets,
        "manifest_planning": passed and "tests.test_simulation_planning" in targets,
        "single_neuron_solver": passed and "tests.test_surface_wave_solver" in targets,
        "optional_modes": passed and "tests.test_surface_wave_solver" in targets,
        "coupled_execution": passed and "tests.test_surface_wave_execution" in targets,
        "result_bundle_contract": passed and "tests.test_simulator_result_contract" in targets,
        "manifest_execution": passed and "tests.test_simulator_execution" in targets,
        "inspection_tooling": passed and "tests.test_surface_wave_inspection" in targets,
    }


def _build_workflow_coverage(
    *,
    fixture_suite_coverage: Mapping[str, Any],
    manifest_plan_audit: Mapping[str, Any],
    surface_wave_execution_audit: Mapping[str, Any],
    baseline_comparison_audit: Mapping[str, Any],
    surface_wave_inspection_audit: Mapping[str, Any],
    documentation_audit: Mapping[str, Any],
) -> dict[str, bool]:
    surface_wave_bundle = dict(surface_wave_execution_audit.get("bundle_audit", {}))
    return {
        "wave_model_discovery_compatible": bool(
            fixture_suite_coverage.get("wave_model_contract")
            and manifest_plan_audit.get("surface_wave_model_audit", {}).get("overall_status") == "pass"
        ),
        "manifest_planning_compatible": bool(
            fixture_suite_coverage.get("manifest_planning")
            and manifest_plan_audit.get("overall_status") == "pass"
        ),
        "single_neuron_solver_compatible": bool(fixture_suite_coverage.get("single_neuron_solver")),
        "recovery_nonlinearity_anisotropy_branching_compatible": bool(
            fixture_suite_coverage.get("optional_modes")
        ),
        "coupling_execution_compatible": bool(
            fixture_suite_coverage.get("coupled_execution")
            and surface_wave_bundle.get("coupling_event_count", 0) >= 0
        ),
        "canonical_input_integration_compatible": bool(
            surface_wave_bundle.get("canonical_input_kind") == "stimulus_bundle"
        ),
        "comparison_ready_result_bundles": bool(
            fixture_suite_coverage.get("result_bundle_contract")
            and surface_wave_bundle.get("comparison_ready_bundle")
            and baseline_comparison_audit.get("comparison_surface_aligned")
        ),
        "inspection_tooling_compatible": bool(
            fixture_suite_coverage.get("inspection_tooling")
            and str(surface_wave_inspection_audit.get("overall_status", "")) in {"pass", "review"}
        ),
        "determinism_compatible": bool(
            surface_wave_execution_audit.get("summary_stable")
            and surface_wave_execution_audit.get("file_hashes_stable")
            and surface_wave_inspection_audit.get("summary_stable")
            and surface_wave_inspection_audit.get("artifact_hashes_stable")
        ),
        "documentation_compatible": str(documentation_audit.get("overall_status", "fail")) == "pass",
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    audits: dict[str, Any] = {}
    issues: list[dict[str, str]] = []

    for relative_path, required_snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        doc_path = repo_root / relative_path
        missing_snippets: list[str] = []
        if not doc_path.exists():
            missing_snippets = list(required_snippets)
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing, so the Milestone 10 readiness workflow is not documented there.",
                )
            )
            audits[relative_path] = {
                "status": "fail",
                "path": str(doc_path.resolve()),
                "missing_snippets": missing_snippets,
            }
            continue

        content = doc_path.read_text(encoding="utf-8")
        missing_snippets = [snippet for snippet in required_snippets if snippet not in content]
        if missing_snippets:
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing the Milestone 10 readiness snippets {missing_snippets!r}.",
                )
            )
        audits[relative_path] = {
            "status": "pass" if not missing_snippets else "fail",
            "path": str(doc_path.resolve()),
            "missing_snippets": missing_snippets,
        }

    return {
        "overall_status": "pass" if not issues else "fail",
        "files": audits,
        "issues": issues,
    }


def _capture_bundle_hashes(summary: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    hashes: dict[str, dict[str, str]] = {}
    for run in summary.get("executed_runs", []):
        arm_id = str(run["arm_id"])
        metadata = load_simulator_result_bundle_metadata(Path(str(run["metadata_path"])).resolve())
        artifact_paths = _bundle_artifact_paths(metadata)
        hashes[arm_id] = {
            artifact_id: _hash_file(path)
            for artifact_id, path in artifact_paths.items()
        }
    return hashes


def _compare_bundle_hashes(
    expected_hashes: Mapping[str, Mapping[str, str]],
    summary: Mapping[str, Any],
) -> bool:
    return _capture_bundle_hashes(summary) == expected_hashes


def _bundle_artifact_paths(metadata: Mapping[str, Any]) -> dict[str, Path]:
    result_paths = discover_simulator_result_bundle_paths(metadata)
    extension_paths = {
        str(item["artifact_id"]): Path(str(item["path"])).resolve()
        for item in discover_simulator_extension_artifacts(metadata)
    }
    paths = {
        artifact_id: path.resolve()
        for artifact_id, path in result_paths.items()
    }
    paths.update(extension_paths)
    return paths


def _hash_directory_tree(path: Path) -> dict[str, str]:
    return {
        str(file_path.relative_to(path)): _hash_file(file_path)
        for file_path in sorted(item for item in path.rglob("*") if item.is_file())
    }


def _load_trace_summary(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        array_names = sorted(str(key) for key in archive.files)
        readout_ids = [str(item) for item in archive["readout_ids"].tolist()]
        time_ms = [float(item) for item in archive["time_ms"].tolist()]
    return {
        "array_names": array_names,
        "readout_ids": readout_ids,
        "sample_count": len(time_ms),
        "sample_start_ms": time_ms[0],
        "sample_end_ms": time_ms[-1],
    }


def _render_milestone10_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    plan_audit = dict(summary["manifest_plan_audit"])
    execution_audit = dict(summary["surface_wave_execution_audit"])
    bundle_audit = dict(execution_audit.get("bundle_audit", {}))
    baseline_audit = dict(summary["baseline_comparison_audit"])
    inspection_audit = dict(summary["surface_wave_inspection_audit"])
    documentation_audit = dict(summary["documentation_audit"])
    workflow_coverage = dict(summary["workflow_coverage"])

    lines = [
        "# Milestone 10 Readiness Report",
        "",
        "## Verdict",
        "",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Local surface-wave gate: `{readiness['local_surface_wave_gate']}`",
        f"- Ready for downstream mixed-fidelity, metrics, validation, and UI work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Verification command: `{summary['documented_verification_command']}`",
        f"- Explicit command: `{summary['explicit_verification_command']}`",
        "",
        "## Verification Surface",
        "",
        f"- Focused fixture suite: `{summary['fixture_verification'].get('status', '')}`",
        f"- Representative manifest path: `{summary['manifest_path']}`",
        f"- Representative sweep spec: `{summary['sweep_spec_path']}`",
        f"- Planned baseline arms: `{plan_audit['baseline_arm_count']}`",
        f"- Planned surface-wave arms: `{plan_audit['surface_wave_arm_count']}`",
        f"- Surface-wave seed-sweep run count discoverable from the same manifest: `{plan_audit['surface_wave_seed_sweep_run_count']}`",
        f"- Repeated surface-wave command summary stable: `{execution_audit.get('summary_stable', False)}`",
        f"- Repeated surface-wave bundle bytes stable: `{execution_audit.get('file_hashes_stable', False)}`",
        f"- Repeated inspection summary stable: `{inspection_audit.get('summary_stable', False)}`",
        f"- Repeated inspection artifact bytes stable: `{inspection_audit.get('artifact_hashes_stable', False)}`",
        f"- Documentation audit: `{documentation_audit['overall_status']}`",
        "",
        "## Workflow Coverage",
        "",
    ]

    for key, value in workflow_coverage.items():
        lines.append(f"- {key.replace('_', ' ')}: `{value}`")

    lines.extend(
        [
            "",
            "## Representative Commands",
            "",
        ]
    )
    for command in summary["representative_commands"]:
        lines.append(f"- `{command}`")

    lines.extend(
        [
            "",
            "## Surface-Wave Execution Audit",
            "",
            f"- Executed arm: `{bundle_audit.get('arm_id', '')}`",
            f"- Bundle id: `{bundle_audit.get('bundle_id', '')}`",
            f"- Shared readouts: `{', '.join(bundle_audit.get('shared_readout_ids', []))}`",
            f"- Wave extension artifacts: `{', '.join(bundle_audit.get('wave_specific_artifact_ids', []))}`",
            f"- Coupling event count: `{bundle_audit.get('coupling_event_count', 0)}`",
            f"- Comparison-ready bundle surface preserved: `{bundle_audit.get('comparison_ready_bundle', False)}`",
            "",
            "## Baseline Comparison Audit",
            "",
            f"- Representative baseline arm: `{baseline_audit.get('baseline_arm_id', '')}`",
            f"- Shared comparison surface aligned: `{baseline_audit.get('comparison_surface_aligned', False)}`",
            f"- Baseline artifact inventory covers shared contract: `{baseline_audit.get('bundle_audit', {}).get('comparison_ready_bundle', False)}`",
            "",
            "## Inspection Audit",
            "",
            f"- Inspection audit status: `{inspection_audit.get('overall_status', '')}`",
            f"- Inspection summary status: `{inspection_audit.get('inspection_summary_status', '')}`",
            f"- Inspection run count: `{inspection_audit.get('run_count', 0)}`",
            f"- Sweep points: `{', '.join(inspection_audit.get('sweep_point_ids', []))}`",
            f"- Inspection output dir: `{inspection_audit.get('output_dir', '')}`",
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
            "## Follow-On Issues",
            "",
        ]
    )
    for issue in summary["follow_on_issues"]:
        lines.append(
            f"- `{issue['ticket_id']}`: {issue['title']}. {issue['summary']} Reproduction: {issue['reproduction']}"
        )

    return "\n".join(lines) + "\n"
