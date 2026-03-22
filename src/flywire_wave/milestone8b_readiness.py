from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .config import REPO_ROOT, load_config
from .io_utils import ensure_dir, write_json
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .retinal_bundle import load_recorded_retinal_bundle
from .retinal_contract import RETINAL_INPUT_BUNDLE_CONTRACT_VERSION
from .retinal_workflow import resolve_retinal_bundle_input


MILESTONE8B_READINESS_REPORT_VERSION = "milestone8b_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_manifest_validation",
    "tests.test_stimulus_bundle_workflow",
    "tests.test_retinal_contract",
    "tests.test_retinal_geometry",
    "tests.test_retinal_sampling",
    "tests.test_retinal_bundle",
    "tests.test_retinal_bundle_workflow",
    "tests.test_retinal_inspection",
    "tests.test_milestone8b_readiness",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "docs/retinal_bundle_workflow.md": (
        "python scripts/12_retinal_bundle.py record",
        "python scripts/12_retinal_bundle.py replay",
        "python scripts/12_retinal_bundle.py inspect",
        "make milestone8b-readiness",
        "python scripts/13_milestone8b_readiness.py --config config/milestone_8b_verification.yaml",
        "milestone_8b_readiness.md",
        "milestone_8b_readiness.json",
    ),
    "docs/retinal_inspection.md": (
        "make milestone8b-readiness",
        "python scripts/13_milestone8b_readiness.py --config config/milestone_8b_verification.yaml",
        "milestone_8b_readiness.md",
        "milestone_8b_readiness.json",
    ),
    "docs/pipeline_notes.md": (
        "make milestone8b-readiness",
        "scripts/13_milestone8b_readiness.py",
        "milestone_8b_readiness.md",
        "milestone_8b_readiness.json",
    ),
    "README.md": (
        "make milestone8b-readiness",
        "scripts/13_milestone8b_readiness.py",
        "milestone_8b_readiness.md",
        "milestone_8b_readiness.json",
    ),
}

DEFAULT_VERIFICATION_STIMULUS = {
    "stimulus_family": "translated_edge",
    "stimulus_name": "simple_translated_edge",
    "determinism": {
        "seed": 11,
    },
    "temporal_sampling": {
        "time_origin_ms": 0.0,
        "dt_ms": 20.0,
        "duration_ms": 80.0,
    },
    "spatial_frame": {
        "width_px": 96,
        "height_px": 64,
        "width_deg": 180.0,
        "height_deg": 120.0,
    },
    "stimulus_overrides": {
        "onset_ms": 0.0,
        "offset_ms": 80.0,
        "background_level": 0.25,
        "contrast": 0.6,
        "velocity_deg_per_s": 24.0,
        "edge_width_deg": 10.0,
    },
}

DEFAULT_VERIFICATION_SCENE = {
    "scene_family": "analytic_panorama",
    "scene_name": "yaw_gradient_panorama",
    "temporal_sampling": {
        "time_origin_ms": 0.0,
        "dt_ms": 20.0,
        "duration_ms": 80.0,
    },
    "scene_parameters": {
        "background_level": 0.45,
        "azimuth_gain_per_deg": 0.001,
        "elevation_gain_per_deg": 0.0005,
        "temporal_modulation_amplitude": 0.1,
        "temporal_frequency_hz": 2.0,
        "phase_deg": 15.0,
    },
}

DEFAULT_VERIFICATION_RETINAL_GEOMETRY = {
    "geometry_name": "fixture",
    "eyes": {
        "left": {
            "optical_axis_head": [1.0, 0.0, 0.0],
            "torsion_deg": 0.0,
        },
        "symmetry": {
            "mode": "mirror_across_head_sagittal_plane",
        },
    },
}

DEFAULT_VERIFICATION_RETINAL_RECORDING = {
    "sampling_kernel": {
        "acceptance_angle_deg": 0.5,
        "support_radius_deg": 1.0,
        "background_fill_value": 0.25,
    },
    "body_pose": {
        "translation_world_mm": [0.0, 0.0, 0.0],
        "yaw_pitch_roll_deg": [2.0, 0.0, 0.0],
    },
    "head_pose": {
        "translation_body_mm": [0.32, 0.0, 0.1],
        "yaw_pitch_roll_deg": [2.0, 0.0, 0.0],
    },
}


def build_milestone8b_readiness_paths(processed_retinal_dir: str | Path) -> dict[str, Path]:
    root = Path(processed_retinal_dir).resolve()
    report_dir = root / "readiness" / "milestone_8b"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_8b_readiness.md",
        "json_path": report_dir / "milestone_8b_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_inputs_dir": report_dir / "generated_inputs",
    }


def execute_milestone8b_readiness_pass(
    *,
    config_path: str | Path,
    fixture_verification: Mapping[str, Any],
    python_executable: str = sys.executable,
    root_dir: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = Path(root_dir).resolve()
    cfg = load_config(config_path, project_root=repo_root)
    processed_stimulus_dir = Path(cfg["paths"]["processed_stimulus_dir"]).resolve()
    processed_retinal_dir = Path(cfg["paths"]["processed_retinal_dir"]).resolve()
    verification_cfg = dict(cfg.get("retinal_verification", {}))

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

    readiness_paths = build_milestone8b_readiness_paths(processed_retinal_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_inputs_dir = ensure_dir(readiness_paths["generated_inputs_dir"])

    generated_inputs = _generate_verification_inputs(
        verification_cfg=verification_cfg,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
        generated_inputs_dir=generated_inputs_dir,
    )

    entrypoint_audits = [
        _exercise_entrypoint(
            label="stimulus_config",
            entrypoint_kind="config",
            entrypoint_args=["--config", str(generated_inputs["stimulus_config_path"])],
            resolve_kwargs={"config_path": generated_inputs["stimulus_config_path"]},
            expected_source_kind="stimulus_bundle",
            expected_source_family="translated_edge",
            expected_source_name="simple_translated_edge",
            commands_dir=commands_dir,
            python_executable=python_executable,
            repo_root=repo_root,
        ),
        _exercise_entrypoint(
            label="manifest_demo",
            entrypoint_kind="manifest",
            entrypoint_args=[
                "--manifest",
                str(manifest_path),
                "--retinal-config",
                str(generated_inputs["manifest_retinal_config_path"]),
                "--schema",
                str(schema_path),
                "--design-lock",
                str(design_lock_path),
            ],
            resolve_kwargs={
                "manifest_path": manifest_path,
                "retinal_config_path": generated_inputs["manifest_retinal_config_path"],
                "schema_path": schema_path,
                "design_lock_path": design_lock_path,
            },
            expected_source_kind="stimulus_bundle",
            expected_source_family="translated_edge",
            expected_source_name="simple_translated_edge",
            commands_dir=commands_dir,
            python_executable=python_executable,
            repo_root=repo_root,
        ),
        _exercise_entrypoint(
            label="scene_entrypoint",
            entrypoint_kind="scene",
            entrypoint_args=["--scene", str(generated_inputs["scene_entrypoint_path"])],
            resolve_kwargs={"scene_path": generated_inputs["scene_entrypoint_path"]},
            expected_source_kind="scene_description",
            expected_source_family="analytic_panorama",
            expected_source_name="yaw_gradient_panorama",
            commands_dir=commands_dir,
            python_executable=python_executable,
            repo_root=repo_root,
        ),
    ]
    documentation_audit = _audit_documentation(repo_root=repo_root)
    workflow_coverage = _build_workflow_coverage(entrypoint_audits)

    blocking_issues = (
        [issue for audit in entrypoint_audits for issue in audit["issues"] if issue["severity"] == "blocking"]
        + [issue for issue in documentation_audit["issues"] if issue["severity"] == "blocking"]
    )
    warning_issues = (
        [issue for audit in entrypoint_audits for issue in audit["issues"] if issue["severity"] != "blocking"]
        + [issue for issue in documentation_audit["issues"] if issue["severity"] != "blocking"]
    )

    fixture_status = str(fixture_verification.get("status", "skipped"))
    docs_status = str(documentation_audit.get("overall_status", "fail"))
    audit_statuses = {audit["label"]: audit["overall_status"] for audit in entrypoint_audits}

    if (
        fixture_status != "pass"
        or docs_status != "pass"
        or any(status == "fail" for status in audit_statuses.values())
        or blocking_issues
    ):
        readiness_status = READINESS_GATE_HOLD
    elif any(status == "warn" for status in audit_statuses.values()) or warning_issues:
        readiness_status = READINESS_GATE_REVIEW
    else:
        readiness_status = "ready"

    remaining_risks = [
        "The readiness pass exercises the shipped fixture hex lattice and one analytic panorama scene only; it does not yet validate a biologically calibrated ommatidial lattice or depth-bearing scene family.",
        "The simulator handoff remains the v1 identity irradiance mapping. Any adapted, opponent, or motion-energy retinal features will need a new versioned extension instead of silent reuse of retinal_input_bundle.v1.",
    ]
    follow_on_issues = [
        {
            "ticket_id": "FW-M8C-001",
            "title": "Add one local depth or occlusion-bearing scene family to the Milestone 8B readiness suite.",
            "reproduction": (
                "Run `make milestone8b-readiness` and inspect the scene-entrypoint audit in the readiness report. "
                "The current world-to-retina verification covers only the analytic panorama fixture scene."
            ),
        },
        {
            "ticket_id": "FW-M9-002",
            "title": "Version non-identity early-visual feature channels before simulator work depends on adapted retinal inputs.",
            "reproduction": (
                "Run `make milestone8b-readiness` and inspect the readiness report. "
                "The local simulator-facing retinal handoff passes with `early_visual_unit_stack` and a single identity `irradiance` channel only."
            ),
        },
    ]

    summary = {
        "report_version": MILESTONE8B_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir),
        "processed_retinal_dir": str(processed_retinal_dir),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "commands_dir": str(commands_dir.resolve()),
        "generated_inputs_dir": str(generated_inputs_dir.resolve()),
        "documented_verification_command": "make milestone8b-readiness",
        "explicit_verification_command": "python scripts/13_milestone8b_readiness.py --config config/milestone_8b_verification.yaml",
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "manifest_path": str(manifest_path.resolve()),
        "schema_path": str(schema_path.resolve()),
        "design_lock_path": str(design_lock_path.resolve()),
        "generated_inputs": {
            key: str(value.resolve()) for key, value in generated_inputs.items()
        },
        "entrypoint_audits": {audit["label"]: audit for audit in entrypoint_audits},
        "workflow_coverage": workflow_coverage,
        "documentation_audit": documentation_audit,
        "remaining_risks": remaining_risks,
        "follow_on_issues": follow_on_issues,
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            "local_retinal_gate": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_milestones": ["8C", "9", "later_ui_review"],
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone8b_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _generate_verification_inputs(
    *,
    verification_cfg: Mapping[str, Any],
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
    generated_inputs_dir: Path,
) -> dict[str, Path]:
    stimulus_payload = _deep_merge_mappings(
        DEFAULT_VERIFICATION_STIMULUS,
        verification_cfg.get("stimulus"),
        field_name="retinal_verification.stimulus",
    )
    scene_payload = _deep_merge_mappings(
        DEFAULT_VERIFICATION_SCENE,
        verification_cfg.get("scene"),
        field_name="retinal_verification.scene",
    )
    retinal_geometry_payload = _deep_merge_mappings(
        DEFAULT_VERIFICATION_RETINAL_GEOMETRY,
        verification_cfg.get("retinal_geometry"),
        field_name="retinal_verification.retinal_geometry",
    )
    retinal_recording_payload = _deep_merge_mappings(
        DEFAULT_VERIFICATION_RETINAL_RECORDING,
        verification_cfg.get("retinal_recording"),
        field_name="retinal_verification.retinal_recording",
    )

    stimulus_config_path = generated_inputs_dir / "stimulus_config.yaml"
    manifest_retinal_config_path = generated_inputs_dir / "manifest_retinal_config.yaml"
    scene_entrypoint_path = generated_inputs_dir / "scene_entrypoint.yaml"

    _write_yaml(
        {
            "paths": {
                "processed_stimulus_dir": str(processed_stimulus_dir),
                "processed_retinal_dir": str(processed_retinal_dir),
            },
            "stimulus": stimulus_payload,
            "retinal_geometry": retinal_geometry_payload,
            "retinal_recording": retinal_recording_payload,
        },
        stimulus_config_path,
    )
    _write_yaml(
        {
            "paths": {
                "processed_stimulus_dir": str(processed_stimulus_dir),
                "processed_retinal_dir": str(processed_retinal_dir),
            },
            "retinal_geometry": retinal_geometry_payload,
            "retinal_recording": retinal_recording_payload,
        },
        manifest_retinal_config_path,
    )
    _write_yaml(
        {
            "paths": {
                "processed_stimulus_dir": str(processed_stimulus_dir),
                "processed_retinal_dir": str(processed_retinal_dir),
            },
            "scene": scene_payload,
            "retinal_geometry": retinal_geometry_payload,
            "retinal_recording": retinal_recording_payload,
        },
        scene_entrypoint_path,
    )
    return {
        "stimulus_config_path": stimulus_config_path,
        "manifest_retinal_config_path": manifest_retinal_config_path,
        "scene_entrypoint_path": scene_entrypoint_path,
    }


def _exercise_entrypoint(
    *,
    label: str,
    entrypoint_kind: str,
    entrypoint_args: list[str],
    resolve_kwargs: dict[str, Any],
    expected_source_kind: str,
    expected_source_family: str,
    expected_source_name: str,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    script_path = repo_root / "scripts" / "12_retinal_bundle.py"
    command_results: dict[str, dict[str, Any]] = {}
    predicted_metadata_path: Path | None = None
    resolved_input_summary: dict[str, Any] = {}

    try:
        resolved_input = resolve_retinal_bundle_input(**resolve_kwargs)
        predicted_metadata_path = resolved_input.retinal_bundle_metadata_path.resolve()
        resolved_input_summary = {
            "entrypoint_kind": resolved_input.entrypoint_kind,
            "entrypoint_path": str(resolved_input.entrypoint_path),
            "predicted_metadata_path": str(predicted_metadata_path),
            "source_descriptor": copy.deepcopy(resolved_input.source_descriptor),
            "frame_times_ms": [_rounded_float(value) for value in resolved_input.frame_times_ms],
            "retinal_geometry": {
                "geometry_family": resolved_input.retinal_geometry.geometry_family,
                "geometry_name": resolved_input.retinal_geometry.geometry_name,
                "ommatidium_count_per_eye": resolved_input.retinal_geometry.ommatidium_count_per_eye,
            },
        }
    except Exception as exc:
        issues.append(
            _issue(
                "blocking",
                f"{label} could not resolve the retinal workflow through the library audit path: {exc}",
            )
        )
        return {
            "label": label,
            "entrypoint_kind": entrypoint_kind,
            "overall_status": "fail",
            "issues": issues,
            "resolved_input": resolved_input_summary,
            "commands": command_results,
        }

    source_descriptor = resolved_input.source_descriptor
    if source_descriptor["source_kind"] != expected_source_kind:
        issues.append(
            _issue(
                "blocking",
                f"{label} resolved source_kind={source_descriptor['source_kind']!r}, expected {expected_source_kind!r}.",
            )
        )
    if source_descriptor["source_family"] != expected_source_family:
        issues.append(
            _issue(
                "blocking",
                f"{label} resolved source_family={source_descriptor['source_family']!r}, expected {expected_source_family!r}.",
            )
        )
    if source_descriptor["source_name"] != expected_source_name:
        issues.append(
            _issue(
                "blocking",
                f"{label} resolved source_name={source_descriptor['source_name']!r}, expected {expected_source_name!r}.",
            )
        )

    record_command = [python_executable, str(script_path), "record", *entrypoint_args]
    command_results["record_1"] = _run_json_command(
        name=f"{label}_record_1",
        command=record_command,
        log_dir=commands_dir,
        repo_root=repo_root,
    )
    if command_results["record_1"]["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                f"{label} record command failed on the first run; see {command_results['record_1']['stderr_log_path']}.",
            )
        )
        return _finalize_entrypoint_audit(
            label=label,
            entrypoint_kind=entrypoint_kind,
            issues=issues,
            resolved_input_summary=resolved_input_summary,
            command_results=command_results,
        )

    record_summary_1 = command_results["record_1"].get("parsed_summary")
    if not isinstance(record_summary_1, Mapping):
        issues.append(
            _issue(
                "blocking",
                f"{label} record command did not emit a parseable JSON summary on the first run.",
            )
        )
        return _finalize_entrypoint_audit(
            label=label,
            entrypoint_kind=entrypoint_kind,
            issues=issues,
            resolved_input_summary=resolved_input_summary,
            command_results=command_results,
        )

    metadata_path = Path(record_summary_1["retinal_bundle_metadata_path"]).resolve()
    frame_archive_path = Path(record_summary_1["frame_archive_path"]).resolve()
    first_record_hashes = _hash_existing_files([metadata_path, frame_archive_path])

    command_results["record_2"] = _run_json_command(
        name=f"{label}_record_2",
        command=record_command,
        log_dir=commands_dir,
        repo_root=repo_root,
    )
    if command_results["record_2"]["status"] != "pass":
        issues.append(
            _issue(
                "blocking",
                f"{label} record command failed on the second run; see {command_results['record_2']['stderr_log_path']}.",
            )
        )
        return _finalize_entrypoint_audit(
            label=label,
            entrypoint_kind=entrypoint_kind,
            issues=issues,
            resolved_input_summary=resolved_input_summary,
            command_results=command_results,
            metadata_path=metadata_path,
            frame_archive_path=frame_archive_path,
            record_file_hashes={"first": first_record_hashes},
        )

    record_summary_2 = command_results["record_2"].get("parsed_summary")
    if not isinstance(record_summary_2, Mapping):
        issues.append(
            _issue(
                "blocking",
                f"{label} record command did not emit a parseable JSON summary on the second run.",
            )
        )
        return _finalize_entrypoint_audit(
            label=label,
            entrypoint_kind=entrypoint_kind,
            issues=issues,
            resolved_input_summary=resolved_input_summary,
            command_results=command_results,
            metadata_path=metadata_path,
            frame_archive_path=frame_archive_path,
            record_file_hashes={"first": first_record_hashes},
        )

    second_record_hashes = _hash_existing_files([metadata_path, frame_archive_path])
    record_paths_stable = (
        record_summary_1["retinal_bundle_metadata_path"] == record_summary_2["retinal_bundle_metadata_path"]
        and record_summary_1["frame_archive_path"] == record_summary_2["frame_archive_path"]
    )
    record_hashes_stable = first_record_hashes == second_record_hashes
    predicted_bundle_path_matches = predicted_metadata_path == metadata_path

    replay_times = _default_replay_times_ms(resolved_input.frame_times_ms)
    replay_time_args = _build_time_arguments(replay_times)

    command_results["replay_entrypoint"] = _run_json_command(
        name=f"{label}_replay_entrypoint",
        command=[python_executable, str(script_path), "replay", *entrypoint_args, *replay_time_args],
        log_dir=commands_dir,
        repo_root=repo_root,
    )
    command_results["replay_bundle"] = _run_json_command(
        name=f"{label}_replay_bundle",
        command=[
            python_executable,
            str(script_path),
            "replay",
            "--bundle-metadata",
            str(metadata_path),
            *replay_time_args,
        ],
        log_dir=commands_dir,
        repo_root=repo_root,
    )

    command_results["inspect_entrypoint"] = _run_json_command(
        name=f"{label}_inspect_entrypoint",
        command=[python_executable, str(script_path), "inspect", *entrypoint_args],
        log_dir=commands_dir,
        repo_root=repo_root,
    )
    inspect_entrypoint_summary = command_results["inspect_entrypoint"].get("parsed_summary")

    inspection_paths: list[Path] = [metadata_path]
    first_inspection_hashes: dict[str, str] = {}
    if isinstance(inspect_entrypoint_summary, Mapping):
        inspection_paths.extend(_inspection_artifact_paths(inspect_entrypoint_summary))
        first_inspection_hashes = _hash_existing_files(inspection_paths)

    command_results["inspect_bundle"] = _run_json_command(
        name=f"{label}_inspect_bundle",
        command=[
            python_executable,
            str(script_path),
            "inspect",
            "--bundle-metadata",
            str(metadata_path),
        ],
        log_dir=commands_dir,
        repo_root=repo_root,
    )
    inspect_bundle_summary = command_results["inspect_bundle"].get("parsed_summary")
    second_inspection_hashes = _hash_existing_files(inspection_paths)

    if not record_paths_stable:
        issues.append(
            _issue(
                "blocking",
                f"{label} record path resolution drifted across repeated runs.",
            )
        )
    if not record_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                f"{label} record artifacts changed bytes across repeated runs at {metadata_path.parent}.",
            )
        )
    if not predicted_bundle_path_matches:
        issues.append(
            _issue(
                "blocking",
                f"{label} resolved bundle path {predicted_metadata_path} did not match the record command output {metadata_path}.",
            )
        )

    replay = load_recorded_retinal_bundle(metadata_path)
    entrypoint_replay_summary = command_results["replay_entrypoint"].get("parsed_summary")
    bundle_replay_summary = command_results["replay_bundle"].get("parsed_summary")
    resolved_replay_matches_bundle_replay = False
    sample_hold_indices_match = False
    if isinstance(entrypoint_replay_summary, Mapping) and isinstance(bundle_replay_summary, Mapping):
        resolved_replay_matches_bundle_replay = (
            entrypoint_replay_summary.get("requested_samples")
            == bundle_replay_summary.get("requested_samples")
        )
        expected_indices = [int(replay.frame_index_for_time_ms(time_ms)) for time_ms in replay_times]
        observed_samples = bundle_replay_summary.get("requested_samples", [])
        observed_indices = [
            int(sample["frame_index"])
            for sample in observed_samples
            if isinstance(sample, Mapping) and "frame_index" in sample
        ]
        sample_hold_indices_match = observed_indices == expected_indices

    if not resolved_replay_matches_bundle_replay:
        issues.append(
            _issue(
                "blocking",
                f"{label} replay via entrypoint did not match replay via explicit bundle metadata discovery.",
            )
        )
    if not sample_hold_indices_match:
        issues.append(
            _issue(
                "blocking",
                f"{label} replay did not preserve the expected sample-hold frame indexing semantics.",
            )
        )

    timing_matches_resolved_input = bool(
        np.allclose(replay.frame_times_ms, resolved_input.frame_times_ms, atol=0.0, rtol=0.0)
    )
    if not timing_matches_resolved_input:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded frame times drifted from the resolved source timing grid.",
            )
        )

    source_reference = replay.bundle_metadata["source_reference"]
    source_metadata = replay.source_descriptor.get("source_metadata", {})
    lineage = source_metadata.get("lineage", {})
    lineage_transforms = lineage.get("effective_transforms", {})
    projector_transforms = replay.projector_metadata.get("effective_transforms", {})
    transform_metadata_consistent = (
        _transforms_compatible(lineage_transforms.get("world_to_body"), projector_transforms.get("world_to_body"))
        and _transforms_compatible(lineage_transforms.get("body_to_head"), projector_transforms.get("body_to_head"))
    )
    if not transform_metadata_consistent:
        issues.append(
            _issue(
                "blocking",
                f"{label} source-lineage transform metadata did not match the realized projector metadata.",
            )
        )

    if replay.bundle_metadata["contract_version"] != RETINAL_INPUT_BUNDLE_CONTRACT_VERSION:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded contract_version={replay.bundle_metadata['contract_version']!r}, expected {RETINAL_INPUT_BUNDLE_CONTRACT_VERSION!r}.",
            )
        )
    if source_reference["source_kind"] != expected_source_kind:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded source_kind={source_reference['source_kind']!r}, expected {expected_source_kind!r}.",
            )
        )
    if source_reference["source_family"] != expected_source_family:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded source_family={source_reference['source_family']!r}, expected {expected_source_family!r}.",
            )
        )
    if source_reference["source_name"] != expected_source_name:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded source_name={source_reference['source_name']!r}, expected {expected_source_name!r}.",
            )
        )

    coordinate_frames_match = (
        replay.bundle_metadata["coordinate_frames"] == resolved_input.retinal_geometry.build_coordinate_frames()
    )
    if not coordinate_frames_match:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded coordinate frames drifted from the resolved retinal geometry contract.",
            )
        )

    eye_sampling = replay.bundle_metadata["eye_sampling"]
    geometry_compatible = (
        eye_sampling["geometry_family"] == resolved_input.retinal_geometry.geometry_family
        and eye_sampling["geometry_name"] == resolved_input.retinal_geometry.geometry_name
        and eye_sampling["ommatidium_count_per_eye"] == resolved_input.retinal_geometry.ommatidium_count_per_eye
    )
    if not geometry_compatible:
        issues.append(
            _issue(
                "blocking",
                f"{label} recorded eye-sampling metadata drifted from the resolved retinal geometry.",
            )
        )

    inspection_summary_payload = _load_json_if_exists(
        Path(inspect_bundle_summary["summary_path"]).resolve()
        if isinstance(inspect_bundle_summary, Mapping) and inspect_bundle_summary.get("summary_path")
        else None
    ) or {}
    inspection_summary_path_text = ""
    if isinstance(inspect_bundle_summary, Mapping):
        inspection_summary_path_text = str(inspect_bundle_summary.get("summary_path", ""))
    if inspection_summary_payload.get("summary_path"):
        inspection_summary_path_text = str(inspection_summary_payload["summary_path"])
    qa_status = str(inspection_summary_payload.get("qa", {}).get("overall_status", "fail"))
    coverage_status = str(inspection_summary_payload.get("coverage", {}).get("overall_status", "fail"))
    source_preview_available = bool(inspection_summary_payload.get("source_preview", {}).get("available", False))
    inspection_hashes_stable = first_inspection_hashes == second_inspection_hashes and bool(first_inspection_hashes)

    if not inspection_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                f"{label} inspection artifacts changed bytes across repeated runs at {metadata_path.parent / 'inspection'}.",
            )
        )
    if not source_preview_available:
        issues.append(
            _issue(
                "blocking",
                f"{label} inspection could not reconstruct a local world-view preview from the recorded source lineage.",
            )
        )
    if qa_status == "fail":
        issues.append(
            _issue(
                "blocking",
                f"{label} inspection QA failed; review {inspection_summary_path_text}.",
            )
        )
    elif qa_status == "warn":
        issues.append(
            _issue(
                "warning",
                f"{label} inspection QA emitted warnings; review {inspection_summary_path_text}.",
            )
        )
    if coverage_status == "fail":
        issues.append(
            _issue(
                "blocking",
                f"{label} detector coverage failed; one or more ommatidia fell fully out of field.",
            )
        )
    elif coverage_status == "warn":
        issues.append(
            _issue(
                "warning",
                f"{label} detector coverage was partially clipped and should be reviewed before downstream simulator use.",
            )
        )

    return _finalize_entrypoint_audit(
        label=label,
        entrypoint_kind=entrypoint_kind,
        issues=issues,
        resolved_input_summary=resolved_input_summary,
        command_results=command_results,
        metadata_path=metadata_path,
        frame_archive_path=frame_archive_path,
        record_file_hashes={
            "first": first_record_hashes,
            "second": second_record_hashes,
        },
        inspection_file_hashes={
            "first": first_inspection_hashes,
            "second": second_inspection_hashes,
        },
        source_reference=copy.deepcopy(source_reference),
        workflow_checks={
            "predicted_bundle_path_matches": predicted_bundle_path_matches,
            "record_paths_stable": record_paths_stable,
            "record_hashes_stable": record_hashes_stable,
            "resolved_replay_matches_bundle_replay": resolved_replay_matches_bundle_replay,
            "sample_hold_indices_match": sample_hold_indices_match,
            "timing_matches_resolved_input": timing_matches_resolved_input,
            "transform_metadata_consistent": transform_metadata_consistent,
            "coordinate_frames_match": coordinate_frames_match,
            "geometry_compatible": geometry_compatible,
            "inspection_hashes_stable": inspection_hashes_stable,
            "source_preview_available": source_preview_available,
        },
        replay_summary=copy.deepcopy(bundle_replay_summary) if isinstance(bundle_replay_summary, Mapping) else {},
        inspection_summary=inspection_summary_payload,
    )


def _build_workflow_coverage(entrypoint_audits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    audit_map = {str(audit["label"]): audit for audit in entrypoint_audits}
    return {
        "entrypoints_exercised": sorted(audit_map.keys()),
        "bundle_discovery_compatible": all(
            bool(audit.get("workflow_checks", {}).get("resolved_replay_matches_bundle_replay"))
            for audit in entrypoint_audits
        ),
        "coordinate_transforms_compatible": all(
            bool(audit.get("workflow_checks", {}).get("transform_metadata_consistent"))
            for audit in entrypoint_audits
        ),
        "projection_and_sampling_compatible": all(
            str(audit.get("inspection", {}).get("qa_overall_status", "fail")) == "pass"
            for audit in entrypoint_audits
        ),
        "temporal_bundling_compatible": all(
            bool(audit.get("workflow_checks", {}).get("timing_matches_resolved_input"))
            and bool(audit.get("workflow_checks", {}).get("sample_hold_indices_match"))
            for audit in entrypoint_audits
        ),
        "offline_inspection_compatible": all(
            bool(audit.get("workflow_checks", {}).get("inspection_hashes_stable"))
            and bool(audit.get("workflow_checks", {}).get("source_preview_available"))
            for audit in entrypoint_audits
        ),
        "stimulus_config_ready": str(audit_map.get("stimulus_config", {}).get("overall_status", "fail")) == "pass",
        "manifest_ready": str(audit_map.get("manifest_demo", {}).get("overall_status", "fail")) == "pass",
        "scene_ready": str(audit_map.get("scene_entrypoint", {}).get("overall_status", "fail")) == "pass",
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
                    f"{relative_path} is missing, so the Milestone 8B readiness workflow is not documented there.",
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
                    f"{relative_path} is missing the Milestone 8B readiness snippets {missing_snippets!r}.",
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


def _finalize_entrypoint_audit(
    *,
    label: str,
    entrypoint_kind: str,
    issues: list[dict[str, str]],
    resolved_input_summary: Mapping[str, Any],
    command_results: Mapping[str, Any],
    metadata_path: Path | None = None,
    frame_archive_path: Path | None = None,
    record_file_hashes: Mapping[str, Any] | None = None,
    inspection_file_hashes: Mapping[str, Any] | None = None,
    source_reference: Mapping[str, Any] | None = None,
    workflow_checks: Mapping[str, Any] | None = None,
    replay_summary: Mapping[str, Any] | None = None,
    inspection_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    overall_status = "pass"
    if any(issue["severity"] == "blocking" for issue in issues):
        overall_status = "fail"
    elif issues:
        overall_status = "warn"

    return {
        "label": label,
        "entrypoint_kind": entrypoint_kind,
        "overall_status": overall_status,
        "issues": issues,
        "resolved_input": copy.deepcopy(dict(resolved_input_summary)),
        "commands": copy.deepcopy(dict(command_results)),
        "retinal_bundle_metadata_path": str(metadata_path.resolve()) if metadata_path is not None else None,
        "frame_archive_path": str(frame_archive_path.resolve()) if frame_archive_path is not None else None,
        "record_file_hashes": copy.deepcopy(dict(record_file_hashes or {})),
        "inspection_file_hashes": copy.deepcopy(dict(inspection_file_hashes or {})),
        "source_reference": copy.deepcopy(dict(source_reference or {})),
        "workflow_checks": copy.deepcopy(dict(workflow_checks or {})),
        "replay": {
            "summary": copy.deepcopy(dict(replay_summary or {})),
        },
        "inspection": {
            "summary": copy.deepcopy(dict(inspection_summary or {})),
            "qa_overall_status": str(inspection_summary.get("qa", {}).get("overall_status", "")) if inspection_summary else "",
            "coverage_overall_status": (
                str(inspection_summary.get("coverage", {}).get("overall_status", "")) if inspection_summary else ""
            ),
            "summary_path": str(inspection_summary.get("summary_path", "")) if inspection_summary else "",
            "report_path": str(inspection_summary.get("report_path", "")) if inspection_summary else "",
        },
    }


def _default_replay_times_ms(frame_times_ms: Sequence[float] | np.ndarray) -> list[float]:
    times = np.asarray(frame_times_ms, dtype=np.float64)
    if times.size == 0:
        return []
    if times.size == 1:
        return [_rounded_float(times[0])]
    dt_ms = float(times[1] - times[0])
    middle_index = min(1, times.size - 1)
    last_index = int(times.size - 1)
    return [
        _rounded_float(float(times[0])),
        _rounded_float(float(times[middle_index] + 0.25 * dt_ms)),
        _rounded_float(float(times[last_index] + 0.45 * dt_ms)),
    ]


def _build_time_arguments(time_ms: Sequence[float]) -> list[str]:
    args: list[str] = []
    for value in time_ms:
        args.extend(["--time-ms", f"{float(value):.12g}"])
    return args


def _inspection_artifact_paths(summary: Mapping[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for key in ("report_path", "summary_path", "markdown_path", "coverage_layout_svg_path"):
        value = summary.get(key)
        if isinstance(value, str) and value:
            paths.append(Path(value).resolve())
    for frame_record in summary.get("selected_frames", []):
        if not isinstance(frame_record, Mapping):
            continue
        for key in ("world_view_svg_path", "retinal_view_svg_path"):
            value = frame_record.get(key)
            if isinstance(value, str) and value:
                paths.append(Path(value).resolve())
    return paths


def _run_json_command(
    *,
    name: str,
    command: list[str],
    log_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_log_path = (log_dir / f"{name}.stdout.txt").resolve()
    stderr_log_path = (log_dir / f"{name}.stderr.txt").resolve()
    stdout_log_path.write_text(result.stdout, encoding="utf-8")
    stderr_log_path.write_text(result.stderr, encoding="utf-8")

    payload: dict[str, Any] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
        "stdout_log_path": str(stdout_log_path),
        "stderr_log_path": str(stderr_log_path),
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
    if isinstance(payload, dict):
        return payload
    return None


def _load_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return None
    return payload


def _hash_existing_files(paths: Sequence[Path]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in paths:
        resolved = Path(path).resolve()
        if resolved.exists() and resolved.is_file():
            digests[str(resolved)] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return digests


def _transforms_compatible(left: Any, right: Any) -> bool:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return False
    return {
        "source_frame": str(left.get("source_frame", "")),
        "target_frame": str(left.get("target_frame", "")),
        "rotation_matrix": left.get("rotation_matrix"),
        "translation_vector_mm": left.get("translation_vector_mm", left.get("translation_vector", [])),
    } == {
        "source_frame": str(right.get("source_frame", "")),
        "target_frame": str(right.get("target_frame", "")),
        "rotation_matrix": right.get("rotation_matrix"),
        "translation_vector_mm": right.get("translation_vector_mm", right.get("translation_vector", [])),
    }


def _deep_merge_mappings(
    defaults: Mapping[str, Any],
    overrides: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if overrides is None:
        return copy.deepcopy(dict(defaults))
    if not isinstance(overrides, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    merged = copy.deepcopy(dict(defaults))
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge_mappings(
                merged[key],
                value,
                field_name=f"{field_name}.{key}",
            )
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_repo_path(value: Any, repo_root: Path, *, default: Path) -> Path:
    candidate = default if value is None else Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _write_yaml(payload: Mapping[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def _issue(severity: str, message: str) -> dict[str, str]:
    return {
        "severity": str(severity),
        "message": str(message),
    }


def _rounded_float(value: float) -> float:
    return round(float(value), 12)


def _render_milestone8b_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    entrypoint_audits = dict(summary["entrypoint_audits"])
    documentation_audit = dict(summary["documentation_audit"])
    workflow_coverage = dict(summary["workflow_coverage"])

    lines = [
        "# Milestone 8B Readiness Report",
        "",
        "## Verdict",
        "",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Local retinal gate: `{readiness['local_retinal_gate']}`",
        f"- Ready for Milestones 8C and 9 follow-on work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Verification command: `{summary['documented_verification_command']}`",
        f"- Explicit command: `{summary['explicit_verification_command']}`",
        "",
        "## Workflow Coverage",
        "",
        f"- Bundle discovery compatibility: `{workflow_coverage['bundle_discovery_compatible']}`",
        f"- Coordinate transform compatibility: `{workflow_coverage['coordinate_transforms_compatible']}`",
        f"- Projection and sampling compatibility: `{workflow_coverage['projection_and_sampling_compatible']}`",
        f"- Temporal bundling compatibility: `{workflow_coverage['temporal_bundling_compatible']}`",
        f"- Offline inspection compatibility: `{workflow_coverage['offline_inspection_compatible']}`",
        f"- Documentation audit: `{documentation_audit['overall_status']}`",
        "",
        "## Entrypoints Exercised",
        "",
    ]

    for label, audit in entrypoint_audits.items():
        lines.extend(
            [
                f"### {label}",
                "",
                f"- Overall status: `{audit['overall_status']}`",
                f"- Source kind: `{audit.get('source_reference', {}).get('source_kind', '')}`",
                f"- Source family/name: `{audit.get('source_reference', {}).get('source_family', '')}` / `{audit.get('source_reference', {}).get('source_name', '')}`",
                f"- Bundle metadata: `{audit['retinal_bundle_metadata_path']}`",
                f"- Inspection summary: `{audit.get('inspection', {}).get('summary_path', '')}`",
                f"- QA status: `{audit.get('inspection', {}).get('qa_overall_status', '')}`",
                f"- Coverage status: `{audit.get('inspection', {}).get('coverage_overall_status', '')}`",
                f"- Record hashes stable: `{audit.get('workflow_checks', {}).get('record_hashes_stable', False)}`",
                f"- Replay resolution matches direct bundle replay: `{audit.get('workflow_checks', {}).get('resolved_replay_matches_bundle_replay', False)}`",
                f"- Transform metadata consistent: `{audit.get('workflow_checks', {}).get('transform_metadata_consistent', False)}`",
                f"- Inspection hashes stable: `{audit.get('workflow_checks', {}).get('inspection_hashes_stable', False)}`",
            ]
        )
        if audit["issues"]:
            lines.append("- Issues:")
            for issue in audit["issues"]:
                lines.append(f"  - `{issue['severity']}`: {issue['message']}")
        lines.append("")

    lines.extend(
        [
            "## Remaining Risks",
            "",
        ]
    )
    for risk in summary["remaining_risks"]:
        lines.append(f"- {risk}")

    lines.extend(
        [
            "",
            "## Deferred Follow-On Issues",
            "",
        ]
    )
    for issue in summary["follow_on_issues"]:
        lines.append(f"- `{issue['ticket_id']}`: {issue['title']}")
        lines.append(f"  Reproduction: {issue['reproduction']}")

    return "\n".join(lines).rstrip() + "\n"
