from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from .coupling_contract import (
    COUPLING_BUNDLE_CONTRACT_VERSION,
    COUPLING_BUNDLE_DESIGN_NOTE,
    COUPLING_BUNDLE_DESIGN_NOTE_VERSION,
    discover_coupling_bundle_paths,
    discover_edge_coupling_bundle_paths,
)
from .coupling_inspection import build_coupling_inspection_output_dir
from .geometry_contract import load_geometry_manifest, load_geometry_manifest_records
from .io_utils import ensure_dir, write_json
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_GO,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .registry import load_connectivity_registry, load_synapse_registry
from .synapse_mapping import (
    ANCHOR_TYPE_POINT_STATE,
    ANCHOR_TYPE_SKELETON_NODE,
    ANCHOR_TYPE_SURFACE_PATCH,
    load_root_anchor_map,
)


MILESTONE7_READINESS_REPORT_VERSION = "milestone7_readiness.v1"
DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_registry",
    "tests.test_selection",
    "tests.test_synapse_mapping",
    "tests.test_coupling_assembly",
    "tests.test_coupling_contract",
    "tests.test_coupling_inspection",
    "tests.test_milestone7_readiness",
)

_EXPECTED_ANCHOR_TYPES_BY_ROLE = {
    "surface_simulated": ANCHOR_TYPE_SURFACE_PATCH,
    "skeleton_simulated": ANCHOR_TYPE_SKELETON_NODE,
    "point_simulated": ANCHOR_TYPE_POINT_STATE,
    "context_only": ANCHOR_TYPE_POINT_STATE,
}


def build_milestone7_readiness_paths(
    coupling_inspection_dir: str | Path,
    edge_specs: Iterable[tuple[int, int]],
) -> dict[str, Path]:
    report_dir = build_coupling_inspection_output_dir(coupling_inspection_dir, edge_specs)
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_7_readiness.md",
        "json_path": report_dir / "milestone_7_readiness.json",
        "coupling_inspection_summary_path": report_dir / "summary.json",
    }


def generate_milestone7_readiness_report(
    *,
    config_path: str | Path,
    manifest_path: str | Path,
    connectivity_registry_path: str | Path,
    synapse_registry_path: str | Path,
    synapse_registry_provenance_path: str | Path,
    coupling_inspection_dir: str | Path,
    root_ids: Iterable[int],
    edge_specs: Iterable[tuple[int, int]],
    fixture_verification: Mapping[str, Any],
    registry_command: Mapping[str, Any],
    selection_command: Mapping[str, Any],
    build_command: Mapping[str, Any],
    coupling_inspection_command: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_root_ids = sorted({int(root_id) for root_id in root_ids})
    normalized_edge_specs = sorted({(int(pre_root_id), int(post_root_id)) for pre_root_id, post_root_id in edge_specs})
    readiness_paths = build_milestone7_readiness_paths(coupling_inspection_dir, normalized_edge_specs)
    report_dir = ensure_dir(readiness_paths["report_dir"])

    manifest_payload = load_geometry_manifest(manifest_path)
    manifest_records = load_geometry_manifest_records(manifest_path)
    coupling_inspection_summary = _load_json_if_exists(readiness_paths["coupling_inspection_summary_path"]) or {}
    synapse_registry = load_synapse_registry(synapse_registry_path)
    connectivity_registry = load_connectivity_registry(connectivity_registry_path)
    synapse_provenance = _load_json_if_exists(synapse_registry_provenance_path) or {}

    root_audits = [
        _audit_root(
            root_id=root_id,
            manifest_record=manifest_records.get(str(root_id)),
            synapse_registry=synapse_registry,
        )
        for root_id in normalized_root_ids
    ]
    edge_audits = [
        _audit_edge(
            edge_spec=edge_spec,
            report_dir=report_dir,
            coupling_inspection_summary=coupling_inspection_summary,
        )
        for edge_spec in normalized_edge_specs
    ]

    coupling_contract_audit = _audit_coupling_contract_header(
        manifest_payload=manifest_payload,
        synapse_registry=synapse_registry,
        synapse_provenance=synapse_provenance,
        selected_root_ids=normalized_root_ids,
        connectivity_registry=connectivity_registry,
    )
    mode_coverage = _build_mode_coverage(root_audits)

    blocking_issues = (
        [issue for audit in root_audits for issue in audit["issues"] if issue["severity"] == "blocking"]
        + [issue for audit in edge_audits for issue in audit["issues"] if issue["severity"] == "blocking"]
        + [issue for issue in coupling_contract_audit["issues"] if issue["severity"] == "blocking"]
    )
    warning_issues = (
        [issue for audit in root_audits for issue in audit["issues"] if issue["severity"] != "blocking"]
        + [issue for audit in edge_audits for issue in audit["issues"] if issue["severity"] != "blocking"]
        + [issue for issue in coupling_contract_audit["issues"] if issue["severity"] != "blocking"]
    )

    fixture_status = str(fixture_verification.get("status", "skipped"))
    registry_status = str(registry_command.get("status", "skipped"))
    selection_status = str(selection_command.get("status", "skipped"))
    build_status = str(build_command.get("status", "skipped"))
    inspection_status = str(coupling_inspection_command.get("status", "skipped"))
    local_coupling_gate = _resolve_local_coupling_gate(coupling_inspection_summary)

    scientific_risks: list[str] = []
    follow_on_issues: list[dict[str, str]] = []
    if _is_curated_verification_synapse_source(synapse_provenance):
        scientific_risks.append(
            "The cached Milestone 7 subset uses a curated local synapse snapshot over real cached geometry rather than a tracked biological synapse export."
        )
        follow_on_issues.append(
            {
                "ticket_id": "FW-M7-007",
                "title": "Replace the curated Milestone 7 verification synapse snapshot with a biologically sourced cached export for one connected local subset.",
                "reproduction": (
                    "Run `make milestone7-readiness` and inspect the readiness report: the integration pass is structurally coherent, "
                    "but the synapse provenance source points at `config/milestone_7_verification_inputs/synapses.csv` rather than a downloaded biological snapshot."
                ),
            }
        )

    edge_findings: list[str] = []
    for audit in edge_audits:
        if audit["overall_status"] == "pass":
            continue
        if audit["overall_status"] == "warn":
            edge_findings.append(
                f"Edge {audit['edge_label']} requires review because the coupling inspection summary is `warn`."
            )
        elif audit["overall_status"] == "fail":
            edge_findings.append(
                f"Edge {audit['edge_label']} failed the coupling inspection gate."
            )
        elif audit["overall_status"] == "blocked":
            edge_findings.append(
                f"Edge {audit['edge_label']} was blocked because required local artifacts were unavailable."
            )

    if (
        fixture_status != "pass"
        or registry_status != "pass"
        or selection_status != "pass"
        or build_status != "pass"
        or inspection_status != "pass"
        or local_coupling_gate == READINESS_GATE_HOLD
        or blocking_issues
    ):
        readiness_status = READINESS_GATE_HOLD
    elif local_coupling_gate == READINESS_GATE_REVIEW or warning_issues or scientific_risks or follow_on_issues:
        readiness_status = READINESS_GATE_REVIEW
    else:
        readiness_status = "ready"

    summary = {
        "report_version": MILESTONE7_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "manifest_path": str(Path(manifest_path).resolve()),
        "connectivity_registry_path": str(Path(connectivity_registry_path).resolve()),
        "synapse_registry_path": str(Path(synapse_registry_path).resolve()),
        "synapse_registry_provenance_path": str(Path(synapse_registry_provenance_path).resolve()),
        "root_ids": normalized_root_ids,
        "edge_specs": [
            {"pre_root_id": int(pre_root_id), "post_root_id": int(post_root_id)}
            for pre_root_id, post_root_id in normalized_edge_specs
        ],
        "root_count": len(normalized_root_ids),
        "edge_count": len(normalized_edge_specs),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "coupling_inspection_summary_path": str(readiness_paths["coupling_inspection_summary_path"].resolve()),
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "registry_command": copy.deepcopy(dict(registry_command)),
        "selection_command": copy.deepcopy(dict(selection_command)),
        "build_command": copy.deepcopy(dict(build_command)),
        "coupling_inspection_command": copy.deepcopy(dict(coupling_inspection_command)),
        "coupling_contract_audit": coupling_contract_audit,
        "root_contract_audit": {
            "blocking_issue_count": sum(
                1 for audit in root_audits for issue in audit["issues"] if issue["severity"] == "blocking"
            ),
            "warning_issue_count": sum(
                1 for audit in root_audits for issue in audit["issues"] if issue["severity"] != "blocking"
            ),
            "roots_with_ready_coupling_assets": sum(1 for audit in root_audits if audit["coupling_assets_ready"]),
            "roots_with_expected_anchor_modes": sum(1 for audit in root_audits if audit["expected_anchor_modes_ready"]),
            "roots": {str(audit["root_id"]): audit for audit in root_audits},
        },
        "edge_contract_audit": {
            "blocking_issue_count": sum(
                1 for audit in edge_audits for issue in audit["issues"] if issue["severity"] == "blocking"
            ),
            "warning_issue_count": sum(
                1 for audit in edge_audits for issue in audit["issues"] if issue["severity"] != "blocking"
            ),
            "inspected_edges_ready": sum(1 for audit in edge_audits if audit["inspection_ready"]),
            "edges": {audit["edge_label"]: audit for audit in edge_audits},
        },
        "mode_coverage": mode_coverage,
        "coupling_inspection_summary": coupling_inspection_summary,
        "scientific_risks": scientific_risks,
        "edge_findings": edge_findings,
        "follow_on_issues": follow_on_issues,
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            "local_coupling_gate": local_coupling_gate,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone7_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def discover_milestone7_edge_specs(manifest_path: str | Path) -> list[tuple[int, int]]:
    manifest_records = load_geometry_manifest_records(manifest_path)
    discovered: set[tuple[int, int]] = set()
    for record in manifest_records.values():
        for edge_bundle in discover_edge_coupling_bundle_paths(record):
            if str(edge_bundle["status"]) == "missing":
                continue
            discovered.add((int(edge_bundle["pre_root_id"]), int(edge_bundle["post_root_id"])))
    return sorted(discovered)


def _audit_coupling_contract_header(
    *,
    manifest_payload: Mapping[str, Any],
    synapse_registry: pd.DataFrame,
    synapse_provenance: Mapping[str, Any],
    selected_root_ids: list[int],
    connectivity_registry: pd.DataFrame,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    contract_version = str(manifest_payload.get("_coupling_contract_version", ""))
    contract_payload = dict(manifest_payload.get("_coupling_contract", {}))
    if contract_version != COUPLING_BUNDLE_CONTRACT_VERSION:
        issues.append(
            {
                "severity": "blocking",
                "message": "The manifest coupling contract version does not match `coupling_bundle.v1`.",
            }
        )
    if str(contract_payload.get("design_note", "")) != COUPLING_BUNDLE_DESIGN_NOTE:
        issues.append(
            {
                "severity": "blocking",
                "message": "The manifest coupling contract does not point at the authoritative Milestone 7 design note.",
            }
        )
    if str(contract_payload.get("design_note_version", "")) != COUPLING_BUNDLE_DESIGN_NOTE_VERSION:
        issues.append(
            {
                "severity": "blocking",
                "message": "The manifest coupling contract design-note version is missing or unexpected.",
            }
        )

    scope = dict(synapse_provenance.get("scope", {}))
    provenance_root_ids = sorted({int(root_id) for root_id in scope.get("root_ids") or []})
    if str(scope.get("mode", "")) != "root_id_subset":
        issues.append(
            {
                "severity": "blocking",
                "message": "The synapse registry provenance does not record a root_id_subset scope.",
            }
        )
    if provenance_root_ids != selected_root_ids:
        issues.append(
            {
                "severity": "blocking",
                "message": "The synapse registry provenance root-id scope does not match the selected subset.",
            }
        )

    connectivity_match = _compare_connectivity_and_synapse_scope(
        synapse_registry=synapse_registry,
        connectivity_registry=connectivity_registry,
    )
    if not connectivity_match["matches"]:
        issues.append(
            {
                "severity": "blocking",
                "message": "The aggregated connectivity registry does not match the scoped synapse registry.",
            }
        )

    return {
        "contract_version": contract_version,
        "design_note": str(contract_payload.get("design_note", "")),
        "design_note_version": str(contract_payload.get("design_note_version", "")),
        "synapse_registry_row_count": int(len(synapse_registry)),
        "synapse_scope_mode": str(scope.get("mode", "")),
        "synapse_scope_root_ids": provenance_root_ids,
        "connectivity_registry_matches_synapse_scope": bool(connectivity_match["matches"]),
        "connectivity_mismatch_count": int(connectivity_match["mismatch_count"]),
        "issues": issues,
    }


def _audit_root(
    *,
    root_id: int,
    manifest_record: Mapping[str, Any] | None,
    synapse_registry: pd.DataFrame,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    manifest_record = dict(manifest_record or {})
    project_role = str(manifest_record.get("project_role", ""))
    cell_type = str(manifest_record.get("cell_type", ""))
    build_result = dict(manifest_record.get("build_result", {}))
    expected_anchor_type = _EXPECTED_ANCHOR_TYPES_BY_ROLE.get(project_role, "")

    incoming_synapse_count = int((synapse_registry["post_root_id"] == int(root_id)).sum())
    outgoing_synapse_count = int((synapse_registry["pre_root_id"] == int(root_id)).sum())

    coupling_assets_ready = False
    coupling_bundle_status = ""
    incoming_anchor_type_counts: dict[str, int] = {}
    outgoing_anchor_type_counts: dict[str, int] = {}
    discovered_edge_bundle_count = 0
    expected_anchor_modes_ready = False
    try:
        asset_paths = discover_coupling_bundle_paths(manifest_record)
        coupling_assets_ready = all(path.exists() for path in asset_paths.values())
        if not coupling_assets_ready:
            issues.append(
                {
                    "severity": "blocking",
                    "message": "One or more root-local coupling assets are missing from disk.",
                }
            )
        incoming_table = load_root_anchor_map(asset_paths["incoming_anchor_map"]).table
        outgoing_table = load_root_anchor_map(asset_paths["outgoing_anchor_map"]).table
        incoming_anchor_type_counts = _mapped_anchor_type_counts(incoming_table)
        outgoing_anchor_type_counts = _mapped_anchor_type_counts(outgoing_table)
        if incoming_synapse_count and expected_anchor_type and incoming_anchor_type_counts.get(expected_anchor_type, 0) == 0:
            issues.append(
                {
                    "severity": "blocking",
                    "message": (
                        f"Incoming mapped synapses for root {root_id} do not realize the expected `{expected_anchor_type}` anchor type."
                    ),
                }
            )
        if outgoing_synapse_count and expected_anchor_type and outgoing_anchor_type_counts.get(expected_anchor_type, 0) == 0:
            issues.append(
                {
                    "severity": "blocking",
                    "message": (
                        f"Outgoing mapped synapses for root {root_id} do not realize the expected `{expected_anchor_type}` anchor type."
                    ),
                }
            )
        discovered_edge_bundle_count = len(discover_edge_coupling_bundle_paths(manifest_record))
        expected_anchor_modes_ready = not any(issue["severity"] == "blocking" for issue in issues)
    except Exception as exc:
        issues.append(
            {
                "severity": "blocking",
                "message": f"Coupling bundle discovery failed for root {root_id}: {type(exc).__name__}: {exc}",
            }
        )

    coupling_bundle_status = str(dict(manifest_record.get("coupling_bundle", {})).get("status", ""))
    if not coupling_bundle_status:
        issues.append(
            {
                "severity": "blocking",
                "message": f"Manifest record for root {root_id} is missing coupling_bundle metadata.",
            }
        )
    elif coupling_bundle_status not in {"ready", "partial"}:
        issues.append(
            {
                "severity": "blocking",
                "message": f"Manifest record for root {root_id} has unusable coupling_bundle status `{coupling_bundle_status}`.",
            }
        )

    if str(build_result.get("status", "")) == "failed":
        issues.append(
            {
                "severity": "blocking",
                "message": f"Wave-asset construction failed for root {root_id}.",
            }
        )

    return {
        "root_id": int(root_id),
        "cell_type": cell_type,
        "project_role": project_role,
        "expected_anchor_type": expected_anchor_type,
        "incoming_synapse_count": incoming_synapse_count,
        "outgoing_synapse_count": outgoing_synapse_count,
        "incoming_anchor_type_counts": incoming_anchor_type_counts,
        "outgoing_anchor_type_counts": outgoing_anchor_type_counts,
        "coupling_bundle_status": coupling_bundle_status,
        "coupling_assets_ready": coupling_assets_ready,
        "expected_anchor_modes_ready": expected_anchor_modes_ready,
        "edge_bundle_count": discovered_edge_bundle_count,
        "issues": issues,
    }


def _audit_edge(
    *,
    edge_spec: tuple[int, int],
    report_dir: Path,
    coupling_inspection_summary: Mapping[str, Any],
) -> dict[str, Any]:
    pre_root_id, post_root_id = edge_spec
    edge_label = _edge_label(pre_root_id, post_root_id)
    detail_path = report_dir / f"{edge_label}_details.json"
    detail_payload = _load_json_if_exists(detail_path) or {}
    summary_entry = dict(coupling_inspection_summary.get("edges_by_id", {}).get(edge_label, {}))

    issues: list[dict[str, str]] = []
    inspection_ready = bool(detail_payload and summary_entry)
    if not inspection_ready:
        issues.append(
            {
                "severity": "blocking",
                "message": f"Coupling inspection detail payload is missing for edge {edge_label}.",
            }
        )
        overall_status = "missing"
    else:
        overall_status = str(summary_entry.get("overall_status", ""))
        if overall_status == "fail" or overall_status == "blocked":
            issues.append(
                {
                    "severity": "blocking",
                    "message": f"Coupling inspection for edge {edge_label} reported `{overall_status}`.",
                }
            )
        elif overall_status == "warn":
            issues.append(
                {
                    "severity": "warning",
                    "message": f"Coupling inspection for edge {edge_label} reported `warn`.",
                }
            )

        artifacts = dict(detail_payload.get("artifacts", {}))
        for key in ["details_json_path", "source_svg_path", "target_svg_path"]:
            artifact_path = artifacts.get(key)
            if not isinstance(artifact_path, str) or not Path(artifact_path).exists():
                issues.append(
                    {
                        "severity": "blocking",
                        "message": f"Coupling inspection artifact `{key}` is missing for edge {edge_label}.",
                    }
                )
    return {
        "edge_label": edge_label,
        "pre_root_id": int(pre_root_id),
        "post_root_id": int(post_root_id),
        "overall_status": overall_status,
        "inspection_ready": inspection_ready,
        "synapse_count": int(summary_entry.get("synapse_count", 0)),
        "usable_synapse_count": int(summary_entry.get("usable_synapse_count", 0)),
        "blocked_synapse_count": int(summary_entry.get("blocked_synapse_count", 0)),
        "component_count": int(summary_entry.get("component_count", 0)),
        "issues": issues,
    }


def _build_mode_coverage(root_audits: list[dict[str, Any]]) -> dict[str, Any]:
    role_counts = Counter(str(audit["project_role"]) for audit in root_audits)
    anchor_type_counts = Counter()
    for audit in root_audits:
        anchor_type_counts.update(dict(audit["incoming_anchor_type_counts"]))
        anchor_type_counts.update(dict(audit["outgoing_anchor_type_counts"]))
    expected_anchor_types = {
        audit["expected_anchor_type"]
        for audit in root_audits
        if audit["expected_anchor_type"]
        and (audit["incoming_synapse_count"] > 0 or audit["outgoing_synapse_count"] > 0)
    }
    return {
        "project_role_counts": {key: role_counts[key] for key in sorted(role_counts)},
        "mapped_anchor_type_counts": {key: anchor_type_counts[key] for key in sorted(anchor_type_counts)},
        "expected_anchor_type_coverage_ok": all(anchor_type_counts.get(key, 0) > 0 for key in expected_anchor_types),
    }


def _compare_connectivity_and_synapse_scope(
    *,
    synapse_registry: pd.DataFrame,
    connectivity_registry: pd.DataFrame,
) -> dict[str, Any]:
    synapse_grouped = (
        synapse_registry.groupby(["pre_root_id", "post_root_id", "neuropil", "nt_type"], dropna=False)
        .size()
        .reset_index(name="syn_count")
        .sort_values(["pre_root_id", "post_root_id", "neuropil", "nt_type"], kind="mergesort")
        .reset_index(drop=True)
    )
    connectivity_grouped = (
        connectivity_registry.groupby(["pre_root_id", "post_root_id", "neuropil", "nt_type"], dropna=False)["syn_count"]
        .sum()
        .reset_index()
        .sort_values(["pre_root_id", "post_root_id", "neuropil", "nt_type"], kind="mergesort")
        .reset_index(drop=True)
    )
    joined = synapse_grouped.merge(
        connectivity_grouped,
        on=["pre_root_id", "post_root_id", "neuropil", "nt_type"],
        how="outer",
        suffixes=("_synapse", "_connectivity"),
    ).fillna({"syn_count_synapse": -1, "syn_count_connectivity": -1})
    mismatch_mask = joined["syn_count_synapse"].astype(int) != joined["syn_count_connectivity"].astype(int)
    return {
        "matches": not bool(mismatch_mask.any()),
        "mismatch_count": int(mismatch_mask.sum()),
    }


def _mapped_anchor_type_counts(table: pd.DataFrame) -> dict[str, int]:
    if table.empty:
        return {}
    mapped = table.loc[table["mapping_status"] != "blocked"].copy()
    if mapped.empty:
        return {}
    counts = Counter(str(value) for value in mapped["anchor_type"].tolist() if str(value))
    return {key: counts[key] for key in sorted(counts)}


def _resolve_local_coupling_gate(coupling_inspection_summary: Mapping[str, Any]) -> str:
    overall_status = str(coupling_inspection_summary.get("overall_status", ""))
    if overall_status == "pass":
        return READINESS_GATE_GO
    if overall_status == "warn":
        return READINESS_GATE_REVIEW
    return READINESS_GATE_HOLD


def _is_curated_verification_synapse_source(synapse_provenance: Mapping[str, Any]) -> bool:
    source = dict(synapse_provenance.get("source", {}))
    source_path = str(source.get("path", ""))
    return "config/milestone_7_verification_inputs/synapses.csv" in source_path


def _edge_label(pre_root_id: int, post_root_id: int) -> str:
    return f"{int(pre_root_id)}__to__{int(post_root_id)}"


def _load_json_if_exists(path: str | Path) -> dict[str, Any] | None:
    json_path = Path(path)
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text(encoding="utf-8"))


def _render_milestone7_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    coupling_contract_audit = dict(summary["coupling_contract_audit"])
    root_contract_audit = dict(summary["root_contract_audit"])
    edge_contract_audit = dict(summary["edge_contract_audit"])
    mode_coverage = dict(summary["mode_coverage"])
    coupling_inspection_summary = dict(summary.get("coupling_inspection_summary", {}))

    lines = [
        "# Milestone 7 Readiness Report",
        "",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Config: `{summary['config_path']}`",
        f"- Root count: `{summary['root_count']}`",
        f"- Edge count: `{summary['edge_count']}`",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Local coupling gate: `{readiness['local_coupling_gate']}`",
        f"- Ready for follow-on work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        "",
        "## Verified",
        "",
        f"- Fixture verification status: `{summary['fixture_verification'].get('status', 'skipped')}`",
        f"- Registry command status: `{summary['registry_command'].get('status', 'skipped')}`",
        f"- Selection command status: `{summary['selection_command'].get('status', 'skipped')}`",
        f"- Local build command status: `{summary['build_command'].get('status', 'skipped')}`",
        f"- Coupling inspection command status: `{summary['coupling_inspection_command'].get('status', 'skipped')}`",
        f"- Synapse registry rows: `{coupling_contract_audit['synapse_registry_row_count']}`",
        f"- Connectivity registry matches synapse scope: `{coupling_contract_audit['connectivity_registry_matches_synapse_scope']}`",
        f"- Roots with ready coupling assets: `{root_contract_audit['roots_with_ready_coupling_assets']}` / `{summary['root_count']}`",
        f"- Roots with expected anchor modes: `{root_contract_audit['roots_with_expected_anchor_modes']}` / `{summary['root_count']}`",
        f"- Inspected edges ready: `{edge_contract_audit['inspected_edges_ready']}` / `{summary['edge_count']}`",
        f"- Mode coverage: `{mode_coverage['mapped_anchor_type_counts']}`",
        f"- Coupling inspection overall status: `{coupling_inspection_summary.get('overall_status', '')}`",
        f"- Coupling inspection summary path: `{summary['coupling_inspection_summary_path']}`",
        f"- Readiness JSON path: `{summary['json_path']}`",
        f"- Readiness Markdown path: `{summary['markdown_path']}`",
        "",
        "## Risks And Deferred",
        "",
    ]

    risks = list(summary.get("scientific_risks", []))
    edge_findings = list(summary.get("edge_findings", []))
    if risks:
        lines.extend(f"- {risk}" for risk in risks)
    else:
        lines.append("- No extra scientific risks were recorded beyond the shipped coupling QA gates.")
    if edge_findings:
        lines.extend(f"- {finding}" for finding in edge_findings)

    follow_on_issues = list(summary.get("follow_on_issues", []))
    if follow_on_issues:
        lines.extend(
            [
                "",
                "## Follow-On Issues",
                "",
            ]
        )
        for issue in follow_on_issues:
            lines.append(f"- `{issue['ticket_id']}`: {issue['title']}")
            lines.append(f"  Reproduction: {issue['reproduction']}")
    return "\n".join(lines) + "\n"
