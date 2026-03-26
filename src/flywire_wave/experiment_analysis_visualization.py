from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    COMPARISON_MATRICES_ARTIFACT_ID,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
    TASK_SUMMARY_ROWS_ARTIFACT_ID,
    VISUALIZATION_CATALOG_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
)
from .io_utils import ensure_dir, write_json


EXPERIMENT_ANALYSIS_REPORT_VERSION = "experiment_analysis_report.v1"


def generate_experiment_analysis_report(
    *,
    analysis_bundle_metadata_path: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    metadata_path = Path(analysis_bundle_metadata_path).resolve()
    metadata = load_experiment_analysis_bundle_metadata(metadata_path)
    artifact_paths = discover_experiment_analysis_bundle_paths(metadata)
    resolved_output_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else Path(str(metadata["bundle_layout"]["report_directory"])).resolve()
    )
    ensure_dir(resolved_output_dir)

    ui_payload = _load_json_mapping(artifact_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID])
    task_summary = _load_json_mapping(artifact_paths[TASK_SUMMARY_ROWS_ARTIFACT_ID])
    comparison_matrices = _load_json_mapping(
        artifact_paths[COMPARISON_MATRICES_ARTIFACT_ID]
    )
    visualization_catalog = _load_json_mapping(
        artifact_paths[VISUALIZATION_CATALOG_ARTIFACT_ID]
    )

    report_path = (resolved_output_dir / "index.html").resolve()
    summary_path = (resolved_output_dir / "summary.json").resolve()
    summary = _build_report_summary(
        metadata=metadata,
        metadata_path=metadata_path,
        report_path=report_path,
        summary_path=summary_path,
        ui_payload=ui_payload,
        task_summary=task_summary,
        comparison_matrices=comparison_matrices,
        visualization_catalog=visualization_catalog,
    )
    report_path.write_text(
        _render_report_html(
            metadata=metadata,
            summary=summary,
            ui_payload=ui_payload,
            task_summary=task_summary,
            comparison_matrices=comparison_matrices,
            visualization_catalog=visualization_catalog,
        ),
        encoding="utf-8",
    )
    write_json(summary, summary_path)
    return summary


def _build_report_summary(
    *,
    metadata: Mapping[str, Any],
    metadata_path: Path,
    report_path: Path,
    summary_path: Path,
    ui_payload: Mapping[str, Any],
    task_summary: Mapping[str, Any],
    comparison_matrices: Mapping[str, Any],
    visualization_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    task_cards = list(ui_payload.get("task_summary_cards", []))
    comparison_cards = list(ui_payload.get("comparison_cards", []))
    visualization_refs = _require_mapping(
        ui_payload.get("analysis_visualizations"),
        field_name="analysis_ui_payload.analysis_visualizations",
    )
    shared_comparison = _require_mapping(
        ui_payload.get("shared_comparison"),
        field_name="analysis_ui_payload.shared_comparison",
    )
    decision_panel = _require_mapping(
        shared_comparison.get("milestone_1_decision_panel"),
        field_name="analysis_ui_payload.shared_comparison.milestone_1_decision_panel",
    )
    phase_map_references = list(visualization_catalog.get("phase_map_references", []))
    return {
        "report_version": EXPERIMENT_ANALYSIS_REPORT_VERSION,
        "bundle_id": str(metadata["bundle_id"]),
        "experiment_id": str(metadata["experiment_id"]),
        "analysis_spec_hash": str(metadata["analysis_spec_hash"]),
        "metadata_path": str(metadata_path),
        "output_dir": str(report_path.parent),
        "report_path": str(report_path),
        "report_file_url": report_path.as_uri(),
        "summary_path": str(summary_path),
        "task_summary_row_count": len(task_summary.get("rows", [])),
        "task_summary_card_count": len(task_cards),
        "comparison_card_ids": [
            str(item["output_id"]) for item in comparison_cards if isinstance(item, Mapping)
        ],
        "matrix_ids": [
            str(item["matrix_id"])
            for item in comparison_matrices.get("matrices", [])
            if isinstance(item, Mapping)
        ],
        "phase_map_reference_count": len(phase_map_references),
        "decision_panel_status": str(decision_panel.get("overall_status", "unknown")),
        "offline_report_artifact_ids": [
            OFFLINE_REPORT_INDEX_ARTIFACT_ID,
            OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
        ],
        "offline_visualization_reference": copy_json(visualization_refs.get("offline_report")),
        "viewer_open_hint": (
            "Open the generated analysis report index.html directly in your browser; "
            "no local server is required."
        ),
    }


def _render_report_html(
    *,
    metadata: Mapping[str, Any],
    summary: Mapping[str, Any],
    ui_payload: Mapping[str, Any],
    task_summary: Mapping[str, Any],
    comparison_matrices: Mapping[str, Any],
    visualization_catalog: Mapping[str, Any],
) -> str:
    shared_comparison = _require_mapping(
        ui_payload.get("shared_comparison"),
        field_name="analysis_ui_payload.shared_comparison",
    )
    wave_only_diagnostics = _require_mapping(
        ui_payload.get("wave_only_diagnostics"),
        field_name="analysis_ui_payload.wave_only_diagnostics",
    )
    analysis_visualizations = _require_mapping(
        ui_payload.get("analysis_visualizations"),
        field_name="analysis_ui_payload.analysis_visualizations",
    )
    decision_panel = _require_mapping(
        shared_comparison.get("milestone_1_decision_panel"),
        field_name="analysis_ui_payload.shared_comparison.milestone_1_decision_panel",
    )
    task_cards = [
        dict(item)
        for item in ui_payload.get("task_summary_cards", [])
        if isinstance(item, Mapping)
    ]
    comparison_cards = [
        dict(item)
        for item in ui_payload.get("comparison_cards", [])
        if isinstance(item, Mapping)
    ]
    null_test_cards = [
        dict(item)
        for item in shared_comparison.get("null_test_cards", [])
        if isinstance(item, Mapping)
    ]
    matrix_rows = [
        dict(item)
        for item in comparison_matrices.get("matrices", [])
        if isinstance(item, Mapping)
    ]
    phase_map_references = [
        dict(item)
        for item in visualization_catalog.get("phase_map_references", [])
        if isinstance(item, Mapping)
    ]
    task_rows = [
        dict(item)
        for item in task_summary.get("rows", [])
        if isinstance(item, Mapping)
    ]

    header_facts = [
        ("Bundle ID", metadata["bundle_id"]),
        ("Experiment ID", metadata["experiment_id"]),
        ("Analysis Spec Hash", metadata["analysis_spec_hash"]),
        ("Decision Panel Status", decision_panel.get("overall_status", "unknown")),
        ("Task Cards", len(task_cards)),
        ("Comparison Cards", len(comparison_cards)),
        ("Phase Maps", len(phase_map_references)),
    ]
    return "\n".join(
        [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\" />",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
            "  <title>Experiment Analysis Report</title>",
            "  <style>",
            "    :root {",
            "      color-scheme: light;",
            "      --bg: #f5f3ef;",
            "      --card: #fffdf8;",
            "      --ink: #1f2933;",
            "      --muted: #5b6770;",
            "      --border: #dbcdbf;",
            "      --accent: #004e64;",
            "      --accent-soft: #d6eef4;",
            "      --good: #0f766e;",
            "      --warn: #b45309;",
            "      --bad: #b42318;",
            "    }",
            "    * { box-sizing: border-box; }",
            "    body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #fbf7f1 0%, var(--bg) 100%); color: var(--ink); }",
            "    main { max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }",
            "    h1, h2, h3 { margin: 0; font-weight: 600; }",
            "    h1 { font-size: 2.2rem; line-height: 1.1; }",
            "    h2 { font-size: 1.2rem; margin-bottom: 12px; }",
            "    p { margin: 0; line-height: 1.5; }",
            "    .hero { display: grid; gap: 18px; padding: 24px; border: 1px solid var(--border); background: radial-gradient(circle at top left, var(--accent-soft), var(--card) 55%); border-radius: 18px; }",
            "    .lede { color: var(--muted); max-width: 72ch; }",
            "    .fact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }",
            "    .fact { padding: 12px 14px; border: 1px solid var(--border); border-radius: 14px; background: rgba(255,255,255,0.72); }",
            "    .fact-label { display: block; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 4px; }",
            "    .fact-value { display: block; font-size: 1rem; word-break: break-word; }",
            "    .section { margin-top: 22px; padding: 20px; border: 1px solid var(--border); background: var(--card); border-radius: 18px; }",
            "    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 14px; }",
            "    .card { padding: 14px; border: 1px solid var(--border); border-radius: 14px; background: #fff; }",
            "    .card h3 { font-size: 1rem; margin-bottom: 6px; }",
            "    .meta { color: var(--muted); font-size: 0.92rem; }",
            "    .status-pass { color: var(--good); }",
            "    .status-fail { color: var(--bad); }",
            "    .status-unavailable { color: var(--warn); }",
            "    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.95rem; }",
            "    th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid #eadfd3; vertical-align: top; }",
            "    th { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }",
            "    code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; font-size: 0.92em; background: #f4efe7; padding: 0.08rem 0.28rem; border-radius: 0.35rem; }",
            "    pre { margin: 12px 0 0; padding: 14px; border-radius: 14px; background: #f7f2eb; border: 1px solid var(--border); overflow-x: auto; }",
            "  </style>",
            "</head>",
            "<body>",
            "<main>",
            "  <section class=\"hero\">",
            "    <h1>Milestone 12 Experiment Analysis Bundle</h1>",
            "    <p class=\"lede\">This static report is generated entirely from the packaged Milestone 12 analysis bundle. It summarizes task-layer comparisons, null-test status, and UI-facing visualization references without reparsing raw simulator bundle directories.</p>",
            "    <div class=\"fact-grid\">",
            *[
                "      <div class=\"fact\"><span class=\"fact-label\">"
                + html.escape(str(label))
                + "</span><span class=\"fact-value\">"
                + html.escape(str(value))
                + "</span></div>"
                for label, value in header_facts
            ],
            "    </div>",
            "  </section>",
            _section(
                "Decision Panel",
                _render_decision_panel(decision_panel),
            ),
            _section(
                "Task Summary Cards",
                _render_task_cards(task_cards),
            ),
            _section(
                "Comparison Cards",
                _render_comparison_cards(comparison_cards),
            ),
            _section(
                "Null Tests",
                _render_null_test_table(null_test_cards),
            ),
            _section(
                "Task Score Rows",
                _render_task_rows(task_rows),
            ),
            _section(
                "Matrix Exports",
                _render_matrix_table(matrix_rows),
            ),
            _section(
                "Wave Diagnostics",
                _render_phase_map_table(
                    phase_map_references,
                    wave_only_diagnostics.get("diagnostic_cards", []),
                ),
            ),
            _section(
                "Visualization References",
                _render_visualization_block(analysis_visualizations),
            ),
            _section(
                "Report Summary JSON",
                "<pre>"
                + html.escape(json.dumps(dict(summary), indent=2, sort_keys=True))
                + "</pre>",
            ),
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _section(title: str, body: str) -> str:
    return (
        f"<section class=\"section\"><h2>{html.escape(title)}</h2>{body}</section>"
    )


def _render_decision_panel(decision_panel: Mapping[str, Any]) -> str:
    rows = [
        (
            item.get("item_id", ""),
            item.get("status", ""),
            _decision_value(item.get("evidence")),
        )
        for item in decision_panel.get("decision_items", [])
        if isinstance(item, Mapping)
    ]
    return _table_html(
        headers=("Item", "Status", "Evidence"),
        rows=rows,
    )


def _render_task_cards(task_cards: Sequence[Mapping[str, Any]]) -> str:
    if not task_cards:
        return "<p class=\"meta\">No task summary cards were packaged.</p>"
    cards = []
    for item in task_cards:
        status_class = _status_class(item.get("scope_label"))
        cards.append(
            "\n".join(
                [
                    "<article class=\"card\">",
                    f"  <h3>{html.escape(str(item.get('requested_metric_id', item.get('card_id', 'task_card'))))}</h3>",
                    f"  <p class=\"meta\">Group: <code>{html.escape(str(item.get('group_id', 'manifest')))}</code></p>",
                    f"  <p class=\"meta\">Value: {html.escape(str(item.get('value', 'n/a')))} {html.escape(str(item.get('units', '')))}</p>",
                    f"  <p class=\"meta {status_class}\">Scope: {html.escape(str(item.get('scope_label', 'unknown')))}</p>",
                    "</article>",
                ]
            )
        )
    return "<div class=\"cards\">" + "".join(cards) + "</div>"


def _render_comparison_cards(comparison_cards: Sequence[Mapping[str, Any]]) -> str:
    if not comparison_cards:
        return "<p class=\"meta\">No comparison cards were packaged.</p>"
    cards = []
    for item in comparison_cards:
        cards.append(
            "\n".join(
                [
                    "<article class=\"card\">",
                    f"  <h3>{html.escape(str(item.get('display_name', item.get('output_id', 'comparison_card'))))}</h3>",
                    f"  <p class=\"meta\">Output: <code>{html.escape(str(item.get('output_id', '')))}</code></p>",
                    f"  <p class=\"meta\">Kind: {html.escape(str(item.get('output_kind', '')))}</p>",
                    f"  <p class=\"meta\">Scope: {html.escape(str(item.get('scope_label', '')))}</p>",
                    f"  <p class=\"meta\">Summary: {html.escape(json.dumps(copy_json(item.get('summary')), sort_keys=True))}</p>",
                    "</article>",
                ]
            )
        )
    return "<div class=\"cards\">" + "".join(cards) + "</div>"


def _render_null_test_table(null_test_cards: Sequence[Mapping[str, Any]]) -> str:
    if not null_test_cards:
        return "<p class=\"meta\">No null-test cards were packaged.</p>"
    rows = [
        (
            item.get("null_test_id", ""),
            item.get("status", ""),
            item.get("pass_criterion", ""),
            item.get("metric_outcome_count", 0),
        )
        for item in null_test_cards
    ]
    return _table_html(
        headers=("Null Test", "Status", "Pass Criterion", "Outcome Count"),
        rows=rows,
    )


def _render_task_rows(task_rows: Sequence[Mapping[str, Any]]) -> str:
    if not task_rows:
        return "<p class=\"meta\">No task score rows were exported.</p>"
    rows = [
        (
            item.get("requested_metric_id", ""),
            item.get("group_id", ""),
            item.get("value", ""),
            item.get("units", ""),
            item.get("effect_direction", ""),
        )
        for item in task_rows
    ]
    return _table_html(
        headers=("Requested Metric", "Group", "Value", "Units", "Effect"),
        rows=rows,
    )


def _render_matrix_table(matrix_rows: Sequence[Mapping[str, Any]]) -> str:
    if not matrix_rows:
        return "<p class=\"meta\">No matrix exports were packaged.</p>"
    rows = [
        (
            item.get("matrix_id", ""),
            item.get("scope_label", ""),
            len(item.get("row_axis", {}).get("ids", [])),
            len(item.get("column_axis", {}).get("ids", [])),
            item.get("value_semantics", ""),
        )
        for item in matrix_rows
    ]
    return _table_html(
        headers=("Matrix ID", "Scope", "Rows", "Columns", "Value Semantics"),
        rows=rows,
    )


def _render_phase_map_table(
    phase_map_references: Sequence[Mapping[str, Any]],
    diagnostic_cards: Any,
) -> str:
    parts = []
    if isinstance(diagnostic_cards, Sequence) and not isinstance(
        diagnostic_cards, (str, bytes)
    ):
        parts.append(
            _table_html(
                headers=("Metric", "Arm", "Mean", "Units"),
                rows=[
                    (
                        item.get("metric_id", ""),
                        item.get("arm_id", ""),
                        item.get("mean_value", ""),
                        item.get("units", ""),
                    )
                    for item in diagnostic_cards
                    if isinstance(item, Mapping)
                ],
            )
        )
    if phase_map_references:
        parts.append(
            _table_html(
                headers=("Arm", "Seed", "Artifact", "Root IDs", "Path"),
                rows=[
                    (
                        item.get("arm_id", ""),
                        item.get("seed", ""),
                        item.get("artifact_id", ""),
                        ", ".join(str(root_id) for root_id in item.get("root_ids", [])),
                        item.get("path", ""),
                    )
                    for item in phase_map_references
                ],
            )
        )
    if not parts:
        return "<p class=\"meta\">No wave diagnostics or phase-map references were packaged.</p>"
    return "".join(parts)


def _render_visualization_block(analysis_visualizations: Mapping[str, Any]) -> str:
    offline_report = _require_mapping(
        analysis_visualizations.get("offline_report"),
        field_name="analysis_ui_payload.analysis_visualizations.offline_report",
    )
    lines = [
        "<p class=\"meta\">Packaged visualization references are exported for later UI work.</p>",
        _table_html(
            headers=("Reference", "Value"),
            rows=[
                ("Offline Report Artifact", offline_report.get("artifact_id", "")),
                ("Offline Report Path", offline_report.get("path", "")),
                ("Offline Report Summary", offline_report.get("summary_path", "")),
                (
                    "Visualization Catalog Artifact",
                    analysis_visualizations.get("visualization_catalog_artifact_id", ""),
                ),
                (
                    "Comparison Matrix Artifact",
                    analysis_visualizations.get("comparison_matrices_artifact_id", ""),
                ),
            ],
        ),
    ]
    return "".join(lines)


def _table_html(
    *,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> str:
    if not rows:
        return "<p class=\"meta\">No rows available.</p>"
    rendered_rows = []
    for row in rows:
        rendered_rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(value))}</td>"
                for value in row
            )
            + "</tr>"
        )
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(rendered_rows)
        + "</tbody></table>"
    )


def _decision_value(value: Any) -> str:
    if isinstance(value, Mapping):
        if "value" in value:
            return str(value["value"])
        if "status" in value:
            return str(value["status"])
        return json.dumps(copy_json(value), sort_keys=True)
    return "n/a" if value is None else str(value)


def _status_class(value: Any) -> str:
    text = str(value).lower()
    if text == "shared_comparison":
        return "status-pass"
    if text == "wave_only_diagnostics":
        return "status-unavailable"
    return "meta"


def _load_json_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected mapping JSON payload at {path}.")
    return dict(payload)


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


__all__ = [
    "EXPERIMENT_ANALYSIS_REPORT_VERSION",
    "generate_experiment_analysis_report",
]
