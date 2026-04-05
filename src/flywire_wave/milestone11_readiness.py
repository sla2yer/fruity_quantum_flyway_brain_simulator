from __future__ import annotations

import copy
import json
import textwrap
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml

from .config import REPO_ROOT, load_config
from .coupling_assembly import (
    ANCHOR_COLUMN_TYPES,
    CLOUD_COLUMN_TYPES,
    COMPONENT_COLUMN_TYPES,
    COMPONENT_SYNAPSE_COLUMN_TYPES,
    EdgeCouplingBundle,
)
from .coupling_contract import (
    ASSET_STATUS_READY,
    DEFAULT_AGGREGATION_RULE,
    DEFAULT_DELAY_REPRESENTATION,
    DEFAULT_SIGN_REPRESENTATION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
    build_coupling_bundle_metadata,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
)
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    build_operator_bundle_metadata,
    default_asset_statuses,
    write_geometry_manifest,
)
from .hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_CONTRACT_VERSION,
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from .hybrid_morphology_runtime import (
    MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
    SURFACE_WAVE_MIXED_MORPHOLOGY_RUNTIME_FAMILY,
)
from .io_utils import ensure_dir, write_deterministic_npz, write_json
from .manifests import load_json, load_yaml
from .milestone9_readiness import (
    DEFAULT_VERIFICATION_BASELINE_FAMILIES,
    DEFAULT_VERIFICATION_READOUT_CATALOG,
    _deep_merge_mappings,
    _hash_file,
    _issue,
    _resolve_repo_path,
    _run_command,
)
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_mixed_fidelity_plan,
    resolve_manifest_simulation_plan,
)
from .simulator_execution import (
    EXECUTION_PROVENANCE_ARTIFACT_ID,
    MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
    STRUCTURED_LOG_ARTIFACT_ID,
    SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
    UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
)
from .simulator_result_contract import (
    METADATA_JSON_KEY,
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    discover_simulator_extension_artifacts,
    discover_simulator_result_bundle_paths,
    discover_simulator_root_morphology_metadata,
    load_simulator_result_bundle_metadata,
    load_simulator_root_state_payload,
    load_simulator_shared_readout_payload,
)
from .stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from .surface_operators import serialize_sparse_matrix
from .synapse_mapping import _write_edge_coupling_bundle_npz
from .selection import write_selected_root_roster, write_subset_manifest


MILESTONE11_READINESS_REPORT_VERSION = "milestone11_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_manifest_validation",
    "tests.test_simulation_planning",
    "tests.test_hybrid_morphology_contract",
    "tests.test_hybrid_morphology_runtime",
    "tests.test_mixed_coupling_routing",
    "tests.test_simulator_result_contract",
    "tests.test_simulator_execution",
    "tests.test_simulator_visualization",
    "tests.test_mixed_fidelity_inspection",
    "tests.test_milestone11_readiness",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone11-readiness",
        "scripts/19_milestone11_readiness.py",
        "config/milestone_11_verification.yaml",
        "scripts/18_mixed_fidelity_inspection.py",
        "scripts/17_visualize_simulator_results.py",
        "no local server is required",
    ),
    "docs/pipeline_notes.md": (
        "make milestone11-readiness",
        "scripts/19_milestone11_readiness.py",
        "milestone_11_readiness.md",
        "milestone_11_readiness.json",
        "scripts/18_mixed_fidelity_inspection.py",
        "scripts/17_visualize_simulator_results.py",
        "no local server is required",
    ),
    "docs/simulator_result_bundle_design.md": (
        "make milestone11-readiness",
        "scripts/19_milestone11_readiness.py",
        "milestone_11_readiness.md",
        "milestone_11_readiness.json",
        "no local server is required",
    ),
    "docs/mixed_fidelity_inspection.md": (
        "make milestone11-readiness",
        "scripts/19_milestone11_readiness.py",
        "scripts/18_mixed_fidelity_inspection.py",
        "scripts/17_visualize_simulator_results.py",
        "no local server is required",
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

REQUIRED_WAVE_ARTIFACT_IDS = {
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
    MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
    SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
}

EXPECTED_MIXED_PROJECTION_ROUTES = (
    "point_state_projection_to_surface_patch_injection",
    "skeleton_node_projection_to_point_state_injection",
    "surface_patch_projection_to_skeleton_node_injection",
)


def build_milestone11_readiness_paths(
    processed_simulator_results_dir: str | Path,
) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_11"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_11_readiness.md",
        "json_path": report_dir / "milestone_11_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
        "visualization_dir": report_dir / "visualization",
        "inspection_dir": report_dir / "mixed_fidelity_inspection",
    }


def execute_milestone11_readiness_pass(
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
    mixed_fidelity_inspection_dir = Path(cfg["paths"]["mixed_fidelity_inspection_dir"]).resolve()
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

    readiness_paths = build_milestone11_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = ensure_dir(readiness_paths["generated_fixture_dir"])
    visualization_dir = ensure_dir(readiness_paths["visualization_dir"])
    inspection_dir = ensure_dir(readiness_paths["inspection_dir"])

    fixture = _materialize_verification_fixture(
        source_manifest_path=manifest_path,
        generated_fixture_dir=generated_fixture_dir,
        report_dir=report_dir,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
        processed_simulator_results_dir=processed_simulator_results_dir,
        mixed_fidelity_inspection_dir=mixed_fidelity_inspection_dir,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        verification_cfg=verification_cfg,
    )
    manifest_plan_audit, plan = _build_manifest_plan_audit(
        fixture=fixture,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
    )
    mixed_execution_audit = _execute_mixed_execution_audit(
        fixture=fixture,
        plan=plan,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
    )
    visualization_audit = _execute_visualization_audit(
        fixture=fixture,
        execution_audit=mixed_execution_audit,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
        output_dir=visualization_dir,
    )
    inspection_audit = _execute_mixed_fidelity_inspection_audit(
        fixture=fixture,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
        output_dir=inspection_dir,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)
    workflow_coverage = _build_workflow_coverage(
        fixture_verification=fixture_verification,
        manifest_plan_audit=manifest_plan_audit,
        mixed_execution_audit=mixed_execution_audit,
        visualization_audit=visualization_audit,
        inspection_audit=inspection_audit,
        documentation_audit=documentation_audit,
    )

    all_issues = (
        list(manifest_plan_audit["issues"])
        + list(mixed_execution_audit["issues"])
        + list(visualization_audit["issues"])
        + list(inspection_audit["issues"])
        + list(documentation_audit["issues"])
    )
    blocking_issues = [
        issue for issue in all_issues if str(issue.get("severity", "")) == "blocking"
    ]
    review_issues = [
        issue for issue in all_issues if str(issue.get("severity", "")) == "review"
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
            "ticket_id": "FW-M11-FOLLOW-001",
            "severity": "non_blocking",
            "title": "Promote the Milestone 11 readiness fixture into a richer branch-positive mixed-fidelity stress bundle",
            "summary": (
                "The shipped readiness pass now proves that one surface root, one skeleton root, "
                "one routed point root, and one isolated point-surrogate root can coexist through "
                "planning, execution, cross-class routing, serialization, visualization, and "
                "surrogate inspection. It is still a small synthetic fixture with one promotion "
                "candidate and a branch-free skeleton."
            ),
            "reproduction": (
                "Run `make milestone11-readiness`, then inspect "
                f"`{fixture['fixture_assets_dir']}` and "
                f"`{fixture['fixture_manifest_path']}`. The generated mixed-fidelity fixture covers "
                "four selected roots, three mixed-route edge bundles, and one isolated promotion "
                "candidate, but the skeleton asset remains branch-free and the policy/inspection "
                "workflow exercises only one promoted surrogate root (`303 -> surface_neuron`)."
            ),
        },
        {
            "ticket_id": "FW-M11-FOLLOW-002",
            "severity": "non_blocking",
            "title": "Teach mixed-fidelity inspection to regenerate coupling-compatible reference variants for promoted roots with incident edges",
            "summary": (
                "The readiness fixture now keeps the promotion candidate isolated so the shipped "
                "inspection workflow can prove that manifest-only fidelity promotion still produces "
                "a runnable reference arm. Later milestones will eventually need the same audit to "
                "cover promoted roots that also participate in mixed-class coupling routes."
            ),
            "reproduction": (
                "Use the generated readiness fixture as a starting point, then attach root 303 to "
                "one or more mixed-class coupling edges and rerun "
                "`python scripts/18_mixed_fidelity_inspection.py --config "
                f"{fixture['fixture_config_path']} --manifest {fixture['fixture_manifest_path']} "
                "--schema schemas/milestone_1_experiment_manifest.schema.json --design-lock "
                "config/milestone_1_design_lock.yaml --arm-id surface_wave_intact`. The current "
                "workflow rewrites the manifest fidelity assignment but does not regenerate "
                "incident coupling anchor geometry for the promoted reference root."
            ),
        },
    ]
    remaining_risks = [
        (
            "The readiness pass is a deterministic integration audit on synthetic local assets. "
            "It proves software coherence, not biological calibration."
        ),
        (
            "Cross-class routing is exercised end to end on one representative surface->skeleton, "
            "skeleton->point, and point->surface loop. Broader morphology-specific approximation "
            "quality still depends on later validation fixtures."
        ),
        (
            "The policy hook and the surrogate inspection workflow are now wired together through "
            "the same fixture, but one readiness pass cannot settle where later readout or scientific "
            "validation work should draw the final promotion threshold."
        ),
        (
            "The shipped inspection workflow now proves that an isolated surrogate root can be "
            "promoted through a manifest-only reference rewrite. Promoting roots that already carry "
            "incident mixed-class coupling assets remains a follow-on engineering task."
        ),
    ]

    fixture_config_path = str(Path(fixture["fixture_config_path"]).resolve())
    fixture_manifest_path = str(Path(fixture["fixture_manifest_path"]).resolve())
    summary = {
        "report_version": MILESTONE11_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "schema_path": str(schema_path.resolve()),
        "design_lock_path": str(design_lock_path.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir),
        "processed_retinal_dir": str(processed_retinal_dir),
        "processed_simulator_results_dir": str(processed_simulator_results_dir),
        "mixed_fidelity_inspection_dir": str(mixed_fidelity_inspection_dir),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "commands_dir": str(commands_dir.resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "visualization_report_path": str(visualization_audit.get("report_path", "")),
        "visualization_report_file_url": str(visualization_audit.get("report_file_url", "")),
        "visualization_summary_path": str(visualization_audit.get("summary_path", "")),
        "visualization_open_hint": str(
            visualization_audit.get(
                "viewer_open_hint",
                "Open the generated visualization index.html directly in your browser; no local server is required.",
            )
        ),
        "verification_fixture_config_path": fixture_config_path,
        "verification_fixture_manifest_path": fixture_manifest_path,
        "documented_verification_command": "make milestone11-readiness",
        "explicit_verification_command": "python scripts/19_milestone11_readiness.py --config config/milestone_11_verification.yaml",
        "representative_commands": [
            f"python scripts/run_simulation.py --config {fixture_config_path} --manifest {fixture_manifest_path} --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --model-mode surface_wave --arm-id surface_wave_intact",
            f"python scripts/17_visualize_simulator_results.py --bundle-metadata {mixed_execution_audit.get('metadata_path', '')} --output-dir {str(visualization_dir.resolve())}",
            f"python scripts/18_mixed_fidelity_inspection.py --config {fixture_config_path} --manifest {fixture_manifest_path} --schema schemas/milestone_1_experiment_manifest.schema.json --design-lock config/milestone_1_design_lock.yaml --arm-id surface_wave_intact --output-dir {str(inspection_dir.resolve())}",
        ],
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "generated_fixture": copy.deepcopy(fixture),
        "manifest_plan_audit": manifest_plan_audit,
        "mixed_execution_audit": mixed_execution_audit,
        "visualization_audit": visualization_audit,
        "inspection_audit": inspection_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": remaining_risks,
        "follow_on_issues": follow_on_issues,
        "issues": all_issues,
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            "local_mixed_fidelity_gate": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_workstreams": []
            if readiness_status == READINESS_GATE_HOLD
            else ["readouts", "validation", "ui"],
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone11_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _materialize_verification_fixture(
    *,
    source_manifest_path: Path,
    generated_fixture_dir: Path,
    report_dir: Path,
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
    processed_simulator_results_dir: Path,
    mixed_fidelity_inspection_dir: Path,
    schema_path: Path,
    design_lock_path: Path,
    verification_cfg: Mapping[str, Any],
) -> dict[str, Any]:
    fixture_assets_dir = ensure_dir(generated_fixture_dir / "assets")
    subset_output_dir = ensure_dir(generated_fixture_dir / "subsets")
    fixture_manifest_path = _write_fixture_manifest(
        source_manifest_path=source_manifest_path,
        output_path=generated_fixture_dir / "fixture_manifest.yaml",
    )
    manifest_payload = load_yaml(fixture_manifest_path)
    subset_name = str(manifest_payload["subset_name"])
    selected_root_ids = [101, 202, 303, 404]

    stimulus = resolve_stimulus_input(
        manifest_path=fixture_manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )
    record_stimulus_bundle(stimulus)

    selected_root_ids_path = generated_fixture_dir / "selected_root_ids.txt"
    write_selected_root_roster(selected_root_ids, selected_root_ids_path)

    subset_manifest_path = write_subset_manifest(
        subset_output_dir=subset_output_dir,
        preset_name=subset_name,
        root_ids=selected_root_ids,
    )

    geometry_manifest_path = generated_fixture_dir / "geometry_manifest.json"
    _write_mixed_execution_geometry_manifest(
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
            "mixed_fidelity_inspection_dir": str(mixed_fidelity_inspection_dir.resolve()),
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
            "surface_wave": copy.deepcopy(_default_surface_wave_verification_config()),
            "mixed_fidelity": copy.deepcopy(_default_mixed_fidelity_verification_config()),
        },
    }

    fixture_config_path = generated_fixture_dir / "simulation_fixture_config.yaml"
    fixture_config_path.write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "fixture_config_path": str(fixture_config_path.resolve()),
        "fixture_manifest_path": str(fixture_manifest_path.resolve()),
        "selected_root_ids_path": str(selected_root_ids_path.resolve()),
        "subset_manifest_path": str(subset_manifest_path.resolve()),
        "geometry_manifest_path": str(geometry_manifest_path.resolve()),
        "fixture_assets_dir": str(fixture_assets_dir.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir.resolve()),
        "processed_retinal_dir": str(processed_retinal_dir.resolve()),
        "processed_simulator_results_dir": str(processed_simulator_results_dir.resolve()),
        "mixed_fidelity_inspection_dir": str(mixed_fidelity_inspection_dir.resolve()),
        "selected_root_ids": list(selected_root_ids),
        "expected_projection_routes": list(EXPECTED_MIXED_PROJECTION_ROUTES),
        "reference_root_id": 303,
    }


def _build_manifest_plan_audit(
    *,
    fixture: Mapping[str, Any],
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    plan = resolve_manifest_simulation_plan(
        manifest_path=fixture["fixture_manifest_path"],
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    repeated = resolve_manifest_simulation_plan(
        manifest_path=fixture["fixture_manifest_path"],
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    if plan != repeated:
        issues.append(
            _issue(
                "blocking",
                "Mixed-fidelity manifest planning is not deterministic across repeated resolution.",
            )
        )

    surface_wave_run_plans = discover_simulation_run_plans(plan, model_mode="surface_wave")
    topology_conditions = sorted(
        {str(item["topology_condition"]) for item in surface_wave_run_plans}
    )
    if topology_conditions != ["intact", "shuffled"]:
        issues.append(
            _issue(
                "blocking",
                "Mixed-fidelity manifest planning did not preserve both intact and shuffled surface_wave arms.",
            )
        )

    intact_plan = resolve_manifest_mixed_fidelity_plan(
        manifest_path=fixture["fixture_manifest_path"],
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_id="surface_wave_intact",
    )
    shuffled_plan = resolve_manifest_mixed_fidelity_plan(
        manifest_path=fixture["fixture_manifest_path"],
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_id="surface_wave_shuffled",
    )
    if intact_plan["resolved_class_counts"] != shuffled_plan["resolved_class_counts"]:
        issues.append(
            _issue(
                "blocking",
                "Mixed-fidelity class counts drift between intact and shuffled arms.",
            )
        )

    intact_by_root = {
        int(item["root_id"]): item
        for item in intact_plan["per_root_assignments"]
    }
    expected_classes = {
        101: SURFACE_NEURON_CLASS,
        202: SKELETON_NEURON_CLASS,
        303: POINT_NEURON_CLASS,
        404: POINT_NEURON_CLASS,
    }
    for root_id, expected_class in expected_classes.items():
        realized_class = str(intact_by_root[root_id]["realized_morphology_class"])
        if realized_class != expected_class:
            issues.append(
                _issue(
                    "blocking",
                    f"Mixed-fidelity plan resolved root {root_id} to {realized_class!r} instead of {expected_class!r}.",
                )
            )

    if intact_plan["policy_hook"]["promotion_recommendation_root_ids"] != [303]:
        issues.append(
            _issue(
                "review",
                "The readiness fixture policy hook no longer recommends promoting root 303, so the inspection workflow is no longer exercising the intended surrogate path.",
            )
        )

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "manifest_arm_count": len(plan["arm_plans"]),
        "surface_wave_arm_count": len(surface_wave_run_plans),
        "surface_wave_arm_ids": [
            str(item["arm_reference"]["arm_id"])
            for item in surface_wave_run_plans
        ],
        "surface_wave_topology_conditions": topology_conditions,
        "intact_mixed_fidelity_plan": {
            "plan_version": str(intact_plan["plan_version"]),
            "resolved_class_counts": copy.deepcopy(intact_plan["resolved_class_counts"]),
            "promotion_recommendation_root_ids": copy.deepcopy(
                intact_plan["policy_hook"]["promotion_recommendation_root_ids"]
            ),
            "operator_root_ids": [
                int(item["root_id"])
                for item in intact_plan["per_root_assignments"]
                if item["surface_operator_asset"] is not None
            ],
            "skeleton_asset_root_ids": [
                int(item["root_id"])
                for item in intact_plan["per_root_assignments"]
                if item["skeleton_runtime_asset"] is not None
            ],
            "per_root_assignments": [
                {
                    "root_id": int(item["root_id"]),
                    "realized_morphology_class": str(item["realized_morphology_class"]),
                    "assignment_source": str(item["assignment_provenance"]["resolved_from"]),
                    "relation_to_registry_default": str(
                        item["approximation_route"]["relation_to_registry_default"]
                    ),
                }
                for item in intact_plan["per_root_assignments"]
            ],
        },
    }
    write_json(audit, commands_dir / "manifest_plan_audit.json")
    return audit, plan


def _execute_mixed_execution_audit(
    *,
    fixture: Mapping[str, Any],
    plan: Mapping[str, Any],
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    command = [
        python_executable,
        str(repo_root / "scripts" / "run_simulation.py"),
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(fixture["fixture_manifest_path"]),
        "--schema",
        str(schema_path),
        "--design-lock",
        str(design_lock_path),
        "--model-mode",
        "surface_wave",
        "--arm-id",
        "surface_wave_intact",
    ]
    first = _run_command(name="mixed_execution_first", command=command, cwd=repo_root)
    second = _run_command(name="mixed_execution_second", command=command, cwd=repo_root)
    write_json(first, commands_dir / "mixed_execution_first.json")
    write_json(second, commands_dir / "mixed_execution_second.json")

    if first["status"] != "pass" or second["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                "The shipped mixed-fidelity run_simulation command did not execute successfully for the readiness fixture.",
            )
        )
        audit = {
            "overall_status": "fail",
            "issues": issues,
            "executed_run_count": 0,
        }
        write_json(audit, commands_dir / "mixed_execution_audit.json")
        return audit

    first_summary = first.get("parsed_summary", {})
    second_summary = second.get("parsed_summary", {})
    summary_stable = first_summary == second_summary
    if not summary_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated mixed-fidelity run_simulation invocations produced different command summaries.",
            )
        )
    executed_runs = list(first_summary.get("executed_runs", []))
    if int(first_summary.get("executed_run_count", 0)) != 1 or len(executed_runs) != 1:
        issues.append(
            _issue(
                "blocking",
                "The readiness fixture expected exactly one executed mixed-fidelity surface_wave run.",
            )
        )
    if not executed_runs:
        audit = {
            "overall_status": "fail",
            "issues": issues,
            "executed_run_count": 0,
        }
        write_json(audit, commands_dir / "mixed_execution_audit.json")
        return audit

    run_summary = dict(executed_runs[0])
    metadata_path = Path(str(run_summary["metadata_path"])).resolve()
    metadata = load_simulator_result_bundle_metadata(metadata_path)
    bundle_paths = discover_simulator_result_bundle_paths(metadata)
    extension_paths = {
        item["artifact_id"]: Path(str(item["path"])).resolve()
        for item in discover_simulator_extension_artifacts(metadata)
    }
    first_hashes = _capture_mixed_execution_hashes(metadata)
    second_hashes = _capture_mixed_execution_hashes(
        load_simulator_result_bundle_metadata(Path(second_summary["executed_runs"][0]["metadata_path"]))
    )
    file_hashes_stable = first_hashes == second_hashes
    if not file_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated mixed-fidelity run_simulation invocations produced different bundle bytes.",
            )
        )

    missing_shared_artifacts = sorted(
        artifact_id
        for artifact_id in REQUIRED_SHARED_ARTIFACT_IDS
        if artifact_id not in {
            METADATA_JSON_KEY,
            STATE_SUMMARY_KEY,
            READOUT_TRACES_KEY,
            METRICS_TABLE_KEY,
            *extension_paths.keys(),
        }
    )
    missing_wave_artifacts = sorted(
        artifact_id
        for artifact_id in REQUIRED_WAVE_ARTIFACT_IDS
        if artifact_id not in extension_paths
    )
    if missing_shared_artifacts or missing_wave_artifacts:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity result bundle is missing required shared or wave-specific artifacts.",
            )
        )

    wave_summary = load_json(extension_paths[SURFACE_WAVE_SUMMARY_ARTIFACT_ID])
    provenance = load_json(extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID])
    coupling_payload = load_json(extension_paths[SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID])
    root_metadata = discover_simulator_root_morphology_metadata(metadata)
    shared_payload = load_simulator_shared_readout_payload(metadata)
    root_payloads = {
        root_id: load_simulator_root_state_payload(metadata, root_id=root_id)
        for root_id in (101, 202, 303)
    }

    route_families = list(wave_summary["coupling"]["component_families"])
    projection_routes = sorted(
        {
            str(item["projection_route"])
            for item in route_families
            if str(item["source_morphology_class"]) != str(item["target_morphology_class"])
        }
    )
    if projection_routes != list(EXPECTED_MIXED_PROJECTION_ROUTES):
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity execution summary did not preserve the expected cross-class route catalog.",
            )
        )
    if str(wave_summary["morphology_runtime"]["runtime_family"]) != SURFACE_WAVE_MIXED_MORPHOLOGY_RUNTIME_FAMILY:
        issues.append(
            _issue(
                "blocking",
                "The readiness fixture did not execute through the mixed-morphology runtime adapter.",
            )
        )
    if wave_summary["hybrid_morphology"]["contract_version"] != HYBRID_MORPHOLOGY_CONTRACT_VERSION:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity execution summary drifted from the canonical hybrid morphology contract version.",
            )
        )
    if wave_summary["morphology_runtime"]["interface_version"] != MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity execution summary drifted from the canonical morphology runtime interface version.",
            )
        )
    if int(wave_summary["coupling"]["mixed_route_component_count"]) != 3:
        issues.append(
            _issue(
                "blocking",
                "The readiness fixture no longer resolves the expected three mixed-route coupling components.",
            )
        )
    if str(wave_summary["coupling"]["non_surface_selected_edge_execution"]) != "enabled_explicit_router_v1":
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity execution summary no longer reports the explicit cross-class router as active.",
            )
        )

    event_routes = sorted(
        {
            str(item["projection_route"])
            for item in coupling_payload.get("events", [])
            if isinstance(item, Mapping)
        }
    )
    missing_event_routes = [
        route for route in EXPECTED_MIXED_PROJECTION_ROUTES if route not in event_routes
    ]
    if missing_event_routes:
        issues.append(
            _issue(
                "blocking",
                f"The mixed-fidelity coupling event log is missing route events for {missing_event_routes!r}.",
            )
        )

    expected_root_classes = [
        SURFACE_NEURON_CLASS,
        SKELETON_NEURON_CLASS,
        POINT_NEURON_CLASS,
        POINT_NEURON_CLASS,
    ]
    discovered_root_classes = [str(item["morphology_class"]) for item in root_metadata]
    if discovered_root_classes != expected_root_classes:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity result bundle does not expose the expected per-root morphology ordering.",
            )
        )
    if str(root_payloads[303]["runtime_metadata"]["baseline_family"]) != "P0":
        issues.append(
            _issue(
                "blocking",
                "The point-neuron placeholder root did not preserve the expected P0 baseline provenance in the mixed state bundle.",
            )
        )
    if tuple(shared_payload["readout_ids"]) != ("shared_output_mean",):
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity bundle no longer exposes the expected shared readout payload.",
            )
        )

    with np.load(extension_paths[SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID], allow_pickle=False) as patch_traces:
        array_names = set(str(item) for item in patch_traces.files)
    expected_projection_arrays = {
        "root_101_patch_activation",
        "root_202_skeleton_activation",
        "root_303_point_activation",
        "root_404_point_activation",
    }
    if not expected_projection_arrays <= array_names:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity projection archive is missing one or more class-specific projection arrays.",
            )
        )

    provenance_coupling_hash = (
        provenance.get("model_execution", {})
        .get("coupling", {})
        .get("routing_hash")
    )
    if provenance_coupling_hash is None:
        provenance_coupling_hash = (
            provenance.get("model_execution", {})
            .get("morphology_runtime", {})
            .get("coupling_metadata", {})
            .get("routing_hash")
        )
    if provenance_coupling_hash is None:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity execution provenance does not expose a routing hash for the active coupling plan.",
            )
        )

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "executed_run_count": int(first_summary["executed_run_count"]),
        "executed_arm_ids": [str(run["arm_id"]) for run in executed_runs],
        "summary_stable": summary_stable,
        "file_hashes_stable": file_hashes_stable,
        "metadata_path": str(metadata_path),
        "bundle_directory": str(metadata["bundle_layout"]["bundle_directory"]),
        "bundle_id": str(metadata["bundle_id"]),
        "run_spec_hash": str(metadata["run_spec_hash"]),
        "runtime_family": str(wave_summary["morphology_runtime"]["runtime_family"]),
        "root_morphology_classes": discovered_root_classes,
        "projection_routes": projection_routes,
        "coupling_event_route_ids": event_routes,
        "mixed_route_component_count": int(wave_summary["coupling"]["mixed_route_component_count"]),
        "point_root_runtime_metadata": {
            "baseline_family": str(root_payloads[303]["runtime_metadata"]["baseline_family"]),
            "projection_layout": str(root_payloads[303]["runtime_metadata"]["projection_layout"]),
        },
        "shared_readout_ids": list(shared_payload["readout_ids"]),
        "missing_shared_artifacts": missing_shared_artifacts,
        "missing_wave_artifacts": missing_wave_artifacts,
        "file_hashes": first_hashes,
        "execution_command": str(first["command"]),
        "provenance_coupling_hash": "" if provenance_coupling_hash is None else str(provenance_coupling_hash),
    }
    write_json(audit, commands_dir / "mixed_execution_audit.json")
    return audit


def _execute_visualization_audit(
    *,
    fixture: Mapping[str, Any],
    execution_audit: Mapping[str, Any],
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    metadata_path = execution_audit.get("metadata_path")
    if not metadata_path:
        issues.append(
            _issue(
                "blocking",
                "Visualization audit could not start because the mixed execution audit did not produce a metadata path.",
            )
        )
        audit = {
            "overall_status": "fail",
            "issues": issues,
        }
        write_json(audit, commands_dir / "visualization_audit.json")
        return audit

    command = [
        python_executable,
        str(repo_root / "scripts" / "17_visualize_simulator_results.py"),
        "--bundle-metadata",
        str(metadata_path),
        "--output-dir",
        str(output_dir.resolve()),
    ]
    first = _run_command(name="mixed_visualization_first", command=command, cwd=repo_root)
    second = _run_command(name="mixed_visualization_second", command=command, cwd=repo_root)
    write_json(first, commands_dir / "mixed_visualization_first.json")
    write_json(second, commands_dir / "mixed_visualization_second.json")
    if first["status"] != "pass" or second["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                "The shipped simulator visualization command did not execute successfully for the mixed-fidelity result bundle.",
            )
        )
        audit = {
            "overall_status": "fail",
            "issues": issues,
        }
        write_json(audit, commands_dir / "visualization_audit.json")
        return audit

    first_summary = first.get("parsed_summary", {})
    second_summary = second.get("parsed_summary", {})
    summary_stable = first_summary == second_summary
    report_path = Path(first_summary["report_path"]).resolve()
    summary_path = Path(first_summary["summary_path"]).resolve()
    artifact_hashes_stable = (
        _hash_file(report_path) == _hash_file(Path(second_summary["report_path"]).resolve())
        and _hash_file(summary_path) == _hash_file(Path(second_summary["summary_path"]).resolve())
    )
    if not summary_stable or not artifact_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated mixed-fidelity visualization runs did not remain byte-stable.",
            )
        )

    report_html = report_path.read_text(encoding="utf-8")
    summary_payload = load_json(summary_path)
    required_snippets = (
        "101:surface_neuron",
        "202:skeleton_neuron",
        "303:point_neuron",
        "404:point_neuron",
        "Root 202 skeleton_neuron projection (normalized)",
        "Root 303 point_neuron projection (normalized)",
        "Root 404 point_neuron projection (normalized)",
    )
    missing_snippets = [snippet for snippet in required_snippets if snippet not in report_html]
    if missing_snippets:
        issues.append(
            _issue(
                "blocking",
                f"The mixed-fidelity visualization report is missing mixed-class root traces or labels {missing_snippets!r}.",
            )
        )

    bundle_records = list(summary_payload.get("compared_bundles", []))
    root_classes = []
    if bundle_records:
        root_classes = list(bundle_records[0].get("root_morphology_classes", []))
    if root_classes != [
        SURFACE_NEURON_CLASS,
        SKELETON_NEURON_CLASS,
        POINT_NEURON_CLASS,
        POINT_NEURON_CLASS,
    ]:
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity visualization summary no longer reports the expected per-root morphology classes.",
            )
        )

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "summary_stable": summary_stable,
        "artifact_hashes_stable": artifact_hashes_stable,
        "output_dir": str(output_dir.resolve()),
        "report_path": str(report_path),
        "report_file_url": str(first_summary.get("report_file_url", report_path.as_uri())),
        "summary_path": str(summary_path),
        "summary_file_url": str(first_summary.get("summary_file_url", summary_path.as_uri())),
        "root_morphology_classes": root_classes,
        "viewer_is_self_contained": bool(first_summary.get("viewer_is_self_contained", True)),
        "viewer_open_hint": str(
            first_summary.get(
                "viewer_open_hint",
                "Open report_file_url directly in your browser; no local server is required.",
            )
        ),
        "command": str(first["command"]),
    }
    write_json(audit, commands_dir / "visualization_audit.json")
    return audit


def _execute_mixed_fidelity_inspection_audit(
    *,
    fixture: Mapping[str, Any],
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    command = [
        python_executable,
        str(repo_root / "scripts" / "18_mixed_fidelity_inspection.py"),
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(fixture["fixture_manifest_path"]),
        "--schema",
        str(repo_root / "schemas" / "milestone_1_experiment_manifest.schema.json"),
        "--design-lock",
        str(repo_root / "config" / "milestone_1_design_lock.yaml"),
        "--arm-id",
        "surface_wave_intact",
        "--output-dir",
        str(output_dir.resolve()),
    ]
    first = _run_command(name="mixed_inspection_first", command=command, cwd=repo_root)
    second = _run_command(name="mixed_inspection_second", command=command, cwd=repo_root)
    write_json(first, commands_dir / "mixed_inspection_first.json")
    write_json(second, commands_dir / "mixed_inspection_second.json")
    if first["status"] != "pass" or second["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                "The shipped mixed-fidelity inspection command did not execute successfully for the readiness fixture.",
            )
        )
        audit = {
            "overall_status": "fail",
            "issues": issues,
        }
        write_json(audit, commands_dir / "inspection_audit.json")
        return audit

    first_summary = first.get("parsed_summary", {})
    second_summary = second.get("parsed_summary", {})
    summary_stable = first_summary == second_summary
    report_path = Path(first_summary["report_path"]).resolve()
    summary_path = Path(first_summary["summary_path"]).resolve()
    roots_csv_path = Path(first_summary["roots_csv_path"]).resolve()
    artifact_hashes_stable = (
        _hash_file(report_path) == _hash_file(Path(second_summary["report_path"]).resolve())
        and _hash_file(summary_path) == _hash_file(Path(second_summary["summary_path"]).resolve())
        and _hash_file(roots_csv_path) == _hash_file(Path(second_summary["roots_csv_path"]).resolve())
    )
    if not summary_stable or not artifact_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated mixed-fidelity inspection runs did not remain deterministic.",
            )
        )

    reference_roots = list(first_summary.get("reference_roots", []))
    if reference_roots != [
        {
            "root_id": int(fixture["reference_root_id"]),
            "reference_morphology_class": SURFACE_NEURON_CLASS,
            "reference_source": "policy_recommendation",
        }
    ]:
        issues.append(
            _issue(
                "review",
                "The mixed-fidelity inspection no longer targets the policy-recommended surface promotion for root 303.",
            )
        )
    if list(first_summary.get("blocked_root_ids", [])):
        issues.append(
            _issue(
                "blocking",
                "The mixed-fidelity inspection left one or more readiness-fixture roots unresolved.",
            )
        )
    if list(first_summary.get("blocking_root_ids", [])):
        issues.append(
            _issue(
                "review",
                "The mixed-fidelity inspection recommends promoting one or more readiness-fixture surrogates before downstream scientific comparisons depend on them.",
            )
        )
    if list(first_summary.get("review_root_ids", [])):
        issues.append(
            _issue(
                "review",
                "The mixed-fidelity inspection still flags at least one readiness-fixture root for promotion review.",
            )
        )

    audit = {
        "overall_status": (
            "fail"
            if any(str(item.get("severity")) == "blocking" for item in issues)
            else "review"
            if issues
            else "pass"
        ),
        "issues": issues,
        "inspection_summary_status": str(first_summary["overall_status"]),
        "summary_stable": summary_stable,
        "artifact_hashes_stable": artifact_hashes_stable,
        "output_dir": str(output_dir.resolve()),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "roots_csv_path": str(roots_csv_path),
        "reference_roots": reference_roots,
        "review_root_ids": copy.deepcopy(first_summary.get("review_root_ids", [])),
        "blocking_root_ids": copy.deepcopy(first_summary.get("blocking_root_ids", [])),
        "recommended_promotion_root_ids": copy.deepcopy(
            first_summary.get("recommended_promotion_root_ids", [])
        ),
        "command": str(first["command"]),
    }
    write_json(audit, commands_dir / "inspection_audit.json")
    return audit


def _build_workflow_coverage(
    *,
    fixture_verification: Mapping[str, Any],
    manifest_plan_audit: Mapping[str, Any],
    mixed_execution_audit: Mapping[str, Any],
    visualization_audit: Mapping[str, Any],
    inspection_audit: Mapping[str, Any],
    documentation_audit: Mapping[str, Any],
) -> dict[str, bool]:
    return {
        "fixture_suite_passed": str(fixture_verification.get("status", "")) == "pass",
        "mixed_fidelity_plan_verified": str(manifest_plan_audit["overall_status"]) == "pass",
        "mixed_execution_verified": str(mixed_execution_audit["overall_status"]) == "pass",
        "mixed_serialization_verified": bool(mixed_execution_audit.get("metadata_path")),
        "mixed_result_viewer_verified": str(visualization_audit["overall_status"]) == "pass",
        "surrogate_inspection_verified": str(inspection_audit["overall_status"]) != "fail",
        "documentation_verified": str(documentation_audit["overall_status"]) == "pass",
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    audits: dict[str, Any] = {}
    issues: list[dict[str, str]] = []
    for relative_path, required_snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        doc_path = repo_root / relative_path
        if not doc_path.exists():
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing, so the Milestone 11 readiness workflow is not documented there.",
                )
            )
            audits[relative_path] = {
                "status": "fail",
                "path": str(doc_path.resolve()),
                "missing_snippets": list(required_snippets),
            }
            continue
        content = doc_path.read_text(encoding="utf-8")
        missing_snippets = [snippet for snippet in required_snippets if snippet not in content]
        if missing_snippets:
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing the Milestone 11 readiness snippets {missing_snippets!r}.",
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


def _capture_mixed_execution_hashes(metadata: Mapping[str, Any]) -> dict[str, str]:
    bundle_paths = discover_simulator_result_bundle_paths(metadata)
    extension_paths = {
        item["artifact_id"]: Path(str(item["path"])).resolve()
        for item in discover_simulator_extension_artifacts(metadata)
    }
    file_paths = {
        METADATA_JSON_KEY: bundle_paths[METADATA_JSON_KEY].resolve(),
        STATE_SUMMARY_KEY: bundle_paths[STATE_SUMMARY_KEY].resolve(),
        READOUT_TRACES_KEY: bundle_paths[READOUT_TRACES_KEY].resolve(),
        METRICS_TABLE_KEY: bundle_paths[METRICS_TABLE_KEY].resolve(),
        STRUCTURED_LOG_ARTIFACT_ID: extension_paths[STRUCTURED_LOG_ARTIFACT_ID],
        EXECUTION_PROVENANCE_ARTIFACT_ID: extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID],
        UI_COMPARISON_PAYLOAD_ARTIFACT_ID: extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID],
        SURFACE_WAVE_SUMMARY_ARTIFACT_ID: extension_paths[SURFACE_WAVE_SUMMARY_ARTIFACT_ID],
        SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID: extension_paths[SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID],
        MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID: extension_paths[MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID],
        SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID: extension_paths[SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID],
    }
    return {
        name: _hash_file(path)
        for name, path in sorted(file_paths.items())
    }


def _default_surface_wave_verification_config() -> dict[str, Any]:
    return {
        "parameter_preset": "milestone_11_mixed_verification",
        "propagation": {
            "wave_speed_sq_scale": 0.1,
            "restoring_strength_per_ms2": 0.05,
        },
        "damping": {
            "gamma_per_ms": 0.1,
        },
        "recovery": {
            "mode": "disabled",
        },
        "nonlinearity": {
            "mode": "none",
        },
        "anisotropy": {
            "mode": "isotropic",
        },
        "branching": {
            "mode": "disabled",
        },
    }


def _default_mixed_fidelity_verification_config() -> dict[str, Any]:
    return {
        "assignment_policy": {
            "promotion_mode": "recommend_from_policy",
            "demotion_mode": "disabled",
            "recommendation_rules": [
                {
                    "rule_id": "promote_patch_dense_surrogate",
                    "minimum_morphology_class": SURFACE_NEURON_CLASS,
                    "root_ids": [303],
                    "topology_conditions": ["intact"],
                    "arm_tags_any": ["surface_wave"],
                    "descriptor_thresholds": {
                        "patch_count": {
                            "gte": 2,
                        }
                    },
                }
            ],
        }
    }


def _write_fixture_manifest(
    *,
    source_manifest_path: Path,
    output_path: Path,
) -> Path:
    manifest_payload = load_yaml(source_manifest_path)
    fidelity_assignment = {
        "default_morphology_class": POINT_NEURON_CLASS,
        "root_overrides": [
            {"root_id": 101, "morphology_class": SURFACE_NEURON_CLASS},
            {"root_id": 202, "morphology_class": SKELETON_NEURON_CLASS},
        ],
    }
    for arm in manifest_payload["comparison_arms"]:
        if arm["model_mode"] == "surface_wave":
            arm["fidelity_assignment"] = copy.deepcopy(fidelity_assignment)
    output_path.write_text(
        yaml.safe_dump(manifest_payload, sort_keys=False),
        encoding="utf-8",
    )
    return output_path.resolve()


def _write_mixed_execution_geometry_manifest(*, output_dir: Path, manifest_path: Path) -> None:
    root_specs = _default_root_specs()
    root_ids = [int(item["root_id"]) for item in root_specs]
    coupling_dir = output_dir / "processed_coupling"
    local_synapse_registry_path = coupling_dir / "synapse_registry.csv"
    local_synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"synapse_row_id": "fixture-1", "pre_root_id": 101, "post_root_id": 202},
            {"synapse_row_id": "fixture-2", "pre_root_id": 202, "post_root_id": 404},
            {"synapse_row_id": "fixture-3", "pre_root_id": 404, "post_root_id": 101},
        ]
    ).to_csv(local_synapse_registry_path, index=False)

    coupling_paths_by_root = {
        root_id: build_root_coupling_bundle_paths(
            root_id,
            processed_coupling_dir=coupling_dir,
        )
        for root_id in root_ids
    }
    for bundle_paths in coupling_paths_by_root.values():
        _write_placeholder_file(bundle_paths.incoming_anchor_map_path)
        _write_placeholder_file(bundle_paths.outgoing_anchor_map_path)
        _write_placeholder_file(bundle_paths.coupling_index_path)

    edge_specs = [
        {
            "pre_root_id": 101,
            "post_root_id": 202,
            "source_anchor": _surface_anchor(root_id=101, anchor_index=0, x=0.0),
            "target_anchor": _skeleton_anchor(root_id=202, node_id=2, x=1.0),
            "signed_weight_total": 1.5,
            "delay_ms": 10.0,
            "sign_label": "excitatory",
        },
        {
            "pre_root_id": 202,
            "post_root_id": 404,
            "source_anchor": _skeleton_anchor(root_id=202, node_id=2, x=1.0),
            "target_anchor": _point_anchor(root_id=404, x=0.0),
            "signed_weight_total": 1.0,
            "delay_ms": 0.0,
            "sign_label": "excitatory",
        },
        {
            "pre_root_id": 404,
            "post_root_id": 101,
            "source_anchor": _point_anchor(root_id=404, x=0.0),
            "target_anchor": _surface_anchor(root_id=101, anchor_index=1, x=1.0),
            "signed_weight_total": -0.5,
            "delay_ms": 0.0,
            "sign_label": "inhibitory",
        },
    ]
    for edge_spec in edge_specs:
        edge_path = coupling_dir / "edges" / (
            f"{edge_spec['pre_root_id']}__to__{edge_spec['post_root_id']}_coupling.npz"
        )
        _write_route_edge_bundle(edge_bundle_path=edge_path, **edge_spec)

    bundle_records = {}
    for spec in root_specs:
        root_id = int(spec["root_id"])
        asset_profile = str(spec["asset_profile"])
        asset_statuses = _asset_statuses_for_profile(asset_profile)
        bundle_paths = build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=output_dir / "meshes_raw",
            skeletons_raw_dir=output_dir / "skeletons_raw",
            processed_mesh_dir=output_dir / "processed_meshes",
            processed_graph_dir=output_dir / "processed_graphs",
        )
        if asset_profile == "surface":
            _write_placeholder_file(bundle_paths.simplified_mesh_path)
        if asset_statuses[RAW_SKELETON_KEY] == ASSET_STATUS_READY:
            _write_skeleton_fixture(bundle_paths.raw_skeleton_path)

        operator_bundle_metadata = _write_fixture_operator_bundle(
            bundle_paths=bundle_paths,
            root_id=root_id,
            asset_statuses=asset_statuses,
            asset_profile=asset_profile,
        )
        if root_id == 303:
            _write_policy_descriptor_fixture(bundle_paths.descriptor_sidecar_path, root_id=root_id)

        coupling_metadata = build_coupling_bundle_metadata(
            root_id=root_id,
            processed_coupling_dir=coupling_dir,
            local_synapse_registry_status=ASSET_STATUS_READY,
            incoming_anchor_map_status=ASSET_STATUS_READY,
            outgoing_anchor_map_status=ASSET_STATUS_READY,
            coupling_index_status=ASSET_STATUS_READY,
            edge_bundles=[
                build_edge_coupling_bundle_reference(
                    root_id=root_id,
                    pre_root_id=edge_spec["pre_root_id"],
                    post_root_id=edge_spec["post_root_id"],
                    processed_coupling_dir=coupling_dir,
                    status=ASSET_STATUS_READY,
                )
                for edge_spec in edge_specs
                if root_id in (edge_spec["pre_root_id"], edge_spec["post_root_id"])
            ],
        )
        bundle_records[root_id] = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": str(spec["cell_type"]),
                "project_role": str(spec["project_role"]),
                "materialization_version": "783",
                "snapshot_version": "783",
            },
            operator_bundle_metadata=operator_bundle_metadata,
            coupling_bundle_metadata=coupling_metadata,
            processed_coupling_dir=coupling_dir,
        )

    write_geometry_manifest(
        manifest_path=manifest_path,
        bundle_records=bundle_records,
        dataset_name="public",
        materialization_version=783,
        meshing_config_snapshot=_meshing_config_snapshot(),
        processed_coupling_dir=coupling_dir,
    )


def _default_root_specs() -> list[dict[str, Any]]:
    return [
        {
            "root_id": 101,
            "cell_type": "fixture_surface_101",
            "project_role": "surface_simulated",
            "asset_profile": "surface",
        },
        {
            "root_id": 202,
            "cell_type": "fixture_skeleton_202",
            "project_role": "skeleton_simulated",
            "asset_profile": "skeleton",
        },
        {
            "root_id": 303,
            "cell_type": "fixture_surrogate_303",
            "project_role": "surface_simulated",
            "asset_profile": "surface",
        },
        {
            "root_id": 404,
            "cell_type": "fixture_point_router_404",
            "project_role": "point_simulated",
            "asset_profile": "point",
        },
    ]


def _asset_statuses_for_profile(asset_profile: str) -> dict[str, str]:
    if asset_profile == "surface":
        asset_statuses = default_asset_statuses(fetch_skeletons=False)
        asset_statuses.update(
            {
                SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
                FINE_OPERATOR_KEY: ASSET_STATUS_READY,
                COARSE_OPERATOR_KEY: ASSET_STATUS_READY,
                TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
                OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
                DESCRIPTOR_SIDECAR_KEY: ASSET_STATUS_READY,
            }
        )
        return asset_statuses
    if asset_profile == "skeleton":
        asset_statuses = default_asset_statuses(fetch_skeletons=True)
        asset_statuses.update(
            {
                RAW_SKELETON_KEY: ASSET_STATUS_READY,
            }
        )
        return asset_statuses
    if asset_profile == "point":
        return default_asset_statuses(fetch_skeletons=False)
    raise ValueError(f"Unsupported readiness fixture asset_profile {asset_profile!r}.")


def _meshing_config_snapshot() -> dict[str, object]:
    return {
        "fetch_skeletons": False,
        "operator_assembly": {
            "version": "operator_assembly.v1",
            "boundary_condition": {
                "version": "boundary_condition.v1",
                "mode": "closed_surface_zero_flux",
            },
            "anisotropy": {
                "version": "anisotropy.v1",
                "model": "local_tangent_diagonal",
                "default_tensor": [1.2, 0.8],
            },
        },
    }


def _write_fixture_operator_bundle(
    *,
    bundle_paths: Any,
    root_id: int,
    asset_statuses: dict[str, str],
    asset_profile: str,
) -> dict[str, Any]:
    if asset_profile != "surface":
        return build_operator_bundle_metadata(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            meshing_config_snapshot=_meshing_config_snapshot(),
        )

    fine_operator = sp.csr_matrix(
        [
            [1.0, -1.0, 0.0],
            [-1.0, 2.0, -1.0],
            [0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(fine_operator).items()
            },
        },
        bundle_paths.fine_operator_path,
    )
    coarse_operator = sp.csr_matrix(
        [
            [1.0, -1.0],
            [-1.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(coarse_operator).items()
            },
        },
        bundle_paths.coarse_operator_path,
    )
    restriction = sp.csr_matrix(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.5, 0.5],
        ],
        dtype=np.float64,
    )
    prolongation = sp.csr_matrix(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"restriction_{key}": value
                for key, value in serialize_sparse_matrix(restriction).items()
            },
            **{
                f"prolongation_{key}": value
                for key, value in serialize_sparse_matrix(prolongation).items()
            },
            **{
                f"normalized_restriction_{key}": value
                for key, value in serialize_sparse_matrix(restriction).items()
            },
            **{
                f"normalized_prolongation_{key}": value
                for key, value in serialize_sparse_matrix(prolongation).items()
            },
        },
        bundle_paths.transfer_operator_path,
    )
    write_json({"descriptor_version": 1, "root_id": root_id}, bundle_paths.descriptor_sidecar_path)
    write_json({"qa_version": 1, "root_id": root_id}, bundle_paths.qa_sidecar_path)
    operator_bundle_metadata = build_operator_bundle_metadata(
        bundle_paths=bundle_paths,
        asset_statuses=asset_statuses,
        meshing_config_snapshot=_meshing_config_snapshot(),
        realized_operator_metadata={
            "realization_mode": "fixture_mass_normalized_surface_operator",
            "operator_assembly": _meshing_config_snapshot()["operator_assembly"],
            "preferred_discretization_family": "triangle_mesh_cotangent_fem",
            "discretization_family": "triangle_mesh_cotangent_fem",
            "mass_treatment": "lumped_mass",
            "normalization": "mass_normalized",
            "boundary_condition_mode": "closed_surface_zero_flux",
            "anisotropy_model": "local_tangent_diagonal",
            "fallback_policy": {
                "allowed": False,
                "used": False,
                "reason": "",
                "fallback_discretization_family": "triangle_mesh_cotangent_fem",
            },
            "geodesic_neighborhood": {
                "mode": "fixture_patch_neighbors",
            },
            "transfer_restriction_mode": "mass_weighted_patch_average",
            "transfer_prolongation_mode": "constant_on_patch",
            "transfer_preserves_mass_or_area_totals": True,
            "normalized_state_transfer_available": True,
        },
    )
    write_json(operator_bundle_metadata, bundle_paths.operator_metadata_path)
    return operator_bundle_metadata


def _write_policy_descriptor_fixture(path: Path, *, root_id: int) -> None:
    write_json(
        {
            "root_id": int(root_id),
            "descriptor_version": "geometry_descriptors.v1",
            "patch_count": 4,
            "n_vertices": 6,
            "n_faces": 4,
            "surface_graph_edge_count": 8,
            "derived_relations": {
                "simplified_to_raw_face_ratio": 0.5,
                "simplified_to_raw_vertex_ratio": 0.5,
            },
            "representations": {
                "coarse_patches": {
                    "max_patch_vertex_fraction": 0.4,
                    "singleton_patch_fraction": 0.0,
                },
                "skeleton": {
                    "available": True,
                    "node_count": 3,
                    "segment_count": 2,
                    "branch_point_count": 0,
                    "leaf_count": 2,
                    "total_cable_length": 2.0,
                },
            },
        },
        path,
    )


def _write_skeleton_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "1 1 0.0 0.0 0.0 1.0 -1",
                "2 3 1.0 0.0 0.0 0.5 1",
                "3 3 2.0 0.0 0.0 0.5 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_placeholder_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _surface_anchor(*, root_id: int, anchor_index: int, x: float) -> dict[str, Any]:
    return {
        "anchor_table_index": 0,
        "root_id": int(root_id),
        "anchor_mode": "surface_patch_cloud",
        "anchor_type": "surface_patch",
        "anchor_resolution": "coarse_patch",
        "anchor_index": int(anchor_index),
        "anchor_x": float(x),
        "anchor_y": 0.0,
        "anchor_z": 0.0,
    }


def _skeleton_anchor(*, root_id: int, node_id: int, x: float) -> dict[str, Any]:
    return {
        "anchor_table_index": 0,
        "root_id": int(root_id),
        "anchor_mode": "skeleton_segment_cloud",
        "anchor_type": "skeleton_node",
        "anchor_resolution": "skeleton_node",
        "anchor_index": int(node_id),
        "anchor_x": float(x),
        "anchor_y": 0.0,
        "anchor_z": 0.0,
    }


def _point_anchor(*, root_id: int, x: float) -> dict[str, Any]:
    return {
        "anchor_table_index": 0,
        "root_id": int(root_id),
        "anchor_mode": "point_neuron_lumped",
        "anchor_type": "point_state",
        "anchor_resolution": "lumped_root_state",
        "anchor_index": 0,
        "anchor_x": float(x),
        "anchor_y": 0.0,
        "anchor_z": 0.0,
    }


def _write_route_edge_bundle(
    *,
    edge_bundle_path: Path,
    pre_root_id: int,
    post_root_id: int,
    source_anchor: dict[str, Any],
    target_anchor: dict[str, Any],
    signed_weight_total: float,
    delay_ms: float,
    sign_label: str,
) -> None:
    source_anchor_table = pd.DataFrame.from_records(
        [copy.deepcopy(source_anchor)],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    target_anchor_table = pd.DataFrame.from_records(
        [copy.deepcopy(target_anchor)],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    component_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "component_id": f"{int(pre_root_id)}__to__{int(post_root_id)}__component_0000",
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "pre_anchor_mode": str(source_anchor["anchor_mode"]),
                "post_anchor_mode": str(target_anchor["anchor_mode"]),
                "sign_label": str(sign_label),
                "sign_polarity": 1 if signed_weight_total > 0.0 else -1 if signed_weight_total < 0.0 else 0,
                "sign_representation": DEFAULT_SIGN_REPRESENTATION,
                "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                "delay_model": "fixture_delay_model",
                "delay_ms": float(delay_ms),
                "delay_bin_index": int(delay_ms),
                "delay_bin_label": f"delay_{delay_ms:.1f}",
                "delay_bin_start_ms": float(delay_ms),
                "delay_bin_end_ms": float(delay_ms),
                "aggregation_rule": DEFAULT_AGGREGATION_RULE,
                "source_anchor_count": 1,
                "target_anchor_count": 1,
                "synapse_count": 1,
                "signed_weight_total": float(signed_weight_total),
                "absolute_weight_total": float(abs(signed_weight_total)),
                "confidence_sum": 1.0,
                "confidence_mean": 1.0,
                "source_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "target_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "source_normalization_total": 1.0,
                "target_normalization_total": 1.0,
            }
        ],
        columns=list(COMPONENT_COLUMN_TYPES),
    )
    source_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    target_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    component_synapse_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "synapse_row_id": "fixture#0",
                "source_row_number": 1,
                "synapse_id": "fixture-0",
                "sign_label": str(sign_label),
                "signed_weight": float(signed_weight_total),
                "absolute_weight": float(abs(signed_weight_total)),
                "delay_ms": float(delay_ms),
                "delay_bin_index": int(delay_ms),
                "delay_bin_label": f"delay_{delay_ms:.1f}",
            }
        ],
        columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES),
    )
    empty_synapse_table = pd.DataFrame()
    bundle = EdgeCouplingBundle(
        pre_root_id=int(pre_root_id),
        post_root_id=int(post_root_id),
        status="ready",
        topology_family=DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        kernel_family=SEPARABLE_RANK_ONE_CLOUD_KERNEL,
        sign_representation=DEFAULT_SIGN_REPRESENTATION,
        delay_representation=DEFAULT_DELAY_REPRESENTATION,
        delay_model="fixture_delay_model",
        delay_model_parameters={
            "base_delay_ms": 0.0,
            "velocity_distance_units_per_ms": 1.0,
            "delay_bin_size_ms": 1.0,
        },
        aggregation_rule=DEFAULT_AGGREGATION_RULE,
        missing_geometry_policy="fail_fixture",
        source_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        target_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        synapse_table=empty_synapse_table.copy(),
        component_table=component_table,
        blocked_synapse_table=empty_synapse_table.copy(),
        source_anchor_table=source_anchor_table,
        target_anchor_table=target_anchor_table,
        source_cloud_table=source_cloud_table,
        target_cloud_table=target_cloud_table,
        component_synapse_table=component_synapse_table,
    )
    _write_edge_coupling_bundle_npz(
        path=edge_bundle_path,
        bundle=bundle,
    )


def _render_milestone11_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary.get(FOLLOW_ON_READINESS_KEY, {}))
    plan_audit = dict(summary.get("manifest_plan_audit", {}))
    execution_audit = dict(summary.get("mixed_execution_audit", {}))
    visualization_audit = dict(summary.get("visualization_audit", {}))
    inspection_audit = dict(summary.get("inspection_audit", {}))
    documentation_audit = dict(summary.get("documentation_audit", {}))
    intact_plan = dict(plan_audit.get("intact_mixed_fidelity_plan", {}))
    workflow_coverage = dict(summary.get("workflow_coverage", {}))
    remaining_risks = list(summary.get("remaining_risks", []))
    follow_on_issues = list(summary.get("follow_on_issues", []))

    lines = [
        "# Milestone 11 Readiness Report",
        "",
        "## Verdict",
        "",
        f"- Readiness verdict: `{readiness.get('status', '')}`",
        f"- Local mixed-fidelity gate: `{readiness.get('local_mixed_fidelity_gate', '')}`",
        f"- Ready for downstream readout, validation, and UI work: `{readiness.get(READY_FOR_FOLLOW_ON_WORK_KEY, False)}`",
        f"- Verification command: `{summary.get('documented_verification_command', '')}`",
        f"- Explicit command: `{summary.get('explicit_verification_command', '')}`",
        "",
        "## Verification Surface",
        "",
        f"- Focused fixture suite: `{summary['fixture_verification'].get('status', '')}`",
        f"- Representative fixture manifest: `{summary.get('verification_fixture_manifest_path', '')}`",
        f"- Planned mixed root classes: `{intact_plan.get('resolved_class_counts', {})}`",
        f"- Executed mixed routes: `{execution_audit.get('projection_routes', [])}`",
        f"- Visualization audit: `{visualization_audit.get('overall_status', '')}`",
        f"- Visualization report: `{visualization_audit.get('report_path', '')}`",
        f"- Visualization open URL: `{visualization_audit.get('report_file_url', '')}`",
        f"- Visualization open hint: {visualization_audit.get('viewer_open_hint', '')}",
        f"- Inspection audit: `{inspection_audit.get('inspection_summary_status', inspection_audit.get('overall_status', ''))}`",
        f"- Documentation audit: `{documentation_audit.get('overall_status', '')}`",
        "",
        "## Workflow Coverage",
        "",
    ]
    for key, value in workflow_coverage.items():
        lines.append(f"- {key.replace('_', ' ')}: `{value}`")

    lines.extend(
        [
            "",
            "## Mixed-Fidelity Planning",
            "",
            f"- Surface-wave arm count: `{plan_audit.get('surface_wave_arm_count', 0)}`",
            f"- Surface-wave topology conditions: `{plan_audit.get('surface_wave_topology_conditions', [])}`",
            f"- Promotion recommendations: `{intact_plan.get('promotion_recommendation_root_ids', [])}`",
            f"- Surface operator roots: `{intact_plan.get('operator_root_ids', [])}`",
            f"- Skeleton asset roots: `{intact_plan.get('skeleton_asset_root_ids', [])}`",
            "",
            "## Mixed Execution",
            "",
            f"- Runtime family: `{execution_audit.get('runtime_family', '')}`",
            f"- Root morphology classes: `{execution_audit.get('root_morphology_classes', [])}`",
            f"- Projection routes: `{execution_audit.get('projection_routes', [])}`",
            f"- Mixed-route component count: `{execution_audit.get('mixed_route_component_count', 0)}`",
            f"- Repeated command summary stable: `{execution_audit.get('summary_stable', False)}`",
            f"- Repeated bundle bytes stable: `{execution_audit.get('file_hashes_stable', False)}`",
            "",
            "## Inspection Tooling",
            "",
            f"- Visualization root classes: `{visualization_audit.get('root_morphology_classes', [])}`",
            f"- Visualization artifacts stable: `{visualization_audit.get('artifact_hashes_stable', False)}`",
            f"- Inspection review roots: `{inspection_audit.get('review_root_ids', [])}`",
            f"- Inspection blocking roots: `{inspection_audit.get('blocking_root_ids', [])}`",
            f"- Recommended promotion roots after inspection: `{inspection_audit.get('recommended_promotion_root_ids', [])}`",
            "",
            "## Remaining Risks",
            "",
        ]
    )
    for risk in remaining_risks:
        lines.append(f"- {risk}")

    lines.extend(
        [
            "",
            "## Deferred Follow-On Issues",
            "",
        ]
    )
    for issue in follow_on_issues:
        lines.append(f"- `{issue.get('ticket_id', '')}`: {issue.get('title', '')}")
        lines.append(f"  Reproduction: {issue.get('reproduction', '')}")
    return "\n".join(lines).rstrip() + "\n"
