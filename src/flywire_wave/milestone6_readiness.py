from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    PATCH_GRAPH_KEY,
    QA_SIDECAR_KEY,
    RAW_MESH_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    TRANSFER_OPERATORS_KEY,
    load_geometry_manifest_records,
)
from .io_utils import ensure_dir, write_json
from .operator_qa import build_operator_qa_output_dir
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    OPERATOR_READINESS_GATE_KEY,
    READY_FOR_FOLLOW_ON_WORK_KEY,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    build_follow_on_readiness,
    resolve_operator_bundle_ready,
    resolve_operator_readiness_gate,
)


MILESTONE6_READINESS_REPORT_VERSION = "milestone6_readiness.v2"
DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_mesh_pipeline_build",
    "tests.test_multiresolution_operators",
    "tests.test_operator_assembly_modes",
    "tests.test_operator_contract",
    "tests.test_operator_qa",
)

_REQUIRED_GEOMETRY_ASSET_KEYS = (
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    PATCH_GRAPH_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    QA_SIDECAR_KEY,
)
_REQUIRED_OPERATOR_ASSET_KEYS = (
    FINE_OPERATOR_KEY,
    COARSE_OPERATOR_KEY,
    TRANSFER_OPERATORS_KEY,
    OPERATOR_METADATA_KEY,
)


def build_milestone6_readiness_paths(
    operator_qa_dir: str | Path,
    root_ids: Iterable[int],
) -> dict[str, Path]:
    report_dir = build_operator_qa_output_dir(operator_qa_dir, root_ids)
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_6_readiness.md",
        "json_path": report_dir / "milestone_6_readiness.json",
        "operator_qa_summary_path": report_dir / "summary.json",
    }


def generate_milestone6_readiness_report(
    *,
    config_path: str | Path,
    manifest_path: str | Path,
    operator_qa_dir: str | Path,
    root_ids: Iterable[int],
    fixture_verification: Mapping[str, Any],
    build_command: Mapping[str, Any],
    operator_qa_command: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_root_ids = _normalize_root_ids(root_ids)
    report_paths = build_milestone6_readiness_paths(operator_qa_dir, normalized_root_ids)
    report_dir = ensure_dir(report_paths["report_dir"])

    manifest_records = load_geometry_manifest_records(manifest_path)
    operator_qa_summary = _load_json_if_exists(report_paths["operator_qa_summary_path"]) or {}
    root_audits = [
        _audit_root(
            root_id=root_id,
            manifest_record=manifest_records.get(str(root_id)),
            detail_payload=_load_json_if_exists(report_dir / f"{root_id}_details.json"),
        )
        for root_id in normalized_root_ids
    ]

    blocking_issues = [
        issue
        for root_audit in root_audits
        for issue in root_audit["issues"]
        if issue["severity"] == "blocking"
    ]
    warning_issues = [
        issue
        for root_audit in root_audits
        for issue in root_audit["issues"]
        if issue["severity"] != "blocking"
    ]

    fixture_status = str(fixture_verification.get("status", "skipped"))
    build_status = str(build_command.get("status", "skipped"))
    operator_qa_status = str(operator_qa_command.get("status", "skipped"))
    operator_gate = resolve_operator_readiness_gate(
        operator_qa_summary,
        default=READINESS_GATE_HOLD if operator_qa_status != "pass" else READINESS_GATE_REVIEW,
    )

    cleanup_root_count = sum(
        1
        for root_audit in root_audits
        if int(root_audit["mesh_cleanup"].get("removed_face_count", 0)) > 0
    )
    cleanup_removed_face_total = sum(
        int(root_audit["mesh_cleanup"].get("removed_face_count", 0))
        for root_audit in root_audits
    )
    surface_simulated_root_count = sum(
        1
        for root_audit in root_audits
        if root_audit["project_role"] == "surface_simulated"
    )
    blocked_prerequisite_root_ids = [audit["root_id"] for audit in root_audits if audit["prerequisite_status"] != "ready"]
    missing_raw_mesh_root_ids = [
        audit["root_id"] for audit in root_audits if audit["prerequisite_status"] == "missing_raw_mesh"
    ]

    scientific_risks: list[str] = []
    follow_on_issues: list[dict[str, str]] = []
    operator_qa_findings: list[str] = []
    if cleanup_removed_face_total > 0:
        scientific_risks.append(
            "Real local meshes required degenerate-face cleanup before cotangent assembly."
        )
    for root_audit in root_audits:
        if root_audit["prerequisite_status"] == "missing_raw_mesh":
            operator_qa_findings.append(
                f"Root {root_audit['root_id']} is blocked because the raw mesh prerequisite is missing."
            )
            continue
        if root_audit["prerequisite_status"] == "missing_operator_inputs":
            operator_qa_findings.append(
                f"Root {root_audit['root_id']} is blocked because operator QA prerequisites are incomplete."
            )
            continue
        if root_audit["prerequisite_status"] == "build_failed":
            operator_qa_findings.append(
                f"Root {root_audit['root_id']} is blocked because wave-asset construction failed."
            )
            continue
        failed_checks = [check for check in root_audit["nonpass_checks"] if check["status"] == "fail"]
        warning_checks = [check for check in root_audit["nonpass_checks"] if check["status"] == "warn"]
        if failed_checks:
            check = failed_checks[0]
            operator_qa_findings.append(
                f"Root {root_audit['root_id']} failed `{check['metric_name']}` at {check['value']:.6g}."
            )
        elif warning_checks:
            joined = ", ".join(check["metric_name"] for check in warning_checks[:3])
            operator_qa_findings.append(
                f"Root {root_audit['root_id']} warned on {joined}."
            )
    if surface_simulated_root_count == 0 and normalized_root_ids:
        scientific_risks.append(
            "The tracked offline verification bundle exercises real morphology, but none of the cached roots are marked surface_simulated."
        )
        follow_on_issues.append(
            {
                "ticket_id": "FW-M6-007",
                "title": "Refresh the tracked Milestone 6 local verification bundle so it includes at least one surface_simulated root.",
                "reproduction": (
                    "Run `make milestone6-readiness` and inspect the readiness report: the cached verification bundle completes offline, "
                    f"but 0/{len(normalized_root_ids)} roots are tagged `project_role=surface_simulated` in the local registry snapshot."
                ),
            }
        )

    if (
        fixture_status != "pass"
        or build_status != "pass"
        or operator_qa_status != "pass"
        or operator_gate == READINESS_GATE_HOLD
        or blocking_issues
    ):
        readiness_status = READINESS_GATE_HOLD
    elif operator_gate == READINESS_GATE_REVIEW or warning_issues or follow_on_issues:
        readiness_status = READINESS_GATE_REVIEW
    else:
        readiness_status = "ready"

    summary = {
        "report_version": MILESTONE6_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "manifest_path": str(Path(manifest_path).resolve()),
        "root_ids": normalized_root_ids,
        "root_count": len(normalized_root_ids),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(report_paths["markdown_path"].resolve()),
        "json_path": str(report_paths["json_path"].resolve()),
        "operator_qa_summary_path": str(report_paths["operator_qa_summary_path"].resolve()),
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "build_command": copy.deepcopy(dict(build_command)),
        "operator_qa_command": copy.deepcopy(dict(operator_qa_command)),
        "operator_qa_summary": operator_qa_summary,
        "contract_audit": {
            "blocking_issue_count": len(blocking_issues),
            "warning_issue_count": len(warning_issues),
            "geometry_assets_ready_root_count": sum(1 for audit in root_audits if audit["geometry_assets_ready"]),
            "operator_assets_ready_root_count": sum(1 for audit in root_audits if audit["operator_assets_ready"]),
            "qa_details_ready_root_count": sum(1 for audit in root_audits if audit["qa_details_ready"]),
            "roots": {
                str(audit["root_id"]): {
                    "cell_type": audit["cell_type"],
                    "project_role": audit["project_role"],
                    "geometry_assets_ready": audit["geometry_assets_ready"],
                    "operator_assets_ready": audit["operator_assets_ready"],
                    "qa_details_ready": audit["qa_details_ready"],
                    OPERATOR_READINESS_GATE_KEY: audit[OPERATOR_READINESS_GATE_KEY],
                    "prerequisite_status": audit["prerequisite_status"],
                    "build_result": audit["build_result"],
                    "boundary_condition_mode": audit["boundary_condition_mode"],
                    "anisotropy_model": audit["anisotropy_model"],
                    "mesh_cleanup": audit["mesh_cleanup"],
                    "issues": audit["issues"],
                }
                for audit in root_audits
            },
        },
        "blocked_prerequisites": {
            "root_count": len(blocked_prerequisite_root_ids),
            "root_ids": blocked_prerequisite_root_ids,
            "missing_raw_mesh_root_ids": missing_raw_mesh_root_ids,
        },
        "scientific_risks": scientific_risks,
        "operator_qa_findings": operator_qa_findings,
        "follow_on_issues": follow_on_issues,
        "mesh_cleanup": {
            "roots_with_removed_faces": cleanup_root_count,
            "removed_face_total": cleanup_removed_face_total,
        },
        "surface_simulated_root_count": surface_simulated_root_count,
        FOLLOW_ON_READINESS_KEY: build_follow_on_readiness(
            status=readiness_status,
            local_operator_gate=operator_gate,
        ),
    }

    report_paths["markdown_path"].write_text(
        _render_milestone6_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, report_paths["json_path"])
    return summary


def _audit_root(
    *,
    root_id: int,
    manifest_record: Mapping[str, Any] | None,
    detail_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    manifest_record = dict(manifest_record or {})
    detail_payload = dict(detail_payload or {})

    geometry_assets = dict(manifest_record.get("assets", {}))
    operator_bundle = dict(manifest_record.get("operator_bundle", {}))
    operator_assets = dict(operator_bundle.get("assets", {}))
    transfer_bundle = dict(operator_bundle.get("transfer_operators", {}))
    detail_summary = dict(detail_payload.get("summary", {}))
    detail_operator_bundle = dict(detail_payload.get("operator_bundle", {}))
    build_result = dict(manifest_record.get("build_result", {}))
    detail_missing_prerequisites = list(detail_payload.get("missing_prerequisites", []))

    geometry_assets_ready = all(
        isinstance(geometry_assets.get(asset_key), Mapping)
        and str(geometry_assets[asset_key].get("status", "")) == "ready"
        for asset_key in _REQUIRED_GEOMETRY_ASSET_KEYS
    )
    operator_assets_ready = all(
        isinstance(operator_assets.get(asset_key), Mapping)
        and str(operator_assets[asset_key].get("status", "")) == "ready"
        for asset_key in _REQUIRED_OPERATOR_ASSET_KEYS
    )
    raw_mesh_asset = geometry_assets.get(RAW_MESH_KEY, {})
    raw_mesh_status = str(raw_mesh_asset.get("status", ""))
    missing_raw_mesh = raw_mesh_status == "missing" or str(build_result.get("reason", "")) == "missing_raw_mesh"
    if missing_raw_mesh:
        prerequisite_status = "missing_raw_mesh"
    elif detail_missing_prerequisites:
        prerequisite_status = "missing_operator_inputs"
    elif str(build_result.get("status", "")) == "failed":
        prerequisite_status = "build_failed"
    else:
        prerequisite_status = "ready"

    if missing_raw_mesh:
        issues.append(
            {
                "severity": "blocking",
                "message": (
                    "raw mesh prerequisite is missing for this root; run `scripts/02_fetch_meshes.py` "
                    "or correct the selected-root subset before rebuilding wave assets."
                ),
            }
        )
    elif detail_missing_prerequisites:
        first_missing = detail_missing_prerequisites[0]
        issues.append(
            {
                "severity": "blocking",
                "message": (
                    "operator QA prerequisites are incomplete for this root; "
                    f"missing `{first_missing.get('asset_key', '')}` at "
                    f"`{first_missing.get('path', '')}`."
                ),
            }
        )
    elif str(build_result.get("status", "")) == "failed":
        first_error = next(iter(build_result.get("errors", [])), {})
        issues.append(
            {
                "severity": "blocking",
                "message": (
                    "wave asset build failed for this root"
                    + (
                        f" with {first_error.get('error_type', 'processing_error')}: "
                        f"{first_error.get('message', '')}"
                    ).rstrip()
                ),
            }
        )
    else:
        for asset_key in _REQUIRED_GEOMETRY_ASSET_KEYS:
            asset_record = geometry_assets.get(asset_key)
            if isinstance(asset_record, Mapping) and str(asset_record.get("status", "")) == "ready":
                continue
            issues.append(
                {
                    "severity": "blocking",
                    "message": f"geometry asset {asset_key} is not ready in the manifest.",
                }
            )
        for asset_key in _REQUIRED_OPERATOR_ASSET_KEYS:
            asset_record = operator_assets.get(asset_key)
            if isinstance(asset_record, Mapping) and str(asset_record.get("status", "")) == "ready":
                continue
            issues.append(
                {
                    "severity": "blocking",
                    "message": f"operator asset {asset_key} is not ready in the manifest.",
                }
            )

    if not missing_raw_mesh and operator_assets_ready:
        if not transfer_bundle.get("fine_to_coarse_restriction", {}).get("available", False):
            issues.append(
                {
                    "severity": "blocking",
                    "message": "fine-to-coarse restriction is missing from operator_bundle.transfer_operators.",
                }
            )
        if not transfer_bundle.get("coarse_to_fine_prolongation", {}).get("available", False):
            issues.append(
                {
                    "severity": "blocking",
                    "message": "coarse-to-fine prolongation is missing from operator_bundle.transfer_operators.",
                }
            )
        if not transfer_bundle.get("normalized_state_transfer", {}).get("available", False):
            issues.append(
                {
                    "severity": "blocking",
                    "message": "normalized state transfer is missing from operator_bundle.transfer_operators.",
                }
            )

    qa_details_ready = bool(detail_payload)
    if not qa_details_ready and prerequisite_status == "ready" and operator_assets_ready:
        issues.append(
            {
                "severity": "blocking",
                "message": "operator QA detail payload is missing for this root.",
            }
        )

    boundary_condition_mode = str(operator_bundle.get("boundary_condition_mode", ""))
    anisotropy_model = str(operator_bundle.get("anisotropy_model", ""))
    if not boundary_condition_mode and prerequisite_status == "ready":
        issues.append(
            {
                "severity": "blocking",
                "message": "boundary_condition_mode is missing from operator metadata.",
            }
        )
    if not anisotropy_model and prerequisite_status == "ready":
        issues.append(
            {
                "severity": "blocking",
                "message": "anisotropy_model is missing from operator metadata.",
            }
        )

    if qa_details_ready and detail_summary.get("overall_status") != "blocked":
        if str(detail_operator_bundle.get("boundary_condition_mode", "")) != boundary_condition_mode:
            issues.append(
                {
                    "severity": "warning",
                    "message": "boundary_condition_mode differs between manifest metadata and QA detail payload.",
                }
            )
        if str(detail_operator_bundle.get("anisotropy_model", "")) != anisotropy_model:
            issues.append(
                {
                    "severity": "warning",
                    "message": "anisotropy_model differs between manifest metadata and QA detail payload.",
                }
            )

    return {
        "root_id": int(root_id),
        "cell_type": str(manifest_record.get("cell_type", "")),
        "project_role": str(manifest_record.get("project_role", "")),
        "geometry_assets_ready": geometry_assets_ready,
        "operator_assets_ready": operator_assets_ready,
        "qa_details_ready": qa_details_ready,
        OPERATOR_READINESS_GATE_KEY: resolve_operator_readiness_gate(detail_summary),
        "prerequisite_status": prerequisite_status,
        "build_result": build_result,
        "boundary_condition_mode": boundary_condition_mode,
        "anisotropy_model": anisotropy_model,
        "mesh_cleanup": dict(manifest_record.get("bundle_metadata", {}).get("mesh_cleanup", {})),
        "nonpass_checks": [
            {
                "metric_name": metric_name,
                "status": str(check.get("status", "")),
                "value": float(check.get("value", 0.0)),
            }
            for metric_name, check in sorted(dict(detail_payload.get("checks", {})).items())
            if isinstance(check, Mapping) and str(check.get("status", "pass")) != "pass"
        ],
        "issues": issues,
    }


def _render_milestone6_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    fixture = dict(summary["fixture_verification"])
    build_command = dict(summary["build_command"])
    operator_qa_command = dict(summary["operator_qa_command"])
    contract_audit = dict(summary["contract_audit"])
    operator_qa_summary = dict(summary.get("operator_qa_summary", {}))
    lines = [
        "# Milestone 6 Readiness Report",
        "",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Config: `{summary['config_path']}`",
        f"- Root count: `{summary['root_count']}`",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Local operator QA gate: `{readiness['local_operator_gate']}`",
        f"- Ready for follow-on work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        "",
        "## Verified",
        "",
        f"- Fixture verification status: `{fixture.get('status', 'skipped')}`",
        f"- Local build command status: `{build_command.get('status', 'skipped')}`",
        f"- Local operator QA command status: `{operator_qa_command.get('status', 'skipped')}`",
        f"- Geometry assets ready in manifest: `{contract_audit['geometry_assets_ready_root_count']}` / `{summary['root_count']}` roots",
        f"- Operator assets ready in manifest: `{contract_audit['operator_assets_ready_root_count']}` / `{summary['root_count']}` roots",
        f"- QA detail payloads present: `{contract_audit['qa_details_ready_root_count']}` / `{summary['root_count']}` roots",
        f"- Blocked prerequisite roots: `{summary['blocked_prerequisites']['root_count']}`",
        f"- Operator QA summary path: `{summary['operator_qa_summary_path']}`",
        f"- Readiness JSON path: `{summary['json_path']}`",
        f"- Readiness Markdown path: `{summary['markdown_path']}`",
    ]
    if operator_qa_summary:
        lines.extend(
            [
                f"- Operator QA overall status: `{operator_qa_summary.get('overall_status', '')}`",
                f"- Operator readiness gate: `{resolve_operator_readiness_gate(operator_qa_summary)}`",
                f"- Operator bundle ready: `{resolve_operator_bundle_ready(operator_qa_summary)}`",
                f"- Operator QA warning count: `{operator_qa_summary.get('warning_count', '')}`",
                f"- Operator QA failure count: `{operator_qa_summary.get('failure_count', '')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Risks And Deferred",
            "",
        ]
    )
    risks = list(summary.get("scientific_risks", []))
    operator_qa_findings = list(summary.get("operator_qa_findings", []))
    if risks:
        lines.extend(f"- {risk}" for risk in risks)
    else:
        lines.append("- No extra scientific risks were recorded beyond the shipped QA gates.")
    if operator_qa_findings:
        lines.extend(f"- {finding}" for finding in operator_qa_findings)

    follow_on_issues = list(summary.get("follow_on_issues", []))
    if follow_on_issues:
        lines.append("")
        lines.append("## Follow-On Issues")
        lines.append("")
        for issue in follow_on_issues:
            lines.append(f"- `{issue['ticket_id']}`: {issue['title']}")
            lines.append(f"- Reproduction: {issue['reproduction']}")

    if int(summary["mesh_cleanup"]["removed_face_total"]) > 0:
        lines.extend(
            [
                "",
                "## Mesh Cleanup",
                "",
                (
                    f"- Removed degenerate or duplicate faces: `{summary['mesh_cleanup']['removed_face_total']}` "
                    f"across `{summary['mesh_cleanup']['roots_with_removed_faces']}` root bundles"
                ),
            ]
        )

    return "\n".join(lines) + "\n"


def _load_json_if_exists(path: str | Path) -> dict[str, Any] | None:
    resolved = Path(path)
    if not resolved.exists():
        return None
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a mapping at {resolved}, got {type(payload)!r}.")
    return payload


def _normalize_root_ids(root_ids: Iterable[int]) -> list[int]:
    return [int(root_id) for root_id in root_ids]
