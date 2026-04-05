from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import yaml

from .config import REPO_ROOT, load_config
from .coupling_contract import (
    ASSET_STATUS_READY,
    build_coupling_bundle_metadata,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
)
from .experiment_analysis_contract import (
    build_experiment_analysis_bundle_metadata,
    write_experiment_analysis_bundle_metadata,
)
from .experiment_comparison_analysis import discover_experiment_bundle_set
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    SIMPLIFIED_MESH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    build_operator_bundle_metadata,
    default_asset_statuses,
    write_geometry_manifest,
)
from .io_utils import ensure_dir, write_deterministic_npz, write_json
from .selection import write_selected_root_roster, write_subset_manifest
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from .simulator_result_contract import (
    build_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from .stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from .stimulus_contract import (
    build_stimulus_bundle_metadata,
    load_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from .surface_operators import serialize_sparse_matrix
from .validation_circuit import resolve_circuit_validation_plan
from .validation_contract import SUPPORTED_VALIDATION_LAYER_IDS
from .validation_morphology import resolve_morphology_validation_plan
from .validation_numerics import resolve_numerical_validation_plan
from .validation_planning import resolve_manifest_validation_plan
from .validation_reporting import (
    discover_validation_ladder_layer_artifacts,
    discover_validation_ladder_package_paths,
    load_validation_ladder_package_metadata,
)
from .validation_task import _resolve_task_validation_plan


MILESTONE13_READINESS_REPORT_VERSION = "milestone13_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_validation_contract",
    "tests.test_validation_planning",
    "tests.test_validation_numerics",
    "tests.test_validation_morphology",
    "tests.test_validation_circuit",
    "tests.test_validation_task",
    "tests.test_validation_reporting",
    "tests.test_milestone13_readiness",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone13-readiness",
        "scripts/28_milestone13_readiness.py",
        "scripts/27_validation_ladder.py",
        "make validation-ladder-smoke",
        "milestone_13_readiness.md",
        "milestone_13_readiness.json",
    ),
    "docs/pipeline_notes.md": (
        "make milestone13-readiness",
        "scripts/28_milestone13_readiness.py",
        "scripts/27_validation_ladder.py smoke",
        "milestone_13_readiness.md",
        "milestone_13_readiness.json",
    ),
}

DEFAULT_VALIDATION_FIXTURE_CONFIG = {
    "active_layer_ids": [
        "numerical_sanity",
        "morphology_sanity",
        "circuit_sanity",
        "task_sanity",
    ],
    "perturbation_suites": {
        "timestep_sweeps": {
            "enabled": True,
            "sweep_spec_paths": ["config/surface_wave_sweep.verification.yaml"],
            "use_manifest_seed_sweep": True,
        },
        "geometry_variants": {
            "enabled": True,
            "variant_ids": ["intact", "shuffled"],
        },
        "sign_delay_perturbations": {
            "enabled": True,
            "variant_ids": ["sign_inversion_probe", "zero_delay_probe"],
        },
        "noise_robustness": {
            "enabled": True,
            "seed_values": [11, 17, 23],
            "noise_levels": [0.0, 0.1],
        },
    },
}

EXPECTED_LAYER_VALIDATOR_IDS = {
    "numerical_sanity": [
        "operator_bundle_gate_alignment",
        "surface_wave_stability_envelope",
    ],
    "morphology_sanity": [
        "geometry_dependence_collapse",
        "mixed_fidelity_surrogate_preservation",
    ],
    "circuit_sanity": [
        "coupling_semantics_continuity",
        "motion_pathway_asymmetry",
    ],
    "task_sanity": [
        "shared_effect_reproducibility",
        "task_decoder_robustness",
    ],
}

FOLLOW_ON_TICKETS = (
    {
        "ticket_id": "FW-M13-FOLLOW-001",
        "severity": "non_blocking",
        "title": "Add a tracked manifest-owned validation fixture with cached runnable artifacts",
        "summary": (
            "FW-M13-008 proves contract integration with a representative-manifest "
            "plan fixture plus the deterministic packaged smoke workflow, but it does "
            "not ship one committed manifest-scale cache that can execute all four "
            "validators without synthesizing fixture metadata."
        ),
        "reproduction_notes": (
            "Run `make milestone13-readiness` and inspect the representative-manifest "
            "audit. The plan resolves cleanly on the real Milestone 1 manifest, but "
            "the end-to-end executed ladder still comes from the shipped smoke fixture."
        ),
    },
    {
        "ticket_id": "FW-M13-FOLLOW-002",
        "severity": "non_blocking",
        "title": "Add a richer task-layer smoke fixture that exercises shared-versus-wave UI separation explicitly",
        "summary": (
            "The current packaged smoke fixture intentionally leaves the task layer at "
            "`review` to preserve the Grant handoff boundary. Dashboard and orchestration "
            "consumers should eventually see a richer fixture that renders both shared "
            "comparison and wave-only diagnostic sections on packaged M13 outputs."
        ),
        "reproduction_notes": (
            "Run `make validation-ladder-smoke` and inspect the packaged task-layer "
            "summary plus report under the readiness-linked smoke output root."
        ),
    },
)


def build_milestone13_readiness_paths(
    processed_simulator_results_dir: str | Path,
) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_13"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_13_readiness.md",
        "json_path": report_dir / "milestone_13_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
        "smoke_processed_simulator_results_dir": report_dir
        / "smoke_fixture"
        / "simulator_results",
    }


def execute_milestone13_readiness_pass(
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
    simulation_verification = dict(cfg.get("simulation_verification", {}))
    validation_verification = dict(cfg.get("validation_verification", {}))

    manifest_path = _resolve_repo_path(
        simulation_verification.get("manifest_path"),
        repo_root,
        default=repo_root / "manifests" / "examples" / "milestone_1_demo.yaml",
    )
    schema_path = _resolve_repo_path(
        simulation_verification.get("schema_path"),
        repo_root,
        default=repo_root / "schemas" / "milestone_1_experiment_manifest.schema.json",
    )
    design_lock_path = _resolve_repo_path(
        simulation_verification.get("design_lock_path"),
        repo_root,
        default=repo_root / "config" / "milestone_1_design_lock.yaml",
    )
    smoke_baseline_path = _resolve_repo_path(
        validation_verification.get("smoke_baseline_path"),
        repo_root,
        default=repo_root / "tests" / "fixtures" / "validation_ladder_smoke_baseline.json",
    )

    readiness_paths = build_milestone13_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = ensure_dir(readiness_paths["generated_fixture_dir"])

    representative_fixture = _materialize_representative_manifest_fixture(
        repo_root=repo_root,
        generated_fixture_dir=generated_fixture_dir,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    validation_plan_audit = _audit_validation_plan_resolution(
        fixture=representative_fixture
    )
    smoke_workflow_audit = _audit_smoke_workflow(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
        smoke_processed_simulator_results_dir=readiness_paths[
            "smoke_processed_simulator_results_dir"
        ],
        smoke_baseline_path=smoke_baseline_path,
    )
    command_surface_audit = _audit_command_surface(
        repo_root=repo_root,
        python_executable=python_executable,
        commands_dir=commands_dir,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)

    workflow_coverage = {
        "fixture_test_suite": str(fixture_verification.get("status", "")) == "pass",
        "representative_manifest_plan_resolution": validation_plan_audit[
            "overall_status"
        ]
        == "pass",
        "smoke_validation_ladder_command": smoke_workflow_audit["overall_status"]
        == "pass",
        "packaged_artifact_discovery": smoke_workflow_audit[
            "artifact_discovery_status"
        ]
        == "pass",
        "regression_command_discovery": command_surface_audit["overall_status"]
        == "pass",
        "documentation": documentation_audit["overall_status"] == "pass",
    }

    all_issues = (
        list(validation_plan_audit["issues"])
        + list(smoke_workflow_audit["issues"])
        + list(command_surface_audit["issues"])
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

    summary = {
        "report_version": MILESTONE13_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "representative_manifest_path": str(manifest_path.resolve()),
        "representative_fixture_config_path": str(
            representative_fixture["config_path"].resolve()
        ),
        "representative_analysis_bundle_path": str(
            representative_fixture["analysis_bundle_path"].resolve()
        ),
        "smoke_processed_simulator_results_dir": str(
            readiness_paths["smoke_processed_simulator_results_dir"].resolve()
        ),
        "smoke_baseline_path": str(smoke_baseline_path.resolve()),
        "documented_verification_command": "make milestone13-readiness",
        "documented_end_to_end_commands": [
            "make milestone13-readiness",
            "make validation-ladder-smoke",
        ],
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "validation_plan_audit": validation_plan_audit,
        "smoke_workflow_audit": smoke_workflow_audit,
        "command_surface_audit": command_surface_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": [
            "The deterministic smoke fixture proves reusable ladder behavior, but it is still a synthetic fixture rather than a committed manifest-scale cached result set.",
            "Review-level findings remain first-class outputs; downstream dashboards and orchestration must preserve `pass` versus `review` versus `blocking` semantics instead of collapsing them into a binary pass/fail gate.",
        ],
        "follow_on_tickets": [copy.deepcopy(item) for item in FOLLOW_ON_TICKETS],
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(
                readiness_status != READINESS_GATE_HOLD
            ),
            "ready_for_milestones": [
                "milestone_14_dashboard",
                "experiment_orchestration",
            ]
            if readiness_status != READINESS_GATE_HOLD
            else [],
            "smoke_ladder_status": smoke_workflow_audit.get("packaged_overall_status", ""),
            "scientific_review_boundary": (
                "Milestone 13 is engineering-ready when command discovery, plan "
                "resolution, packaging, and regression artifacts are deterministic. "
                "Grant-owned plausibility decisions still start at review handoff "
                "artifacts and packaged `review` findings."
            ),
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone13_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _audit_validation_plan_resolution(
    *,
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    general_plan = resolve_manifest_validation_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
    )
    numerical_plan = resolve_numerical_validation_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
    )
    morphology_plan = resolve_morphology_validation_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
    )
    circuit_plan = resolve_circuit_validation_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
        analysis_bundle_metadata_path=fixture["analysis_bundle_path"],
    )
    task_plan = _resolve_task_validation_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
        analysis_bundle_metadata_path=fixture["analysis_bundle_path"],
    )

    if list(general_plan["active_layer_ids"]) != list(SUPPORTED_VALIDATION_LAYER_IDS):
        issues.append(
            _issue(
                "blocking",
                "Representative manifest validation plan did not resolve the canonical "
                f"layer ordering {list(SUPPORTED_VALIDATION_LAYER_IDS)!r}.",
            )
        )

    layer_plans = {
        "numerical_sanity": numerical_plan,
        "morphology_sanity": morphology_plan,
        "circuit_sanity": circuit_plan,
        "task_sanity": task_plan,
    }
    for layer_id, expected_validator_ids in EXPECTED_LAYER_VALIDATOR_IDS.items():
        plan = layer_plans[layer_id]
        if plan["active_layer_ids"] != [layer_id]:
            issues.append(
                _issue(
                    "blocking",
                    f"{layer_id} plan did not resolve as a single-layer validation plan.",
                )
            )
        missing_validator_ids = sorted(
            set(expected_validator_ids) - set(plan["active_validator_ids"])
        )
        if missing_validator_ids:
            issues.append(
                _issue(
                    "blocking",
                    f"{layer_id} plan is missing validator ids {missing_validator_ids!r}.",
                )
            )

    required_suite_ids = {
        "geometry_variants",
        "noise_robustness",
        "sign_delay_perturbations",
        "timestep_sweeps",
    }
    present_suite_ids = {
        str(item["suite_id"]) for item in general_plan["perturbation_suites"]
    }
    missing_suite_ids = sorted(required_suite_ids - present_suite_ids)
    if missing_suite_ids:
        issues.append(
            _issue(
                "blocking",
                "Representative manifest validation plan is missing perturbation suites "
                f"{missing_suite_ids!r}.",
            )
        )

    bundle_directories = {
        layer_id: str(
            Path(plan["output_locations"]["bundle_directory"]).resolve()
        )
        for layer_id, plan in layer_plans.items()
    }
    return {
        "overall_status": "pass" if not issues else "fail",
        "representative_manifest_path": str(Path(fixture["manifest_path"]).resolve()),
        "fixture_config_path": str(Path(fixture["config_path"]).resolve()),
        "analysis_bundle_path": str(Path(fixture["analysis_bundle_path"]).resolve()),
        "active_layer_ids": list(general_plan["active_layer_ids"]),
        "general_validator_ids": list(general_plan["active_validator_ids"]),
        "perturbation_suite_ids": sorted(present_suite_ids),
        "layer_validator_ids": {
            layer_id: list(plan["active_validator_ids"])
            for layer_id, plan in layer_plans.items()
        },
        "bundle_directories": bundle_directories,
        "issues": issues,
    }


def _audit_smoke_workflow(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
    smoke_processed_simulator_results_dir: Path,
    smoke_baseline_path: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    command = [
        python_executable,
        str((repo_root / "scripts" / "27_validation_ladder.py").resolve()),
        "smoke",
        "--processed-simulator-results-dir",
        str(smoke_processed_simulator_results_dir.resolve()),
        "--baseline",
        str(smoke_baseline_path.resolve()),
        "--enforce-baseline",
    ]
    first = _run_command("validation_ladder_smoke_first", command, cwd=repo_root)
    second = _run_command("validation_ladder_smoke_second", command, cwd=repo_root)
    write_json(first, commands_dir / "validation_ladder_smoke_first.json")
    write_json(second, commands_dir / "validation_ladder_smoke_second.json")

    if first["status"] != "pass" or second["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                "The shipped `scripts/27_validation_ladder.py smoke` command did not "
                "complete successfully during the readiness pass.",
            )
        )
        return {
            "overall_status": "fail",
            "artifact_discovery_status": "fail",
            "issues": issues,
            "first_command": first,
            "second_command": second,
        }

    first_summary = dict(first["parsed_summary"])
    second_summary = dict(second["parsed_summary"])
    stable_identity = (
        first_summary["bundle_id"] == second_summary["bundle_id"]
        and first_summary["summary_path"] == second_summary["summary_path"]
        and first_summary["finding_rows_csv_path"] == second_summary["finding_rows_csv_path"]
        and first_summary["report_path"] == second_summary["report_path"]
    )
    if not stable_identity:
        issues.append(
            _issue(
                "blocking",
                "Repeated packaged smoke runs did not reuse the same bundle identity and output paths.",
            )
        )

    summary_path = Path(first_summary["summary_path"]).resolve()
    finding_rows_csv_path = Path(first_summary["finding_rows_csv_path"]).resolve()
    report_path = Path(first_summary["report_path"]).resolve()
    metadata_path = Path(first_summary["metadata_path"]).resolve()
    regression_summary_path = Path(first_summary["regression_summary_path"]).resolve()

    artifact_hashes_stable = (
        _hash_file(summary_path) == _hash_file(Path(second_summary["summary_path"]).resolve())
        and _hash_file(finding_rows_csv_path)
        == _hash_file(Path(second_summary["finding_rows_csv_path"]).resolve())
        and _hash_file(report_path)
        == _hash_file(Path(second_summary["report_path"]).resolve())
    )
    if not artifact_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated packaged smoke runs did not reproduce stable summary, export, and report bytes.",
            )
        )

    metadata = load_validation_ladder_package_metadata(metadata_path)
    discovered_paths = discover_validation_ladder_package_paths(metadata)
    discovered_layer_paths = discover_validation_ladder_layer_artifacts(metadata)
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    regression_summary = json.loads(regression_summary_path.read_text(encoding="utf-8"))

    discovered_layer_ids = sorted(discovered_layer_paths)
    if discovered_layer_ids != sorted(SUPPORTED_VALIDATION_LAYER_IDS):
        issues.append(
            _issue(
                "blocking",
                "Packaged smoke metadata did not rediscover the four canonical validation layers.",
            )
        )
    if regression_summary.get("status") != "pass":
        issues.append(
            _issue(
                "blocking",
                "Packaged smoke regression summary did not pass against the committed baseline.",
            )
        )

    artifact_discovery_status = "pass"
    for artifact_id, path in discovered_paths.items():
        if not Path(path).exists():
            artifact_discovery_status = "fail"
            issues.append(
                _issue(
                    "blocking",
                    f"Packaged smoke discovery path for {artifact_id!r} does not exist on disk.",
                )
            )
    for layer_id, layer_paths in discovered_layer_paths.items():
        for artifact_id, path in layer_paths.items():
            if not Path(path).exists():
                artifact_discovery_status = "fail"
                issues.append(
                    _issue(
                        "blocking",
                        f"Layer discovery path for {layer_id!r}/{artifact_id!r} does not exist on disk.",
                    )
                )

    return {
        "overall_status": "pass" if not issues else "fail",
        "artifact_discovery_status": artifact_discovery_status,
        "first_command": first,
        "second_command": second,
        "summary_stable": stable_identity,
        "artifact_hashes_stable": artifact_hashes_stable,
        "packaged_overall_status": str(summary_payload["overall_status"]),
        "regression_status": str(regression_summary["status"]),
        "layer_statuses": copy.deepcopy(dict(summary_payload["layer_statuses"])),
        "validator_statuses": copy.deepcopy(dict(summary_payload["validator_statuses"])),
        "packaged_artifact_ids": sorted(discovered_paths),
        "discovered_layer_ids": discovered_layer_ids,
        "summary_path": str(summary_path),
        "finding_rows_csv_path": str(finding_rows_csv_path),
        "report_path": str(report_path),
        "metadata_path": str(metadata_path),
        "regression_summary_path": str(regression_summary_path),
        "issues": issues,
    }


def _audit_command_surface(
    *,
    repo_root: Path,
    python_executable: str,
    commands_dir: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    make_help = subprocess.run(
        ["make", "help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    make_help_path = commands_dir / "make_help.txt"
    make_help_path.write_text(make_help.stdout, encoding="utf-8")
    if make_help.returncode != 0:
        issues.append(_issue("blocking", "`make help` failed during command-surface audit."))
    else:
        for snippet in (
            "validation-ladder-smoke",
            "validation-ladder-package",
            "milestone13-readiness",
        ):
            if snippet not in make_help.stdout:
                issues.append(
                    _issue(
                        "blocking",
                        f"`make help` is missing the documented command surface entry {snippet!r}.",
                    )
                )

    readiness_help = subprocess.run(
        [
            python_executable,
            str((repo_root / "scripts" / "28_milestone13_readiness.py").resolve()),
            "--help",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    readiness_help_path = commands_dir / "milestone13_readiness_help.txt"
    readiness_help_path.write_text(readiness_help.stdout, encoding="utf-8")
    if readiness_help.returncode != 0 or "Milestone 13" not in readiness_help.stdout:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 13 readiness script help surface is not executable.",
            )
        )

    smoke_help = subprocess.run(
        [
            python_executable,
            str((repo_root / "scripts" / "27_validation_ladder.py").resolve()),
            "--help",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    smoke_help_path = commands_dir / "validation_ladder_help.txt"
    smoke_help_path.write_text(smoke_help.stdout, encoding="utf-8")
    if smoke_help.returncode != 0 or "smoke" not in smoke_help.stdout:
        issues.append(
            _issue(
                "blocking",
                "The packaged validation ladder CLI help surface is not executable.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "make_help_path": str(make_help_path.resolve()),
        "readiness_help_path": str(readiness_help_path.resolve()),
        "validation_ladder_help_path": str(smoke_help_path.resolve()),
        "issues": issues,
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    audits: dict[str, dict[str, Any]] = {}
    for relative_path, snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        path = (repo_root / relative_path).resolve()
        if not path.exists():
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing, so the Milestone 13 readiness workflow is not documented there.",
                )
            )
            audits[relative_path] = {"exists": False, "missing_snippets": list(snippets)}
            continue
        text = path.read_text(encoding="utf-8")
        missing_snippets = [snippet for snippet in snippets if snippet not in text]
        if missing_snippets:
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing the Milestone 13 readiness snippets {missing_snippets!r}.",
                )
            )
        audits[relative_path] = {
            "exists": True,
            "missing_snippets": missing_snippets,
        }
    rationale_path = repo_root / "docs" / "validation_ladder_notes" / "FW-M13-008_rationale.md"
    if not rationale_path.exists():
        issues.append(
            _issue(
                "blocking",
                "The Milestone 13 readiness rationale note is missing at docs/validation_ladder_notes/FW-M13-008_rationale.md.",
            )
        )
    audits[str(rationale_path.relative_to(repo_root))] = {
        "exists": rationale_path.exists(),
        "missing_snippets": [],
    }
    return {
        "overall_status": "pass" if not issues else "fail",
        "files": audits,
        "issues": issues,
    }


def _materialize_representative_manifest_fixture(
    *,
    repo_root: Path,
    generated_fixture_dir: Path,
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
) -> dict[str, Path]:
    fixture_root = ensure_dir(generated_fixture_dir / "representative_manifest")
    config_path = _write_simulation_fixture(
        fixture_root,
        validation_config={
            **copy.deepcopy(DEFAULT_VALIDATION_FIXTURE_CONFIG),
            "perturbation_suites": {
                **copy.deepcopy(DEFAULT_VALIDATION_FIXTURE_CONFIG["perturbation_suites"]),
                "timestep_sweeps": {
                    **copy.deepcopy(
                        DEFAULT_VALIDATION_FIXTURE_CONFIG["perturbation_suites"][
                            "timestep_sweeps"
                        ]
                    ),
                    "sweep_spec_paths": [
                        str(
                            (repo_root / "config" / "surface_wave_sweep.verification.yaml").resolve()
                        )
                    ],
                },
            },
        },
    )
    _record_fixture_stimulus_bundle(
        manifest_path=manifest_path,
        processed_stimulus_dir=fixture_root / "out" / "stimuli",
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    analysis_plan = resolve_manifest_readout_analysis_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    _write_simulator_bundle_metadata(simulation_plan, analysis_plan=analysis_plan)
    bundle_set = discover_experiment_bundle_set(
        simulation_plan=simulation_plan,
        analysis_plan=analysis_plan,
    )
    analysis_bundle_metadata = build_experiment_analysis_bundle_metadata(
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
    )
    analysis_bundle_path = write_experiment_analysis_bundle_metadata(
        analysis_bundle_metadata
    )
    return {
        "fixture_root": fixture_root.resolve(),
        "manifest_path": manifest_path.resolve(),
        "config_path": config_path.resolve(),
        "schema_path": schema_path.resolve(),
        "design_lock_path": design_lock_path.resolve(),
        "analysis_bundle_path": analysis_bundle_path.resolve(),
    }


def _write_simulation_fixture(
    fixture_root: Path,
    *,
    validation_config: Mapping[str, Any],
) -> Path:
    output_dir = fixture_root / "out"
    subset_name = str(validation_config.get("subset_name", "motion_minimal"))
    selected_root_ids_path = output_dir / "selected_root_ids.txt"
    write_selected_root_roster([101, 202], selected_root_ids_path)

    write_subset_manifest(
        subset_output_dir=output_dir / "subsets",
        preset_name=subset_name,
        root_ids=[101, 202],
    )

    _write_geometry_manifest(output_dir)

    config_path = fixture_root / "simulation_fixture_config.yaml"
    payload = {
        "paths": {
            "selected_root_ids": str(selected_root_ids_path.resolve()),
            "subset_output_dir": str((output_dir / "subsets").resolve()),
            "manifest_json": str((output_dir / "asset_manifest.json").resolve()),
            "processed_stimulus_dir": str((output_dir / "stimuli").resolve()),
            "processed_retinal_dir": str((output_dir / "retinal").resolve()),
            "processed_simulator_results_dir": str(
                (output_dir / "simulator_results").resolve()
            ),
        },
        "selection": {
            "active_preset": subset_name,
        },
        "simulation": {
            "input": {
                "source_kind": "stimulus_bundle",
                "require_recorded_bundle": True,
            },
            "readout_catalog": [
                {
                    "readout_id": "shared_output_mean",
                    "scope": "circuit_output",
                    "aggregation": "mean_over_root_ids",
                    "units": "activation_au",
                    "value_semantics": "shared_downstream_activation",
                    "description": "Shared downstream output mean for matched comparisons.",
                }
            ],
            "surface_wave": {
                "parameter_preset": "motion_patch_reference",
                "propagation": {
                    "wave_speed_sq_scale": 1.25,
                    "restoring_strength_per_ms2": 0.07,
                },
                "damping": {
                    "gamma_per_ms": 0.18,
                },
                "recovery": {
                    "mode": "activity_driven_first_order",
                    "time_constant_ms": 14.0,
                    "drive_gain": 0.3,
                    "coupling_strength_per_ms2": 0.12,
                },
                "nonlinearity": {
                    "mode": "tanh_soft_clip",
                    "activation_scale": 1.1,
                },
                "anisotropy": {
                    "mode": "operator_embedded",
                    "strength_scale": 1.05,
                },
            },
        },
        "validation": copy.deepcopy(dict(validation_config)),
    }
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def _record_fixture_stimulus_bundle(
    *,
    manifest_path: Path,
    processed_stimulus_dir: Path,
    schema_path: Path,
    design_lock_path: Path,
) -> None:
    resolved_input = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )
    record_stimulus_bundle(resolved_input)


def _write_geometry_manifest(output_dir: Path) -> None:
    root_ids = [101, 202]
    coupling_dir = output_dir / "processed_coupling"
    local_synapse_registry_path = coupling_dir / "synapse_registry.csv"
    local_synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
    local_synapse_registry_path.write_text(
        "\n".join(
            [
                "synapse_row_id,pre_root_id,post_root_id",
                "fixture-1,101,202",
                "fixture-2,202,101",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

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
    for pre_root_id in root_ids:
        for post_root_id in root_ids:
            if pre_root_id == post_root_id:
                continue
            _write_placeholder_file(
                coupling_dir / "edges" / f"{pre_root_id}__to__{post_root_id}_coupling.npz"
            )

    bundle_records: dict[int, dict[str, Any]] = {}
    for root_id in root_ids:
        asset_statuses = default_asset_statuses(fetch_skeletons=False)
        asset_statuses.update(
            {
                SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
                FINE_OPERATOR_KEY: ASSET_STATUS_READY,
                COARSE_OPERATOR_KEY: ASSET_STATUS_READY,
                TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
                OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
            }
        )
        bundle_paths = build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=output_dir / "meshes_raw",
            skeletons_raw_dir=output_dir / "skeletons_raw",
            processed_mesh_dir=output_dir / "processed_meshes",
            processed_graph_dir=output_dir / "processed_graphs",
        )
        _write_placeholder_file(bundle_paths.simplified_mesh_path)
        operator_bundle_metadata = _write_fixture_operator_bundle(
            bundle_paths=bundle_paths,
            root_id=root_id,
            asset_statuses=asset_statuses,
        )
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
                    pre_root_id=pre_root_id,
                    post_root_id=post_root_id,
                    processed_coupling_dir=coupling_dir,
                    status=ASSET_STATUS_READY,
                )
                for pre_root_id in root_ids
                for post_root_id in root_ids
                if pre_root_id != post_root_id and root_id in (pre_root_id, post_root_id)
            ],
        )
        bundle_records[root_id] = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": f"fixture_{root_id}",
                "project_role": "surface_simulated",
            },
            operator_bundle_metadata=operator_bundle_metadata,
            coupling_bundle_metadata=coupling_metadata,
            processed_coupling_dir=coupling_dir,
        )

    write_geometry_manifest(
        manifest_path=output_dir / "asset_manifest.json",
        bundle_records=bundle_records,
        dataset_name="public",
        materialization_version=783,
        meshing_config_snapshot=_meshing_config_snapshot(),
        processed_coupling_dir=coupling_dir,
    )


def _write_fixture_operator_bundle(
    *,
    bundle_paths: Any,
    root_id: int,
    asset_statuses: Mapping[str, str],
) -> dict[str, Any]:
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


def _write_placeholder_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _write_simulator_bundle_metadata(
    simulation_plan: Mapping[str, Any],
    *,
    analysis_plan: Mapping[str, Any],
) -> None:
    condition_variants = _condition_variants(analysis_plan)
    for run_plan in discover_simulation_run_plans(
        simulation_plan,
        use_manifest_seed_sweep=True,
    ):
        selected_assets = list(run_plan["selected_assets"])
        input_asset = next(
            asset for asset in selected_assets if str(asset["asset_role"]) == "input_bundle"
        )
        base_stimulus_metadata = load_stimulus_bundle_metadata(input_asset["path"])
        processed_stimulus_dir = Path(
            base_stimulus_metadata["assets"]["metadata_json"]["path"]
        ).resolve().parents[4]
        for condition_variant in condition_variants:
            stimulus_metadata = build_stimulus_bundle_metadata(
                stimulus_family=base_stimulus_metadata["stimulus_family"],
                stimulus_name=base_stimulus_metadata["stimulus_name"],
                processed_stimulus_dir=processed_stimulus_dir,
                representation_family=base_stimulus_metadata["representation_family"],
                parameter_snapshot={
                    **base_stimulus_metadata["parameter_snapshot"],
                    **condition_variant["parameter_overrides"],
                },
                seed=base_stimulus_metadata["determinism"]["seed"],
                rng_family=base_stimulus_metadata["determinism"]["rng_family"],
                temporal_sampling=base_stimulus_metadata["temporal_sampling"],
                spatial_frame=base_stimulus_metadata["spatial_frame"],
                luminance_convention=base_stimulus_metadata["luminance_convention"],
            )
            stimulus_metadata_path = write_stimulus_bundle_metadata(
                stimulus_metadata,
                write_aliases=False,
            )
            mutated_assets: list[dict[str, Any]] = []
            for asset in selected_assets:
                record = dict(asset)
                if str(record["asset_role"]) == "input_bundle":
                    record["bundle_id"] = str(stimulus_metadata["bundle_id"])
                    record["path"] = str(stimulus_metadata_path.resolve())
                mutated_assets.append(record)
            bundle_metadata = build_simulator_result_bundle_metadata(
                manifest_reference=run_plan["manifest_reference"],
                arm_reference=run_plan["arm_reference"],
                determinism=run_plan["determinism"],
                timebase=run_plan["runtime"]["timebase"],
                selected_assets=mutated_assets,
                readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
                processed_simulator_results_dir=run_plan["runtime"][
                    "processed_simulator_results_dir"
                ],
            )
            write_simulator_result_bundle_metadata(bundle_metadata)


def _condition_variants(analysis_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in analysis_plan["condition_catalog"]:
        grouped.setdefault(str(item["parameter_name"]), []).append(dict(item))
    if not grouped:
        return [{"condition_ids": [], "parameter_overrides": {}}]
    variants: list[dict[str, Any]] = [{"condition_ids": [], "parameter_overrides": {}}]
    for parameter_name in sorted(grouped):
        next_variants: list[dict[str, Any]] = []
        for partial in variants:
            for item in grouped[parameter_name]:
                next_variants.append(
                    {
                        "condition_ids": sorted(
                            [*partial["condition_ids"], str(item["condition_id"])]
                        ),
                        "parameter_overrides": {
                            **partial["parameter_overrides"],
                            parameter_name: item["value"],
                        },
                    }
                )
        variants = next_variants
    variants.sort(key=lambda item: tuple(item["condition_ids"]))
    return variants


def _run_command(name: str, command: list[str], *, cwd: Path) -> dict[str, Any]:
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
    return payload if isinstance(payload, dict) else None


def _resolve_repo_path(value: Any, repo_root: Path, *, default: Path) -> Path:
    if value is None:
        return default.resolve()
    candidate = Path(str(value)).expanduser()
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    return candidate.resolve()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _issue(severity: str, message: str) -> dict[str, str]:
    return {
        "severity": str(severity),
        "message": str(message),
    }


def _render_milestone13_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    plan_audit = dict(summary["validation_plan_audit"])
    smoke_audit = dict(summary["smoke_workflow_audit"])
    command_surface = dict(summary["command_surface_audit"])
    documentation = dict(summary["documentation_audit"])
    workflow_coverage = dict(summary["workflow_coverage"])
    lines = [
        "# Milestone 13 Readiness Report",
        "",
        f"- Report version: `{summary['report_version']}`",
        f"- Representative manifest: `{summary['representative_manifest_path']}`",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Ready for follow-on work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Ready for downstream work: `{', '.join(readiness.get('ready_for_milestones', []))}`",
        f"- Documented command: `{summary['documented_verification_command']}`",
        "",
        "## What Was Verified",
        "",
        "- Representative-manifest validation-plan resolution resolves the canonical four-layer ladder and per-layer validator sets on a local deterministic fixture.",
        f"- Validation-plan audit: `{plan_audit['overall_status']}` with layer order `{plan_audit['active_layer_ids']}`.",
        f"- Packaged smoke command audit: `{smoke_audit['overall_status']}` with packaged overall status `{smoke_audit.get('packaged_overall_status', '')}` and regression status `{smoke_audit.get('regression_status', '')}`.",
        f"- Command-surface audit: `{command_surface['overall_status']}`.",
        f"- Documentation audit: `{documentation['overall_status']}`.",
        "",
        "## Workflow Coverage",
        "",
    ]
    for key, value in workflow_coverage.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Deterministic Outputs",
            "",
            f"- Readiness JSON: `{summary['json_path']}`",
            f"- Smoke processed-results root: `{summary['smoke_processed_simulator_results_dir']}`",
            f"- Packaged smoke summary: `{smoke_audit.get('summary_path', '')}`",
            f"- Packaged smoke report: `{smoke_audit.get('report_path', '')}`",
            "",
            "## Remaining Risks",
            "",
        ]
    )
    for item in summary["remaining_risks"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Follow-On Tickets",
            "",
        ]
    )
    for item in summary["follow_on_tickets"]:
        lines.append(
            f"- `{item['ticket_id']}`: {item['title']} "
            f"Reproduction: {item['reproduction_notes']}"
        )
    return "\n".join(lines) + "\n"
