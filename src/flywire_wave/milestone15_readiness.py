from __future__ import annotations

import copy
import hashlib
import importlib
import json
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .config import REPO_ROOT, load_config
from .experiment_suite_execution import load_experiment_suite_execution_state
from .experiment_suite_packaging import (
    discover_experiment_suite_package_paths,
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
)
from .experiment_suite_planning import (
    build_experiment_suite_metadata,
    resolve_experiment_suite_plan,
)
from .io_utils import ensure_dir, write_json
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)


MILESTONE15_READINESS_REPORT_VERSION = "milestone15_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_experiment_suite_contract",
    "tests.test_experiment_ablation_transforms",
    "tests.test_experiment_suite_planning",
    "tests.test_experiment_suite_execution",
    "tests.test_experiment_suite_packaging",
    "tests.test_experiment_suite_aggregation",
    "tests.test_experiment_suite_reporting",
    "tests.test_experiment_comparison_analysis",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone15-readiness",
        "scripts/34_milestone15_readiness.py",
        "suite-aggregate",
        "scripts/31_run_experiment_suite.py",
        "scripts/32_suite_aggregation.py",
        "scripts/33_suite_report.py",
        "milestone_15_readiness.md",
        "milestone_15_readiness.json",
    ),
    "docs/pipeline_notes.md": (
        "make milestone15-readiness",
        "scripts/34_milestone15_readiness.py",
        "suite-aggregate",
        "scripts/31_run_experiment_suite.py",
        "scripts/32_suite_aggregation.py",
        "scripts/33_suite_report.py",
        "milestone_15_readiness.md",
        "milestone_15_readiness.json",
    ),
    "docs/experiment_orchestration_design.md": (
        "scripts/34_milestone15_readiness.py",
        "suite-aggregate",
        "scripts/32_suite_aggregation.py",
        "scripts/33_suite_report.py",
        "Milestone 15 readiness",
    ),
    "Makefile": (
        "milestone15-readiness",
        "suite-aggregate",
        "scripts/34_milestone15_readiness.py",
        "scripts/32_suite_aggregation.py",
    ),
}

FOLLOW_ON_TICKETS = (
    {
        "ticket_id": "FW-M15-FOLLOW-001",
        "severity": "blocking",
        "title": "Teach no-waves and waves-only ablations to rematerialize coupling assets for demoted roots",
        "summary": (
            "The readiness pass now proves that seeded manifest-driven shuffle suites can run "
            "through deterministic simulation staging, but a representative `no_waves` suite "
            "still fails because demoted point-neuron roots inherit surface-patch coupling bundles."
        ),
        "reproduction_notes": (
            "Run `make milestone15-readiness`, then inspect the recorded `no_waves_simulation_suite` "
            "command under `data/processed/milestone_15_verification/simulator_results/readiness/milestone_15/commands/`. "
            "The first failed work item reports that the hybrid coupling component still requires "
            "`surface_patch_cloud` anchors after the ablation demotes the roots to `point_neuron`."
        ),
    },
    {
        "ticket_id": "FW-M15-FOLLOW-002",
        "severity": "blocking",
        "title": "Bridge manifest-driven suite analysis onto a bundle set that satisfies the Milestone 12 condition contract",
        "summary": (
            "The readiness pass also proves that the current manifest-driven full-stage suite handoff "
            "stalls at analysis because `execute_experiment_comparison_workflow` expects the richer "
            "condition coverage from Milestone 12 bundle sets, while `scripts/31_run_experiment_suite.py` "
            "currently feeds it only the direct per-suite-cell simulator outputs."
        ),
        "reproduction_notes": (
            "Run `make milestone15-readiness`, then inspect the recorded `shuffle_full_stage_suite` "
            "command under `data/processed/milestone_15_verification/simulator_results/readiness/milestone_15/commands/`. "
            "The first failed analysis work item reports missing condition coverage for the generated "
            "seeded suite bundles."
        ),
    },
)


def build_milestone15_readiness_paths(
    processed_simulator_results_dir: str | Path,
) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_15"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_15_readiness.md",
        "json_path": report_dir / "milestone_15_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
        "manifest_fixture_dir": report_dir / "generated_fixture" / "manifest_workflow",
        "review_fixture_dir": report_dir / "generated_fixture" / "review_workflow",
    }


def execute_milestone15_readiness_pass(
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
    readiness_paths = build_milestone15_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = readiness_paths["generated_fixture_dir"]
    shutil.rmtree(generated_fixture_dir, ignore_errors=True)
    ensure_dir(generated_fixture_dir)

    manifest_fixture = _materialize_manifest_fixture(
        repo_root=repo_root,
        fixture_dir=readiness_paths["manifest_fixture_dir"],
    )
    manifest_resolution_audit = _audit_manifest_resolution(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        manifest_fixture=manifest_fixture,
    )
    shuffle_simulation_audit = _audit_manifest_suite_command(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        config_path=manifest_fixture["config_path"],
        manifest_arg=("--suite-manifest", manifest_fixture["shuffle_simulation_suite_manifest"]),
        command_name="shuffle_simulation_suite",
        expected_suite_status="succeeded",
    )
    no_waves_audit = _audit_manifest_suite_command(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        config_path=manifest_fixture["config_path"],
        manifest_arg=("--suite-manifest", manifest_fixture["no_waves_simulation_suite_manifest"]),
        command_name="no_waves_simulation_suite",
        expected_suite_status="failed",
    )
    full_stage_audit = _audit_manifest_suite_command(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        config_path=manifest_fixture["config_path"],
        manifest_arg=("--suite-manifest", manifest_fixture["shuffle_full_stage_suite_manifest"]),
        command_name="shuffle_full_stage_suite",
        expected_suite_status="failed",
    )
    review_fixture = _materialize_review_fixture(
        repo_root=repo_root,
        fixture_dir=readiness_paths["review_fixture_dir"],
    )
    review_audit = _audit_review_workflow(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        package_metadata_path=review_fixture["package_metadata_path"],
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)

    issues = []
    issues.extend(manifest_resolution_audit["issues"])
    issues.extend(shuffle_simulation_audit["issues"])
    issues.extend(no_waves_audit["issues"])
    issues.extend(full_stage_audit["issues"])
    issues.extend(review_audit["issues"])
    issues.extend(documentation_audit["issues"])
    blocking_issues = [
        issue for issue in issues if str(issue.get("severity")) == "blocking"
    ]

    workflow_coverage = {
        "fixture_suite": str(fixture_verification.get("status", "")) == "pass",
        "suite_manifest_resolution": manifest_resolution_audit["overall_status"] == "pass",
        "shuffle_simulation_suite": shuffle_simulation_audit["observed_suite_status"]
        == "succeeded",
        "required_ablation_runtime": no_waves_audit["observed_suite_status"]
        == "succeeded",
        "full_stage_manifest_suite": full_stage_audit["observed_suite_status"]
        == "succeeded",
        "suite_packaging_and_indexing": review_audit["package_audit"]["overall_status"]
        == "pass",
        "suite_aggregation": review_audit["aggregation_audit"]["overall_status"] == "pass",
        "suite_report_generation": review_audit["report_audit"]["overall_status"] == "pass",
        "documentation": documentation_audit["overall_status"] == "pass",
    }

    readiness_status = "ready"
    if blocking_issues or not all(workflow_coverage.values()):
        readiness_status = READINESS_GATE_HOLD

    summary = {
        "report_version": MILESTONE15_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "documented_verification_command": "make milestone15-readiness",
        "explicit_verification_command": (
            "python scripts/34_milestone15_readiness.py "
            "--config config/milestone_15_verification.yaml"
        ),
        "verification_command_sequence": [
            "make milestone15-readiness",
            (
                "make suite-run "
                "CONFIG=data/processed/milestone_15_verification/simulator_results/"
                "readiness/milestone_15/generated_fixture/manifest_workflow/"
                "simulation_config.yaml "
                "SUITE_RUN_ARGS='--suite-manifest "
                "data/processed/milestone_15_verification/simulator_results/readiness/"
                "milestone_15/generated_fixture/manifest_workflow/shuffle_simulation_suite.yaml'"
            ),
            (
                "make suite-aggregate "
                "SUITE_AGGREGATE_ARGS='--suite-package-metadata "
                "data/processed/milestone_15_verification/simulator_results/readiness/"
                "milestone_15/generated_fixture/review_workflow/o/package/experiment_suite_package.json "
                "--table-dimension-id motion_direction'"
            ),
            (
                "make suite-report "
                "SUITE_REPORT_ARGS='--suite-package-metadata "
                "data/processed/milestone_15_verification/simulator_results/readiness/"
                "milestone_15/generated_fixture/review_workflow/o/package/experiment_suite_package.json "
                "--table-dimension-id motion_direction'"
            ),
        ],
        "fixture_verification": dict(fixture_verification),
        "manifest_resolution_audit": manifest_resolution_audit,
        "shuffle_simulation_audit": shuffle_simulation_audit,
        "no_waves_audit": no_waves_audit,
        "full_stage_audit": full_stage_audit,
        "review_audit": review_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": [
            "The manifest-driven suite probe now proves deterministic suite planning, hashed work directories, seeded shuffle-materialization, stimulus-bundle preflight, and simulation batching. It does not prove the full downstream Milestone 12 to 14 stage chain is ready for arbitrary suite cells.",
            "The packaged review fixture proves suite packaging, indexing, aggregation, plot generation, and static review delivery are deterministic and reviewable on fixture artifacts, but it still uses synthetic analysis and validation bundles rather than fresh outputs from the manifest-driven runner.",
            "Milestone 15 is therefore still an orchestration-readiness audit, not a claim that later scientific sweeps or showcase narratives are already safe to present without the blocking follow-on tickets below.",
        ],
        "follow_on_tickets": [dict(item) for item in FOLLOW_ON_TICKETS],
        "readiness_scope_note": (
            "This readiness pass deliberately splits the Milestone 15 surface in two: "
            "a representative manifest-driven suite probe for planning, scheduling, seeds, "
            "and batch simulation execution; plus a deterministic packaged-suite fixture that "
            "drives suite packaging, aggregation, and report generation through the shipped CLIs."
        ),
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_milestones": (
                ["milestone_16_showcase_mode"]
                if readiness_status != READINESS_GATE_HOLD
                else []
            ),
            "local_suite_gate": readiness_status,
            "scientific_review_boundary": (
                "Milestone 15 becomes showcase-ready only when one manifest-driven suite can "
                "carry its seeded simulation outputs all the way through analysis, validation, "
                "and reporting without hidden fixture-only assumptions."
            ),
        },
    }
    summary["readiness_verdict"] = (
        "Milestone 15 is not yet ready for Milestone 16 showcase work because the "
        "current local runner still blocks on required-ablation runtime coverage and "
        "on the full-stage analysis handoff."
    )

    write_json(summary, readiness_paths["json_path"])
    readiness_paths["markdown_path"].write_text(
        _render_markdown(summary),
        encoding="utf-8",
    )
    return summary


def _audit_manifest_resolution(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    manifest_fixture: Mapping[str, Any],
) -> dict[str, Any]:
    suite_dry_run = _run_command_capture(
        name="shuffle_simulation_suite_dry_run",
        command=[
            python_executable,
            str(repo_root / "scripts" / "31_run_experiment_suite.py"),
            "--config",
            str(manifest_fixture["config_path"]),
            "--suite-manifest",
            str(manifest_fixture["shuffle_simulation_suite_manifest"]),
            "--schema",
            str(manifest_fixture["schema_path"]),
            "--design-lock",
            str(manifest_fixture["design_lock_path"]),
            "--dry-run",
        ],
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    embedded_dry_run = _run_command_capture(
        name="embedded_shuffle_suite_dry_run",
        command=[
            python_executable,
            str(repo_root / "scripts" / "31_run_experiment_suite.py"),
            "--config",
            str(manifest_fixture["config_path"]),
            "--manifest",
            str(manifest_fixture["embedded_shuffle_simulation_manifest"]),
            "--schema",
            str(manifest_fixture["schema_path"]),
            "--design-lock",
            str(manifest_fixture["design_lock_path"]),
            "--dry-run",
        ],
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    suite_summary = dict(suite_dry_run.get("parsed_summary") or {})
    embedded_summary = dict(embedded_dry_run.get("parsed_summary") or {})
    work_item_order_match = list(suite_summary.get("work_item_order", [])) == list(
        embedded_summary.get("work_item_order", [])
    )
    stage_order_match = list(suite_summary.get("stage_order", [])) == list(
        embedded_summary.get("stage_order", [])
    )
    issues = []
    if suite_dry_run["returncode"] != 0 or embedded_dry_run["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Dry-run suite resolution command failed",
                summary="The shipped suite runner could not resolve one of the representative dry-run manifests.",
            )
        )
    if suite_summary.get("dry_run") is not True or embedded_summary.get("dry_run") is not True:
        issues.append(
            _issue(
                severity="blocking",
                title="Dry-run summary did not report dry_run=true",
                summary="The shipped suite runner no longer advertises dry-run planning clearly in its JSON summary.",
            )
        )
    if not work_item_order_match or not stage_order_match:
        issues.append(
            _issue(
                severity="blocking",
                title="Suite-manifest and embedded-manifest planning diverged",
                summary="The representative suite block no longer resolves to the same deterministic schedule through the two supported manifest entrypoints.",
            )
        )

    plan = resolve_experiment_suite_plan(
        config_path=manifest_fixture["config_path"],
        suite_manifest_path=manifest_fixture["shuffle_simulation_suite_manifest"],
        schema_path=manifest_fixture["schema_path"],
        design_lock_path=manifest_fixture["design_lock_path"],
    )
    seeded_shuffle = next(
        item
        for item in plan["cell_catalog"]
        if item["lineage_kind"] == "seeded_ablation_variant"
        and any(
            reference["ablation_family_id"] == "shuffle_morphology"
            for reference in item.get("ablation_references", [])
        )
    )
    hashed_cell_roots = all(
        Path(item["output_roots"]["cell_root"]).name.startswith("cell_")
        for item in plan["cell_catalog"]
    )
    return {
        "overall_status": "pass" if not issues else "fail",
        "suite_dry_run": suite_dry_run,
        "embedded_dry_run": embedded_dry_run,
        "work_item_order_match": work_item_order_match,
        "stage_order_match": stage_order_match,
        "suite_spec_hash_match": suite_summary.get("suite_spec_hash")
        == embedded_summary.get("suite_spec_hash"),
        "work_item_count": len(plan["work_item_catalog"]),
        "cell_count": len(plan["cell_catalog"]),
        "hashed_cell_roots": hashed_cell_roots,
        "seeded_shuffle_example": {
            "suite_cell_id": str(seeded_shuffle["suite_cell_id"]),
            "simulation_seed": int(seeded_shuffle["simulation_seed"]),
            "perturbation_seed": int(
                seeded_shuffle["ablation_references"][0]["perturbation_seed"]
            ),
        },
        "issues": issues,
    }


def _audit_manifest_suite_command(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    config_path: Path,
    manifest_arg: tuple[str, Path],
    command_name: str,
    expected_suite_status: str,
) -> dict[str, Any]:
    command = [
        python_executable,
        str(repo_root / "scripts" / "31_run_experiment_suite.py"),
        "--config",
        str(config_path),
        manifest_arg[0],
        str(manifest_arg[1]),
        "--schema",
        str(repo_root / "schemas" / "milestone_1_experiment_manifest.schema.json"),
        "--design-lock",
        str(repo_root / "config" / "milestone_1_design_lock.yaml"),
    ]
    result = _run_command_capture(
        name=command_name,
        command=command,
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    parsed = dict(result.get("parsed_summary") or {})
    suite_root = (
        None
        if not isinstance(parsed.get("state_path"), str)
        else Path(parsed["state_path"]).resolve().parent
    )
    state = (
        None
        if suite_root is None
        else load_experiment_suite_execution_state(
            suite_root / "experiment_suite_execution_state.json"
        )
    )
    first_failed = (
        None if state is None else _first_failed_work_item(state)
    )
    issues = []
    overall_status = str(parsed.get("overall_status", ""))
    if result["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title=f"{command_name} command exited non-zero",
                summary=f"The readiness command {command_name!r} did not complete successfully.",
            )
        )
    if overall_status != expected_suite_status:
        issues.append(
            _issue(
                severity="blocking",
                title=f"{command_name} reported unexpected suite status",
                summary=(
                    f"The readiness command {command_name!r} reported overall_status "
                    f"{overall_status!r}, expected {expected_suite_status!r}."
                ),
            )
        )

    package_audit = {
        "package_metadata_exists": False,
        "result_index_exists": False,
    }
    if isinstance(parsed.get("package"), Mapping):
        package_payload = dict(parsed["package"])
        metadata_path = Path(package_payload["metadata_path"]).resolve()
        result_index_path = Path(package_payload["result_index_path"]).resolve()
        package_audit = {
            "package_metadata_exists": metadata_path.exists(),
            "result_index_exists": result_index_path.exists(),
        }

    simulation_details = {}
    if state is not None:
        simulation_records = [
            item for item in state["work_items"] if item["stage_id"] == "simulation"
        ]
        if simulation_records:
            first_record = simulation_records[0]
            simulation_details = {
                "simulation_work_item_count": len(simulation_records),
                "first_simulation_model_modes": list(
                    first_record["attempts"][-1]["result_summary"].get("model_modes", [])
                ),
                "first_simulation_run_count": int(
                    first_record["attempts"][-1]["result_summary"].get(
                        "executed_run_count", 0
                    )
                ),
            }

    return {
        "overall_status": "pass" if not issues else "fail",
        "observed_suite_status": overall_status,
        "expected_suite_status": expected_suite_status,
        "command": result,
        "suite_root": None if suite_root is None else str(suite_root),
        "first_failed_work_item": first_failed,
        "package_audit": package_audit,
        "simulation_details": simulation_details,
        "issues": issues,
    }


def _materialize_manifest_fixture(
    *,
    repo_root: Path,
    fixture_dir: Path,
) -> dict[str, Path]:
    helpers = _load_test_helpers(repo_root)
    fixture_dir = ensure_dir(fixture_dir)
    execution_fixture = helpers["materialize_execution_fixture"](fixture_dir)

    shuffle_simulation_block = _build_manifest_suite_block(
        output_root=fixture_dir / "out" / "shuffle_simulation_suite",
        enabled_stage_ids=["simulation"],
        ablations=(
            {
                "ablation_family_id": "shuffle_morphology",
                "variant_id": "shuffled",
                "display_name": "Shuffle Morphology",
                "dimension_filters": {"motion_direction": ["preferred"]},
                "parameter_snapshot": {"shuffle_kind": "root_correspondence"},
            },
        ),
    )
    no_waves_block = _build_manifest_suite_block(
        output_root=fixture_dir / "out" / "no_waves_simulation_suite",
        enabled_stage_ids=["simulation"],
        ablations=(
            {
                "ablation_family_id": "no_waves",
                "variant_id": "disabled",
                "display_name": "No Waves",
                "parameter_snapshot": {"mode": "disable_surface_wave"},
            },
        ),
    )
    shuffle_full_stage_block = _build_manifest_suite_block(
        output_root=fixture_dir / "out" / "shuffle_full_stage_suite",
        enabled_stage_ids=["simulation", "analysis", "validation", "dashboard"],
        ablations=(
            {
                "ablation_family_id": "shuffle_morphology",
                "variant_id": "shuffled",
                "display_name": "Shuffle Morphology",
                "dimension_filters": {"motion_direction": ["preferred"]},
                "parameter_snapshot": {"shuffle_kind": "root_correspondence"},
            },
        ),
    )

    shuffle_suite_manifest = fixture_dir / "shuffle_simulation_suite.yaml"
    no_waves_suite_manifest = fixture_dir / "no_waves_simulation_suite.yaml"
    shuffle_full_stage_manifest = fixture_dir / "shuffle_full_stage_suite.yaml"
    embedded_shuffle_manifest = fixture_dir / "embedded_shuffle_simulation_manifest.yaml"

    _write_suite_manifest(
        path=shuffle_suite_manifest,
        experiment_manifest_path=execution_fixture["manifest_path"],
        suite_block=shuffle_simulation_block,
    )
    _write_suite_manifest(
        path=no_waves_suite_manifest,
        experiment_manifest_path=execution_fixture["manifest_path"],
        suite_block=no_waves_block,
    )
    _write_suite_manifest(
        path=shuffle_full_stage_manifest,
        experiment_manifest_path=execution_fixture["manifest_path"],
        suite_block=shuffle_full_stage_block,
    )
    _write_embedded_suite_manifest(
        source_manifest_path=execution_fixture["manifest_path"],
        suite_block=shuffle_simulation_block,
        output_path=embedded_shuffle_manifest,
    )

    return {
        "config_path": Path(execution_fixture["config_path"]).resolve(),
        "manifest_path": Path(execution_fixture["manifest_path"]).resolve(),
        "schema_path": Path(execution_fixture["schema_path"]).resolve(),
        "design_lock_path": Path(execution_fixture["design_lock_path"]).resolve(),
        "shuffle_simulation_suite_manifest": shuffle_suite_manifest.resolve(),
        "embedded_shuffle_simulation_manifest": embedded_shuffle_manifest.resolve(),
        "no_waves_simulation_suite_manifest": no_waves_suite_manifest.resolve(),
        "shuffle_full_stage_suite_manifest": shuffle_full_stage_manifest.resolve(),
    }


def _materialize_review_fixture(
    *,
    repo_root: Path,
    fixture_dir: Path,
) -> dict[str, Any]:
    fixture_dir = ensure_dir(fixture_dir)
    helpers = _load_test_helpers(repo_root)
    package_metadata_path = helpers["materialize_packaged_suite_fixture"](fixture_dir)
    package_metadata = load_experiment_suite_package_metadata(package_metadata_path)
    result_index = load_experiment_suite_result_index(package_metadata)
    paths = discover_experiment_suite_package_paths(package_metadata)
    return {
        "package_metadata_path": Path(package_metadata_path).resolve(),
        "suite_root": Path(result_index["suite_root"]).resolve(),
        "result_index_path": paths["result_index"],
    }


def _audit_review_workflow(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    package_metadata_path: Path,
) -> dict[str, Any]:
    aggregation_first = _run_command_capture(
        name="suite_aggregation_first",
        command=[
            python_executable,
            str(repo_root / "scripts" / "32_suite_aggregation.py"),
            "--suite-package-metadata",
            str(package_metadata_path),
            "--table-dimension-id",
            "motion_direction",
        ],
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    aggregation_second = _run_command_capture(
        name="suite_aggregation_second",
        command=[
            python_executable,
            str(repo_root / "scripts" / "32_suite_aggregation.py"),
            "--suite-package-metadata",
            str(package_metadata_path),
            "--table-dimension-id",
            "motion_direction",
        ],
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    package_metadata = load_experiment_suite_package_metadata(package_metadata_path)
    result_index = load_experiment_suite_result_index(package_metadata)
    suite_root = Path(result_index["suite_root"]).resolve()

    aggregation_summary_path = suite_root / "package" / "aggregation" / "suite_aggregation_summary.json"
    aggregation_export_dir = suite_root / "package" / "aggregation" / "exports"
    aggregation_hashes_first = _file_hashes(
        (
            aggregation_summary_path,
            aggregation_export_dir / "shared_comparison_cell_rollups.csv",
            aggregation_export_dir / "shared_comparison_paired_rows.csv",
            aggregation_export_dir / "shared_comparison_summary_table.csv",
            aggregation_export_dir / "wave_diagnostic_summary_table.csv",
            aggregation_export_dir / "validation_summary_table.csv",
        )
    )
    aggregation_hashes_second = _file_hashes(tuple(Path(path) for path in aggregation_hashes_first))
    aggregation_deterministic = aggregation_hashes_first == aggregation_hashes_second

    report_first = _run_command_capture(
        name="suite_report_first",
        command=[
            python_executable,
            str(repo_root / "scripts" / "33_suite_report.py"),
            "--suite-package-metadata",
            str(package_metadata_path),
            "--table-dimension-id",
            "motion_direction",
        ],
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    report_second = _run_command_capture(
        name="suite_report_second",
        command=[
            python_executable,
            str(repo_root / "scripts" / "33_suite_report.py"),
            "--suite-package-metadata",
            str(package_metadata_path),
            "--table-dimension-id",
            "motion_direction",
        ],
        cwd=repo_root,
        commands_dir=commands_dir,
    )
    report_dir = suite_root / "package" / "report" / "suite_review"
    plot_paths = sorted((report_dir / "plots").rglob("*.svg"))
    report_hashes_first = _file_hashes(
        (
            report_dir / "suite_review_summary.json",
            report_dir / "index.html",
            report_dir / "catalog" / "artifact_catalog.json",
            *plot_paths,
        )
    )
    report_hashes_second = _file_hashes(tuple(Path(path) for path in report_hashes_first))
    report_deterministic = report_hashes_first == report_hashes_second

    aggregation_summary = json.loads(aggregation_summary_path.read_text(encoding="utf-8"))
    review_summary = json.loads(
        (report_dir / "suite_review_summary.json").read_text(encoding="utf-8")
    )
    issues = []
    if aggregation_first["returncode"] != 0 or aggregation_second["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Suite aggregation CLI failed",
                summary="The shipped Milestone 15 aggregation command did not complete successfully on the packaged fixture.",
            )
        )
    if report_first["returncode"] != 0 or report_second["returncode"] != 0:
        issues.append(
            _issue(
                severity="blocking",
                title="Suite report CLI failed",
                summary="The shipped Milestone 15 review-report command did not complete successfully on the packaged fixture.",
            )
        )
    if not aggregation_deterministic:
        issues.append(
            _issue(
                severity="blocking",
                title="Suite aggregation outputs changed across reruns",
                summary="The packaged fixture no longer produces stable aggregation bytes across repeated CLI runs.",
            )
        )
    if not report_deterministic:
        issues.append(
            _issue(
                severity="blocking",
                title="Suite report outputs changed across reruns",
                summary="The packaged fixture no longer produces stable review-report outputs across repeated CLI runs.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "package_audit": {
            "overall_status": "pass",
            "package_metadata_path": str(package_metadata_path.resolve()),
            "result_index_path": str(
                discover_experiment_suite_package_paths(package_metadata)["result_index"]
            ),
            "cell_record_count": len(result_index["cell_records"]),
        },
        "aggregation_audit": {
            "overall_status": "pass" if aggregation_first["returncode"] == 0 else "fail",
            "first_command": aggregation_first,
            "second_command": aggregation_second,
            "summary_path": str(aggregation_summary_path.resolve()),
            "deterministic": aggregation_deterministic,
            "row_counts": copy.deepcopy(dict(aggregation_summary["summary"])),
        },
        "report_audit": {
            "overall_status": "pass" if report_first["returncode"] == 0 else "fail",
            "first_command": report_first,
            "second_command": report_second,
            "summary_path": str((report_dir / "suite_review_summary.json").resolve()),
            "index_path": str((report_dir / "index.html").resolve()),
            "artifact_catalog_path": str(
                (report_dir / "catalog" / "artifact_catalog.json").resolve()
            ),
            "plot_count": len(plot_paths),
            "deterministic": report_deterministic,
            "section_ids": [item["section_id"] for item in review_summary["sections"]],
        },
        "issues": issues,
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    issues = []
    snippets_found: dict[str, dict[str, bool]] = {}
    for relative_path, snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        path = (repo_root / relative_path).resolve()
        text = path.read_text(encoding="utf-8")
        snippet_status = {snippet: snippet in text for snippet in snippets}
        snippets_found[relative_path] = snippet_status
        if not all(snippet_status.values()):
            missing = [snippet for snippet, found in snippet_status.items() if not found]
            issues.append(
                _issue(
                    severity="blocking",
                    title=f"Documentation missing Milestone 15 readiness snippets in {relative_path}",
                    summary=f"Expected snippets are missing from {relative_path}: {missing!r}.",
                )
            )
    follow_on_path = repo_root / "agent_tickets" / "milestone_15_follow_on_tickets.md"
    if not follow_on_path.exists():
        issues.append(
            _issue(
                severity="blocking",
                title="Milestone 15 follow-on ticket file is missing",
                summary="The readiness pass requires one explicit follow-on ticket file for the remaining orchestration gaps.",
            )
        )
    return {
        "overall_status": "pass" if not issues else "fail",
        "snippets_found": snippets_found,
        "follow_on_ticket_path": str(follow_on_path.resolve()),
        "issues": issues,
    }


def _build_manifest_suite_block(
    *,
    output_root: Path,
    enabled_stage_ids: Sequence[str],
    ablations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "suite_id": "m15_manifest_readiness_suite",
        "suite_label": "Milestone 15 Manifest Readiness Suite",
        "description": "Representative manifest-driven suite used by the Milestone 15 readiness pass.",
        "output_root": str(output_root.resolve()),
        "enabled_stage_ids": list(enabled_stage_ids),
        "dimensions": {
            "fixed": [
                {
                    "dimension_id": "scene_type",
                    "value_id": "moving_edge",
                    "value_label": "Moving Edge",
                    "parameter_snapshot": {
                        "stimulus_family": "moving_edge",
                        "stimulus_name": "simple_moving_edge",
                    },
                },
                {
                    "dimension_id": "motion_direction",
                    "value_id": "preferred",
                    "value_label": "Preferred",
                    "manifest_overrides": {
                        "stimulus": {"stimulus_overrides": {"direction_deg": 0.0}}
                    },
                    "parameter_snapshot": {"direction_deg": 0.0},
                },
                {
                    "dimension_id": "contrast_level",
                    "value_id": "high_contrast",
                    "value_label": "High Contrast",
                    "manifest_overrides": {
                        "stimulus": {"stimulus_overrides": {"contrast": 0.8}}
                    },
                    "parameter_snapshot": {"contrast": 0.8},
                },
                {
                    "dimension_id": "noise_level",
                    "value_id": "low_noise",
                    "value_label": "Low Noise",
                    "parameter_snapshot": {"noise_level": 0.0},
                },
                {
                    "dimension_id": "active_subset",
                    "value_id": "motion_minimal",
                    "value_label": "Motion Minimal",
                    "manifest_overrides": {"subset_name": "motion_minimal"},
                    "parameter_snapshot": {"subset_name": "motion_minimal"},
                },
                {
                    "dimension_id": "wave_kernel",
                    "value_id": "motion_patch_reference",
                    "value_label": "Motion Patch Reference",
                    "config_overrides": {
                        "simulation": {
                            "surface_wave": {"parameter_preset": "motion_patch_reference"}
                        }
                    },
                    "parameter_snapshot": {"parameter_preset": "motion_patch_reference"},
                },
                {
                    "dimension_id": "mesh_resolution",
                    "value_id": "fine",
                    "value_label": "Fine",
                    "parameter_snapshot": {"resolution": "fine"},
                },
                {
                    "dimension_id": "solver_settings",
                    "value_id": "dt_5_ms",
                    "value_label": "dt 5 ms",
                    "manifest_overrides": {
                        "stimulus": {
                            "temporal_sampling": {
                                "dt_ms": 5.0,
                                "duration_ms": 500.0,
                            }
                        }
                    },
                    "config_overrides": {
                        "simulation": {
                            "timebase": {
                                "dt_ms": 5.0,
                                "duration_ms": 500.0,
                                "sample_count": 100,
                            }
                        }
                    },
                    "parameter_snapshot": {
                        "dt_ms": 5.0,
                        "duration_ms": 500.0,
                        "sample_count": 100,
                    },
                },
                {
                    "dimension_id": "fidelity_class",
                    "value_id": "surface_only",
                    "value_label": "Surface Only",
                    "parameter_snapshot": {"fidelity_class": "surface_only"},
                },
            ],
            "sweep_axes": [],
        },
        "seed_policy": {
            "simulation_seed_source": "explicit_values",
            "simulation_seed_values": [11, 17],
            "reuse_scope": "shared_within_base_condition",
            "lineage_seed_stride": 1000,
            "perturbation_seed_mode": "derived_offset",
            "perturbation_seed_offset": 90000,
        },
        "ablations": [copy.deepcopy(dict(item)) for item in ablations],
    }


def _write_suite_manifest(
    *,
    path: Path,
    experiment_manifest_path: Path,
    suite_block: Mapping[str, Any],
) -> None:
    payload = {
        "format": "yaml_experiment_suite_manifest.v1",
        "experiment_manifest": {"path": str(experiment_manifest_path.resolve())},
        **copy.deepcopy(dict(suite_block)),
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _write_embedded_suite_manifest(
    *,
    source_manifest_path: Path,
    suite_block: Mapping[str, Any],
    output_path: Path,
) -> None:
    payload = yaml.safe_load(source_manifest_path.read_text(encoding="utf-8"))
    payload["suite"] = copy.deepcopy(dict(suite_block))
    output_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _load_test_helpers(repo_root: Path) -> dict[str, Any]:
    tests_root = repo_root / "tests"
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(tests_root) not in sys.path:
        sys.path.insert(0, str(tests_root))
    execution_module = _import_test_helper_module(
        "tests.test_simulator_execution",
        fallback_name="test_simulator_execution",
    )
    aggregation_module = _import_test_helper_module(
        "tests.test_experiment_suite_aggregation",
        fallback_name="test_experiment_suite_aggregation",
    )
    return {
        "materialize_execution_fixture": getattr(
            execution_module, "_materialize_execution_fixture"
        ),
        "materialize_packaged_suite_fixture": getattr(
            aggregation_module, "_materialize_packaged_suite_fixture"
        ),
    }


def _import_test_helper_module(module_name: str, *, fallback_name: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return importlib.import_module(fallback_name)


def _run_command_capture(
    *,
    name: str,
    command: Sequence[str],
    cwd: Path,
    commands_dir: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path = commands_dir / f"{name}.stdout.txt"
    stderr_path = commands_dir / f"{name}.stderr.txt"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    payload: dict[str, Any] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(shlex.quote(part) for part in command),
        "returncode": int(result.returncode),
        "stdout_path": str(stdout_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
    }
    parsed_summary = _parse_json_from_command_output(result.stdout)
    if parsed_summary is not None:
        payload["parsed_summary"] = parsed_summary
    return payload


def _parse_json_from_command_output(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    if start < 0:
        return None
    try:
        candidate = json.loads(stripped[start:])
    except json.JSONDecodeError:
        return None
    return candidate if isinstance(candidate, dict) else None


def _first_failed_work_item(state: Mapping[str, Any]) -> dict[str, Any] | None:
    for item in state.get("work_items", []):
        if str(item.get("status")) != "failed":
            continue
        error = {}
        attempts = item.get("attempts", [])
        if attempts:
            error = dict(attempts[-1].get("error") or {})
        return {
            "stage_id": str(item.get("stage_id", "")),
            "work_item_id": str(item.get("work_item_id", "")),
            "suite_cell_id": str(item.get("suite_cell_id", "")),
            "status_detail": str(item.get("status_detail", "")),
            "error": error,
        }
    return None


def _file_hashes(paths: Sequence[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        resolved = Path(path).resolve()
        if not resolved.exists():
            continue
        hashes[str(resolved)] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return hashes


def _issue(*, severity: str, title: str, summary: str) -> dict[str, str]:
    return {
        "severity": severity,
        "title": title,
        "summary": summary,
    }


def _render_markdown(summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    manifest_resolution = dict(summary["manifest_resolution_audit"])
    shuffle_simulation = dict(summary["shuffle_simulation_audit"])
    no_waves = dict(summary["no_waves_audit"])
    full_stage = dict(summary["full_stage_audit"])
    review_audit = dict(summary["review_audit"])
    lines = [
        "# Milestone 15 Readiness Report",
        "",
        "## Verdict",
        "",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Ready for Milestone 16 showcase work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Verification command: `{summary['documented_verification_command']}`",
        f"- Explicit command: `{summary['explicit_verification_command']}`",
        "",
        "## Verification Surface",
        "",
        f"- Focused fixture suite: `{summary['fixture_verification']['status']}`",
        f"- Suite-manifest resolution audit: `{manifest_resolution['overall_status']}`",
        f"- Manifest-driven shuffle simulation suite status: `{shuffle_simulation['observed_suite_status']}`",
        f"- Required `no_waves` runtime suite status: `{no_waves['observed_suite_status']}`",
        f"- Full-stage manifest suite status: `{full_stage['observed_suite_status']}`",
        f"- Packaged review fixture audit: `{review_audit['report_audit']['overall_status']}`",
        f"- Documentation audit: `{summary['documentation_audit']['overall_status']}`",
        "",
        "## Verified",
        "",
        f"- Dry-run work-item ordering matches across suite-manifest and embedded-manifest entrypoints: `{manifest_resolution['work_item_order_match']}`",
        f"- Representative seeded shuffle suite executes both model modes: `{shuffle_simulation['simulation_details'].get('first_simulation_model_modes', [])}`",
        f"- Shipped package fixture cell count: `{review_audit['package_audit']['cell_record_count']}`",
        f"- Aggregation outputs deterministic across reruns: `{review_audit['aggregation_audit']['deterministic']}`",
        f"- Report outputs deterministic across reruns: `{review_audit['report_audit']['deterministic']}`",
        f"- Report sections: `{review_audit['report_audit']['section_ids']}`",
        "",
        "## Blocking Gaps",
        "",
        f"- `no_waves` runtime failure: `{(no_waves.get('first_failed_work_item') or {}).get('status_detail', 'n/a')}`",
        f"- Full-stage analysis failure: `{(full_stage.get('first_failed_work_item') or {}).get('status_detail', 'n/a')}`",
        "",
        "## Remaining Risks",
        "",
    ]
    for item in summary["remaining_risks"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Deferred Follow-On Issues",
            "",
        ]
    )
    for ticket in summary["follow_on_tickets"]:
        lines.append(
            f"- `{ticket['ticket_id']}`: {ticket['title']}"
        )
        lines.append(f"  Reproduction: {ticket['reproduction_notes']}")
    return "\n".join(lines) + "\n"
