from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .config import REPO_ROOT, load_config
from .io_utils import ensure_dir, write_json
from .manifests import load_yaml, validate_manifest
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .stimulus_bundle import (
    DESCRIPTOR_REPLAY_SOURCE,
    FRAME_CACHE_REPLAY_SOURCE,
    load_recorded_stimulus_bundle,
    resolve_stimulus_input,
)
from .stimulus_contract import (
    FRAME_CACHE_KEY,
    STIMULUS_BUNDLE_CONTRACT_VERSION,
    load_stimulus_bundle_metadata,
)
from .stimulus_registry import get_stimulus_registry_entry, list_stimulus_families


MILESTONE8A_READINESS_REPORT_VERSION = "milestone8a_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_stimulus_contract",
    "tests.test_stimulus_registry",
    "tests.test_stimulus_generators",
    "tests.test_stimulus_motion_generators",
    "tests.test_manifest_validation",
    "tests.test_stimulus_bundle_workflow",
    "tests.test_milestone8a_readiness",
)

DEFAULT_REQUIRED_STIMULUS_FAMILIES = (
    "flash",
    "moving_bar",
    "translated_edge",
    "drifting_grating",
    "looming",
    "radial_flow",
    "rotating_flow",
)

DEFAULT_FAMILY_FIXTURE_CASES = {
    "flash": "flash_clip_timing",
    "moving_bar": "moving_bar_negative_aperture",
    "drifting_grating": "drifting_grating_phase",
    "looming": "looming_growth",
    "radial_flow": "radial_flow_expansion_square",
    "rotating_flow": "rotating_flow_clockwise_square",
}

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "docs/stimulus_bundle_workflow.md": (
        "python scripts/10_stimulus_bundle.py record",
        "python scripts/10_stimulus_bundle.py replay",
        "preview/index.html",
        "preview/summary.json",
        "preview/frames/frame-<index>.svg",
        "make milestone8a-readiness",
    ),
    "docs/stimulus_bundle_design.md": (
        "stimulus_preview.gif",
        "preview/index.html",
        "preview/summary.json",
        "reserved optional animation slot",
    ),
    "docs/pipeline_notes.md": (
        "stimulus_preview.gif",
        "preview/index.html",
        "preview/summary.json",
        "static offline preview sidecars",
    ),
    "README.md": (
        "make milestone8a-readiness",
        "scripts/11_milestone8a_readiness.py",
        "milestone_8a_readiness.md",
        "milestone_8a_readiness.json",
    ),
}


def build_milestone8a_readiness_paths(processed_stimulus_dir: str | Path) -> dict[str, Path]:
    root = Path(processed_stimulus_dir).resolve()
    report_dir = root / "readiness" / "milestone_8a"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_8a_readiness.md",
        "json_path": report_dir / "milestone_8a_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_inputs_dir": report_dir / "generated_inputs",
    }


def execute_milestone8a_readiness_pass(
    *,
    config_path: str | Path,
    fixture_verification: dict[str, Any],
    python_executable: str = sys.executable,
    root_dir: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = Path(root_dir).resolve()
    cfg = load_config(config_path, project_root=repo_root)
    processed_stimulus_dir = Path(cfg["paths"]["processed_stimulus_dir"]).resolve()
    verification_cfg = dict(cfg.get("stimulus_verification", {}))

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
    family_cases_path = _resolve_repo_path(
        verification_cfg.get("fixture_cases_path"),
        repo_root,
        default=repo_root / "tests" / "fixtures" / "stimulus_generator_cases.yaml",
    )
    alias_config_fixture_path = _resolve_repo_path(
        verification_cfg.get("config_alias_fixture_path"),
        repo_root,
        default=repo_root / "tests" / "fixtures" / "stimulus_config_fixture.yaml",
    )

    readiness_paths = build_milestone8a_readiness_paths(processed_stimulus_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_inputs_dir = ensure_dir(readiness_paths["generated_inputs_dir"])

    registry_catalog_audit = _audit_registry_catalog()
    family_cases = load_yaml(family_cases_path).get("cases", {})
    family_audits: list[dict[str, Any]] = []
    for stimulus_family, case_name in DEFAULT_FAMILY_FIXTURE_CASES.items():
        case_payload = family_cases.get(case_name)
        if not isinstance(case_payload, dict):
            family_audits.append(
                _failed_family_audit(
                    stimulus_family=stimulus_family,
                    input_kind="fixture_case",
                    input_path=family_cases_path,
                    issues=[
                        _issue(
                            "blocking",
                            f"Fixture case {case_name!r} is missing from {family_cases_path}.",
                        )
                    ],
                )
            )
            continue
        config_payload = {
            "paths": {"processed_stimulus_dir": str(processed_stimulus_dir)},
            **copy.deepcopy(dict(case_payload.get("stimulus", {}))),
        }
        config_path_for_family = generated_inputs_dir / f"{stimulus_family}.yaml"
        _write_yaml(config_payload, config_path_for_family)
        family_audits.append(
            _exercise_config_entrypoint(
                label=stimulus_family,
                config_path=config_path_for_family,
                expected_canonical_family=stimulus_family,
                commands_dir=commands_dir,
                python_executable=python_executable,
                repo_root=repo_root,
                input_kind="fixture_case",
                source_reference=str(family_cases_path),
            )
        )

    alias_fixture_payload = load_yaml(alias_config_fixture_path)
    alias_fixture_payload.setdefault("paths", {})
    alias_fixture_payload["paths"]["processed_stimulus_dir"] = str(processed_stimulus_dir)
    translated_edge_config_path = generated_inputs_dir / "translated_edge_alias_fixture.yaml"
    _write_yaml(alias_fixture_payload, translated_edge_config_path)
    family_audits.append(
        _exercise_config_entrypoint(
            label="translated_edge_alias_fixture",
            config_path=translated_edge_config_path,
            expected_canonical_family="translated_edge",
            commands_dir=commands_dir,
            python_executable=python_executable,
            repo_root=repo_root,
            input_kind="config_alias_fixture",
            source_reference=str(alias_config_fixture_path),
        )
    )

    manifest_audit = _exercise_manifest_entrypoint(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)

    exercised_families = sorted({audit["stimulus_family"] for audit in family_audits})
    family_coverage_ok = exercised_families == sorted(DEFAULT_REQUIRED_STIMULUS_FAMILIES)
    family_coverage_issues: list[dict[str, str]] = []
    if not family_coverage_ok:
        family_coverage_issues.append(
            _issue(
                "blocking",
                "The readiness pass did not exercise exactly one representative example from every required "
                f"Milestone 8A family. Expected {list(DEFAULT_REQUIRED_STIMULUS_FAMILIES)!r}, "
                f"observed {exercised_families!r}.",
            )
        )

    blocking_issues = (
        [issue for issue in registry_catalog_audit["issues"] if issue["severity"] == "blocking"]
        + [issue for audit in family_audits for issue in audit["issues"] if issue["severity"] == "blocking"]
        + [issue for issue in manifest_audit["issues"] if issue["severity"] == "blocking"]
        + [issue for issue in documentation_audit["issues"] if issue["severity"] == "blocking"]
        + family_coverage_issues
    )
    warning_issues = (
        [issue for issue in registry_catalog_audit["issues"] if issue["severity"] != "blocking"]
        + [issue for audit in family_audits for issue in audit["issues"] if issue["severity"] != "blocking"]
        + [issue for issue in manifest_audit["issues"] if issue["severity"] != "blocking"]
        + [issue for issue in documentation_audit["issues"] if issue["severity"] != "blocking"]
    )

    fixture_status = str(fixture_verification.get("status", "skipped"))
    registry_status = str(registry_catalog_audit.get("overall_status", "fail"))
    manifest_status = str(manifest_audit.get("overall_status", "fail"))
    docs_status = str(documentation_audit.get("overall_status", "fail"))
    family_statuses = {audit["stimulus_family"]: audit["overall_status"] for audit in family_audits}

    if (
        fixture_status != "pass"
        or registry_status != "pass"
        or manifest_status != "pass"
        or docs_status != "pass"
        or not family_coverage_ok
        or any(status != "pass" for status in family_statuses.values())
        or blocking_issues
    ):
        readiness_status = READINESS_GATE_HOLD
    elif warning_issues:
        readiness_status = READINESS_GATE_REVIEW
    else:
        readiness_status = "ready"

    summary = {
        "report_version": MILESTONE8A_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "commands_dir": str(commands_dir.resolve()),
        "generated_inputs_dir": str(generated_inputs_dir.resolve()),
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "required_stimulus_families": list(DEFAULT_REQUIRED_STIMULUS_FAMILIES),
        "exercised_stimulus_families": exercised_families,
        "family_count": len(exercised_families),
        "family_coverage_ok": family_coverage_ok,
        "registry_catalog_audit": registry_catalog_audit,
        "family_audits": family_audits,
        "manifest_audit": manifest_audit,
        "documentation_audit": documentation_audit,
        "follow_on_issues": [],
        "remaining_risks": [
            "This readiness pass proves local canonical-stimulus integration only. Retinal sampling, scene composition, and simulator coupling remain future integration surfaces."
        ],
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            "local_stimulus_gate": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_milestones": ["8B", "8C", "later_experiment_orchestration"],
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone8a_readiness_markdown(summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _exercise_config_entrypoint(
    *,
    label: str,
    config_path: Path,
    expected_canonical_family: str,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
    input_kind: str,
    source_reference: str,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    try:
        resolved_input = resolve_stimulus_input(config_path=config_path)
        resolved_spec = resolved_input.resolved_stimulus.stimulus_spec
        registry_entry = get_stimulus_registry_entry(
            resolved_spec["stimulus_family"],
            resolved_spec["stimulus_name"],
        )

        record_first = _run_command(
            name=f"{label}_record_first",
            command=[
                python_executable,
                str(repo_root / "scripts" / "10_stimulus_bundle.py"),
                "record",
                "--config",
                str(config_path),
            ],
            log_dir=commands_dir,
            cwd=repo_root,
        )
        first_summary = dict(record_first.get("parsed_summary") or {})
        metadata_path = Path(first_summary.get("stimulus_bundle_metadata_path", ""))
        if record_first["status"] != "pass" or not metadata_path.exists():
            issues.append(
                _issue(
                    "blocking",
                    f"Recording the {resolved_spec['stimulus_family']!r} config entrypoint failed.",
                )
            )
            return _build_config_audit(
                label=label,
                input_kind=input_kind,
                source_reference=source_reference,
                config_path=config_path,
                resolved_spec=resolved_spec,
                registry_entry=registry_entry,
                record_first=record_first,
                record_second={},
                replay_bundle={},
                replay_config={},
                metadata={},
                preview_summary={},
                deterministic_file_hashes=False,
                descriptor_regeneration_matches_cache=False,
                descriptor_regeneration_audit={},
                issues=issues,
            )

        bundle_directory = Path(first_summary["bundle_directory"]).resolve()
        first_hashes = _snapshot_file_hashes(bundle_directory)
        metadata = load_stimulus_bundle_metadata(metadata_path)
        if metadata["contract_version"] != STIMULUS_BUNDLE_CONTRACT_VERSION:
            issues.append(
                _issue(
                    "blocking",
                    "Recorded bundle metadata did not preserve the canonical `stimulus_bundle.v1` contract version.",
                )
            )
        if resolved_spec["stimulus_family"] != expected_canonical_family:
            issues.append(
                _issue(
                    "blocking",
                    f"Config entrypoint resolved to {resolved_spec['stimulus_family']!r} instead of {expected_canonical_family!r}.",
                )
            )
        if resolved_input.bundle_metadata_path != metadata_path.resolve():
            issues.append(
                _issue(
                    "blocking",
                    "Resolved config bundle path did not match the recorded `stimulus_bundle.json` path.",
                )
            )
        if first_summary.get("replay_source") != FRAME_CACHE_REPLAY_SOURCE:
            issues.append(
                _issue(
                    "blocking",
                    "The record workflow did not reload the freshly written bundle from the cached frame archive.",
                )
            )

        record_second = _run_command(
            name=f"{label}_record_second",
            command=[
                python_executable,
                str(repo_root / "scripts" / "10_stimulus_bundle.py"),
                "record",
                "--config",
                str(config_path),
            ],
            log_dir=commands_dir,
            cwd=repo_root,
        )
        second_hashes = _snapshot_file_hashes(bundle_directory)
        deterministic_file_hashes = record_second["status"] == "pass" and first_hashes == second_hashes
        if not deterministic_file_hashes:
            issues.append(
                _issue(
                    "blocking",
                    "Repeated recording changed bundle bytes for the same resolved config stimulus.",
                )
            )

        recorded_bundle = load_recorded_stimulus_bundle(metadata_path)
        replay_times = _select_replay_times(recorded_bundle.frame_times_ms)
        replay_bundle = _run_command(
            name=f"{label}_replay_bundle",
            command=_build_replay_command(
                python_executable=python_executable,
                repo_root=repo_root,
                source_flag="--bundle-metadata",
                source_value=str(metadata_path),
                replay_times_ms=replay_times,
            ),
            log_dir=commands_dir,
            cwd=repo_root,
        )
        replay_config = _run_command(
            name=f"{label}_replay_config",
            command=_build_replay_command(
                python_executable=python_executable,
                repo_root=repo_root,
                source_flag="--config",
                source_value=str(config_path),
                replay_times_ms=replay_times,
            ),
            log_dir=commands_dir,
            cwd=repo_root,
        )
        if replay_bundle["status"] != "pass" or replay_config["status"] != "pass":
            issues.append(
                _issue(
                    "blocking",
                    "Offline replay failed for one of the shipped config or bundle entrypoints.",
                )
            )
        replay_bundle_summary = dict(replay_bundle.get("parsed_summary") or {})
        replay_config_summary = dict(replay_config.get("parsed_summary") or {})
        if replay_bundle_summary.get("requested_samples") != replay_config_summary.get("requested_samples"):
            issues.append(
                _issue(
                    "blocking",
                    "Config-based replay and bundle-metadata replay produced different sample-hold frame selections.",
                )
            )
        if replay_bundle_summary.get("replay_source") != FRAME_CACHE_REPLAY_SOURCE:
            issues.append(
                _issue(
                    "blocking",
                    "Bundle replay did not use the deterministic cached frame archive.",
                )
            )

        descriptor_regeneration_audit = _audit_descriptor_regeneration(metadata_path)
        descriptor_regeneration_matches_cache = bool(
            descriptor_regeneration_audit["frame_arrays_equal"]
            and descriptor_regeneration_audit["frame_times_equal"]
            and descriptor_regeneration_audit["descriptor_replay_source"] == DESCRIPTOR_REPLAY_SOURCE
            and descriptor_regeneration_audit["cache_replay_source"] == FRAME_CACHE_REPLAY_SOURCE
        )
        if not descriptor_regeneration_matches_cache:
            issues.append(
                _issue(
                    "blocking",
                    "Descriptor regeneration did not reproduce the same replay arrays as the recorded frame cache.",
                )
            )

        preview_summary = _load_json(Path(first_summary["preview_summary_path"]))
        preview_frame_paths = [
            Path(frame_record["path"]).resolve()
            for frame_record in preview_summary.get("selected_frames", [])
            if isinstance(frame_record, dict) and frame_record.get("path")
        ]
        if not Path(first_summary["preview_report_path"]).exists() or not preview_frame_paths:
            issues.append(
                _issue(
                    "blocking",
                    "The recorded bundle did not emit the expected static offline preview outputs.",
                )
            )
        if metadata["stimulus_family"] != registry_entry["stimulus_family"] or metadata["stimulus_name"] != registry_entry["stimulus_name"]:
            issues.append(
                _issue(
                    "blocking",
                    "Recorded bundle metadata did not match the canonical registry entry chosen by the config resolver.",
                )
            )

        return _build_config_audit(
            label=label,
            input_kind=input_kind,
            source_reference=source_reference,
            config_path=config_path,
            resolved_spec=resolved_spec,
            registry_entry=registry_entry,
            record_first=record_first,
            record_second=record_second,
            replay_bundle=replay_bundle,
            replay_config=replay_config,
            metadata=metadata,
            preview_summary=preview_summary,
            deterministic_file_hashes=deterministic_file_hashes,
            descriptor_regeneration_matches_cache=descriptor_regeneration_matches_cache,
            descriptor_regeneration_audit=descriptor_regeneration_audit,
            issues=issues,
        )
    except Exception as exc:  # pragma: no cover - exercised via report status assertions
        return _failed_family_audit(
            stimulus_family=expected_canonical_family,
            input_kind=input_kind,
            input_path=config_path,
            issues=[_issue("blocking", f"{label} audit failed: {exc}")],
        )


def _exercise_manifest_entrypoint(
    *,
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    processed_stimulus_dir: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    validate_command = _run_command(
        name="manifest_validate",
        command=[
            python_executable,
            str(repo_root / "scripts" / "04_validate_manifest.py"),
            "--manifest",
            str(manifest_path),
            "--schema",
            str(schema_path),
            "--design-lock",
            str(design_lock_path),
        ],
        log_dir=commands_dir,
        cwd=repo_root,
    )
    validation_summary = validate_manifest(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )

    record_first = _run_command(
        name="manifest_record_first",
        command=[
            python_executable,
            str(repo_root / "scripts" / "10_stimulus_bundle.py"),
            "record",
            "--manifest",
            str(manifest_path),
            "--schema",
            str(schema_path),
            "--design-lock",
            str(design_lock_path),
            "--processed-stimulus-dir",
            str(processed_stimulus_dir),
        ],
        log_dir=commands_dir,
        cwd=repo_root,
    )
    first_summary = dict(record_first.get("parsed_summary") or {})
    metadata_path = Path(first_summary.get("stimulus_bundle_metadata_path", ""))
    bundle_directory = Path(first_summary.get("bundle_directory", ""))
    if validate_command["status"] != "pass" or record_first["status"] != "pass" or not metadata_path.exists():
        issues.append(
            _issue(
                "blocking",
                "The example manifest did not validate and record successfully through the shipped CLI entrypoints.",
            )
        )
        return {
            "overall_status": "fail",
            "manifest_path": str(manifest_path.resolve()),
            "schema_path": str(schema_path.resolve()),
            "design_lock_path": str(design_lock_path.resolve()),
            "validate_command": validate_command,
            "validation_summary": validation_summary,
            "record_first": record_first,
            "record_second": {},
            "replay_manifest": {},
            "replay_bundle": {},
            "issues": issues,
        }

    first_hashes = _snapshot_file_hashes(bundle_directory.resolve())
    metadata = load_stimulus_bundle_metadata(metadata_path)
    record_second = _run_command(
        name="manifest_record_second",
        command=[
            python_executable,
            str(repo_root / "scripts" / "10_stimulus_bundle.py"),
            "record",
            "--manifest",
            str(manifest_path),
            "--schema",
            str(schema_path),
            "--design-lock",
            str(design_lock_path),
            "--processed-stimulus-dir",
            str(processed_stimulus_dir),
        ],
        log_dir=commands_dir,
        cwd=repo_root,
    )
    second_hashes = _snapshot_file_hashes(bundle_directory.resolve())
    deterministic_file_hashes = record_second["status"] == "pass" and first_hashes == second_hashes
    if not deterministic_file_hashes:
        issues.append(
            _issue(
                "blocking",
                "Repeated manifest recording changed bundle bytes for the same canonical manifest stimulus.",
            )
        )

    if validation_summary["resolved_stimulus_family"] != "translated_edge":
        issues.append(
            _issue(
                "blocking",
                "The example manifest did not resolve through the canonical translated-edge registry entry.",
            )
        )
    resolved_stimulus = dict(validation_summary.get("resolved_stimulus", {}))
    compatibility = dict(resolved_stimulus.get("compatibility", {}))
    if not compatibility.get("family_alias_used") or not compatibility.get("name_alias_used"):
        issues.append(
            _issue(
                "blocking",
                "The example manifest no longer exercises the required moving_edge compatibility alias path.",
            )
        )
    if validation_summary["stimulus_bundle_metadata_path"] != str(metadata_path.resolve()):
        issues.append(
            _issue(
                "blocking",
                "Manifest validation and manifest recording disagreed about the canonical bundle metadata path.",
            )
        )

    recorded_bundle = load_recorded_stimulus_bundle(metadata_path)
    replay_times = _select_replay_times(recorded_bundle.frame_times_ms)
    replay_manifest = _run_command(
        name="manifest_replay_manifest",
        command=[
            python_executable,
            str(repo_root / "scripts" / "10_stimulus_bundle.py"),
            "replay",
            "--manifest",
            str(manifest_path),
            "--schema",
            str(schema_path),
            "--design-lock",
            str(design_lock_path),
            "--processed-stimulus-dir",
            str(processed_stimulus_dir),
            *[item for time_ms in replay_times for item in ("--time-ms", str(time_ms))],
        ],
        log_dir=commands_dir,
        cwd=repo_root,
    )
    replay_bundle = _run_command(
        name="manifest_replay_bundle",
        command=_build_replay_command(
            python_executable=python_executable,
            repo_root=repo_root,
            source_flag="--bundle-metadata",
            source_value=str(metadata_path),
            replay_times_ms=replay_times,
        ),
        log_dir=commands_dir,
        cwd=repo_root,
    )
    replay_manifest_summary = dict(replay_manifest.get("parsed_summary") or {})
    replay_bundle_summary = dict(replay_bundle.get("parsed_summary") or {})
    if replay_manifest["status"] != "pass" or replay_bundle["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                "Manifest replay failed for the manifest or bundle-metadata entrypoint.",
            )
        )
    elif replay_manifest_summary.get("requested_samples") != replay_bundle_summary.get("requested_samples"):
        issues.append(
            _issue(
                "blocking",
                "Manifest replay and direct bundle replay produced different frame selections.",
            )
        )

    preview_summary = _load_json(Path(first_summary["preview_summary_path"]))
    if not preview_summary.get("selected_frames"):
        issues.append(
            _issue(
                "blocking",
                "The manifest-driven bundle did not record any representative offline preview frames.",
            )
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "manifest_path": str(manifest_path.resolve()),
        "schema_path": str(schema_path.resolve()),
        "design_lock_path": str(design_lock_path.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir.resolve()),
        "validate_command": validate_command,
        "validation_summary": validation_summary,
        "record_first": record_first,
        "record_second": record_second,
        "replay_manifest": replay_manifest,
        "replay_bundle": replay_bundle,
        "deterministic_file_hashes": deterministic_file_hashes,
        "preview_summary": preview_summary,
        "issues": issues,
    }


def _audit_registry_catalog() -> dict[str, Any]:
    discovered_families = sorted(item["stimulus_family"] for item in list_stimulus_families())
    missing = sorted(set(DEFAULT_REQUIRED_STIMULUS_FAMILIES) - set(discovered_families))
    issues: list[dict[str, str]] = []
    if missing:
        issues.append(
            _issue(
                "blocking",
                f"The canonical stimulus registry is missing required Milestone 8A families: {missing!r}.",
            )
        )
    return {
        "overall_status": "pass" if not issues else "fail",
        "required_families": list(DEFAULT_REQUIRED_STIMULUS_FAMILIES),
        "discovered_families": discovered_families,
        "coverage_ok": not missing,
        "issues": issues,
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    file_audits: dict[str, Any] = {}
    issues: list[dict[str, str]] = []
    for relative_path, snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        path = repo_root / relative_path
        text = path.read_text(encoding="utf-8")
        missing = [snippet for snippet in snippets if snippet not in text]
        file_audits[relative_path] = {
            "path": str(path.resolve()),
            "missing_snippets": missing,
            "snippet_count": len(snippets),
        }
        if missing:
            issues.append(
                _issue(
                    "blocking",
                    f"Documentation drift detected in {relative_path}: missing {missing!r}.",
                )
            )
    return {
        "overall_status": "pass" if not issues else "fail",
        "files": file_audits,
        "issues": issues,
    }


def _build_config_audit(
    *,
    label: str,
    input_kind: str,
    source_reference: str,
    config_path: Path,
    resolved_spec: dict[str, Any],
    registry_entry: dict[str, Any],
    record_first: dict[str, Any],
    record_second: dict[str, Any],
    replay_bundle: dict[str, Any],
    replay_config: dict[str, Any],
    metadata: dict[str, Any],
    preview_summary: dict[str, Any],
    deterministic_file_hashes: bool,
    descriptor_regeneration_matches_cache: bool,
    descriptor_regeneration_audit: dict[str, Any],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    compatibility = dict(resolved_spec.get("compatibility", {}))
    overall_status = "pass" if not issues else "fail"
    return {
        "stimulus_family": str(resolved_spec["stimulus_family"]),
        "stimulus_name": str(resolved_spec["stimulus_name"]),
        "label": label,
        "overall_status": overall_status,
        "input_kind": input_kind,
        "source_reference": source_reference,
        "config_path": str(config_path.resolve()),
        "requested_stimulus_family": str(resolved_spec["requested_stimulus_family"]),
        "requested_stimulus_name": str(resolved_spec["requested_stimulus_name"]),
        "compatibility_alias_used": bool(
            compatibility.get("family_alias_used") or compatibility.get("name_alias_used")
        ),
        "family_alias_used": bool(compatibility.get("family_alias_used")),
        "name_alias_used": bool(compatibility.get("name_alias_used")),
        "parameter_hash": str(resolved_spec["parameter_hash"]),
        "bundle_metadata_path": record_first.get("parsed_summary", {}).get("stimulus_bundle_metadata_path", ""),
        "bundle_directory": record_first.get("parsed_summary", {}).get("bundle_directory", ""),
        "record_first": record_first,
        "record_second": record_second,
        "replay_bundle": replay_bundle,
        "replay_config": replay_config,
        "deterministic_file_hashes": deterministic_file_hashes,
        "descriptor_regeneration_matches_cache": descriptor_regeneration_matches_cache,
        "descriptor_regeneration_audit": descriptor_regeneration_audit,
        "registry_entry": registry_entry,
        "bundle_metadata_contract_version": metadata.get("contract_version", ""),
        "preview_report_path": preview_summary.get("report_path", ""),
        "preview_summary_path": preview_summary.get("summary_path", ""),
        "selected_preview_frame_indices": preview_summary.get("selected_frame_indices", []),
        "selected_preview_frame_count": len(preview_summary.get("selected_frames", [])),
        "issues": issues,
    }


def _failed_family_audit(
    *,
    stimulus_family: str,
    input_kind: str,
    input_path: str | Path,
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "stimulus_family": stimulus_family,
        "stimulus_name": "",
        "label": stimulus_family,
        "overall_status": "fail",
        "input_kind": input_kind,
        "source_reference": str(input_path),
        "config_path": "",
        "requested_stimulus_family": "",
        "requested_stimulus_name": "",
        "compatibility_alias_used": False,
        "family_alias_used": False,
        "name_alias_used": False,
        "parameter_hash": "",
        "bundle_metadata_path": "",
        "bundle_directory": "",
        "record_first": {},
        "record_second": {},
        "replay_bundle": {},
        "replay_config": {},
        "deterministic_file_hashes": False,
        "descriptor_regeneration_matches_cache": False,
        "descriptor_regeneration_audit": {},
        "registry_entry": {},
        "bundle_metadata_contract_version": "",
        "preview_report_path": "",
        "preview_summary_path": "",
        "selected_preview_frame_indices": [],
        "selected_preview_frame_count": 0,
        "issues": issues,
    }


def _audit_descriptor_regeneration(metadata_path: Path) -> dict[str, Any]:
    metadata = load_stimulus_bundle_metadata(metadata_path)
    frame_cache_path = Path(metadata["assets"][FRAME_CACHE_KEY]["path"]).resolve()
    cache_replay = load_recorded_stimulus_bundle(metadata)
    backup_path = frame_cache_path.with_suffix(f"{frame_cache_path.suffix}.descriptor-check")
    if backup_path.exists():
        backup_path.unlink()
    frame_cache_path.rename(backup_path)
    try:
        descriptor_replay = load_recorded_stimulus_bundle(metadata)
    finally:
        backup_path.rename(frame_cache_path)
    return {
        "cache_replay_source": cache_replay.replay_source,
        "descriptor_replay_source": descriptor_replay.replay_source,
        "frame_arrays_equal": bool(np.array_equal(cache_replay.frames, descriptor_replay.frames)),
        "frame_times_equal": bool(
            np.array_equal(cache_replay.frame_times_ms, descriptor_replay.frame_times_ms)
        ),
        "render_metadata_equal": bool(cache_replay.render_metadata == descriptor_replay.render_metadata),
    }


def _select_replay_times(frame_times_ms: np.ndarray) -> list[float]:
    if frame_times_ms.size == 0:
        return []
    candidate_indices = sorted({0, int(frame_times_ms.size // 2), int(frame_times_ms.size - 1)})
    return [float(frame_times_ms[index]) for index in candidate_indices]


def _build_replay_command(
    *,
    python_executable: str,
    repo_root: Path,
    source_flag: str,
    source_value: str,
    replay_times_ms: list[float],
) -> list[str]:
    command = [
        python_executable,
        str(repo_root / "scripts" / "10_stimulus_bundle.py"),
        "replay",
        source_flag,
        source_value,
    ]
    for time_ms in replay_times_ms:
        command.extend(["--time-ms", str(time_ms)])
    return command


def _run_command(
    *,
    name: str,
    command: list[str],
    log_dir: Path,
    cwd: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    payload: dict[str, Any] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
        "stdout_log_path": str(stdout_path.resolve()),
        "stderr_log_path": str(stderr_path.resolve()),
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


def _snapshot_file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative_path = str(path.relative_to(root))
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _write_yaml(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _issue(severity: str, message: str) -> dict[str, str]:
    return {"severity": str(severity), "message": str(message)}


def _resolve_repo_path(value: Any, repo_root: Path, *, default: Path) -> Path:
    if value is None:
        return default.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _render_milestone8a_readiness_markdown(summary: dict[str, Any]) -> str:
    readiness = summary[FOLLOW_ON_READINESS_KEY]
    family_lines = [
        (
            f"- `{audit['stimulus_family']}` via `{audit['input_kind']}`: status `{audit['overall_status']}`; "
            f"bundle `{audit['bundle_metadata_path']}`; deterministic bytes `{audit['deterministic_file_hashes']}`; "
            f"descriptor replay matches cache `{audit['descriptor_regeneration_matches_cache']}`."
        )
        for audit in summary["family_audits"]
    ]
    follow_on_lines = [
        "- None."
        if not summary["follow_on_issues"]
        else "\n".join(
            f"- `{item['ticket_id']}`: {item['title']} ({item['reproduction']})"
            for item in summary["follow_on_issues"]
        )
    ][0]
    risk_lines = "\n".join(f"- {item}" for item in summary["remaining_risks"])
    documentation_status = summary["documentation_audit"]["overall_status"]
    manifest_status = summary["manifest_audit"]["overall_status"]
    registry_status = summary["registry_catalog_audit"]["overall_status"]
    return "\n".join(
        [
            "# Milestone 8A Readiness Report",
            "",
            f"- Report version: `{summary['report_version']}`",
            f"- Readiness verdict: `{readiness['status']}`",
            f"- Ready for Milestones 8B, 8C, and later orchestration: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
            f"- Processed stimulus directory: `{summary['processed_stimulus_dir']}`",
            f"- Report directory: `{summary['report_dir']}`",
            f"- Focused fixture verification: `{summary['fixture_verification'].get('status', 'skipped')}`",
            f"- Registry coverage audit: `{registry_status}`",
            f"- Manifest entrypoint audit: `{manifest_status}`",
            f"- Documentation audit: `{documentation_status}`",
            "",
            "## Families Exercised",
            *family_lines,
            "",
            "## Compatibility Checks",
            f"- Required family coverage matched the Milestone 8A contract set: `{summary['family_coverage_ok']}`.",
            f"- The example manifest resolved through the canonical registry as `{summary['manifest_audit']['validation_summary'].get('resolved_stimulus_family', '')}/{summary['manifest_audit']['validation_summary'].get('resolved_stimulus_name', '')}`.",
            f"- The manifest compatibility alias path remained active: `{summary['manifest_audit']['validation_summary'].get('resolved_stimulus', {}).get('compatibility', {}).get('family_alias_used', False)}` family alias, `{summary['manifest_audit']['validation_summary'].get('resolved_stimulus', {}).get('compatibility', {}).get('name_alias_used', False)}` name alias.",
            f"- Repeated manifest recording preserved deterministic bundle bytes: `{summary['manifest_audit'].get('deterministic_file_hashes', False)}`.",
            "",
            "## Risks And Follow-On",
            risk_lines,
            follow_on_lines,
            "",
            "## Report Files",
            f"- Markdown: `{summary['markdown_path']}`",
            f"- JSON: `{summary['json_path']}`",
            f"- Command logs: `{summary['commands_dir']}`",
        ]
    ).strip() + "\n"
