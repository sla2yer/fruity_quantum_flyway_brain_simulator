from __future__ import annotations

import csv
import hashlib
import html
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .io_utils import ensure_dir, write_json
from .simulator_result_contract import (
    discover_simulator_extension_artifacts,
    discover_simulator_result_bundle_paths,
    load_simulator_result_bundle_metadata,
)

SIMULATOR_VISUALIZATION_REPORT_VERSION = "simulator_visualization_report.v1"

_PALETTE = (
    "#1d4ed8",
    "#d97706",
    "#0f766e",
    "#b91c1c",
    "#7c3aed",
    "#0891b2",
)


@dataclass(frozen=True)
class WaveVisualizationPayload:
    summary: dict[str, Any]
    patch_traces: dict[str, np.ndarray]
    coupling_payload: dict[str, Any]


@dataclass(frozen=True)
class BundleVisualizationArchive:
    metadata_path: Path
    metadata: dict[str, Any]
    bundle_paths: dict[str, Path]
    extension_artifacts: dict[str, dict[str, Any]]
    ui_payload: dict[str, Any] | None
    trace_time_ms: np.ndarray
    trace_readout_ids: tuple[str, ...]
    trace_values: np.ndarray
    metrics_rows: tuple[dict[str, Any], ...]
    state_summary_rows: tuple[dict[str, Any], ...]
    wave_payload: WaveVisualizationPayload | None

    @property
    def arm_id(self) -> str:
        return str(self.metadata["arm_reference"]["arm_id"])

    @property
    def model_mode(self) -> str:
        return str(self.metadata["arm_reference"]["model_mode"])

    @property
    def baseline_family(self) -> str | None:
        value = self.metadata["arm_reference"]["baseline_family"]
        return None if value is None else str(value)

    @property
    def bundle_id(self) -> str:
        return str(self.metadata["bundle_id"])

    @property
    def bundle_directory(self) -> Path:
        return Path(str(self.metadata["bundle_layout"]["bundle_directory"])).resolve()

    @property
    def experiment_id(self) -> str:
        return str(self.metadata["manifest_reference"]["experiment_id"])


def generate_simulator_visualization_report(
    *,
    bundle_metadata_paths: Sequence[str | Path],
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    if not bundle_metadata_paths:
        raise ValueError("At least one simulator_result_bundle.json path is required.")

    archives = _load_archives(bundle_metadata_paths)
    resolved_output_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else build_simulator_visualization_output_dir(archives)
    )
    ensure_dir(resolved_output_dir)

    report_path = (resolved_output_dir / "index.html").resolve()
    summary_path = (resolved_output_dir / "summary.json").resolve()
    summary = _build_summary(archives=archives, output_dir=resolved_output_dir, report_path=report_path, summary_path=summary_path)
    report_path.write_text(_render_report_html(archives=archives, summary=summary), encoding="utf-8")
    write_json(summary, summary_path)
    return summary


def build_simulator_visualization_output_dir(
    archives: Sequence[BundleVisualizationArchive],
) -> Path:
    if not archives:
        raise ValueError("At least one archive is required to resolve an output directory.")
    processed_dir = _resolve_processed_simulator_results_dir(archives[0].bundle_directory)
    experiment_slug = _slugify(archives[0].experiment_id)
    arm_slug = "--".join(_slugify(archive.arm_id) for archive in archives)
    digest = hashlib.sha256(
        "\n".join(sorted(archive.bundle_id for archive in archives)).encode("utf-8")
    ).hexdigest()[:12]
    return (
        processed_dir
        / "visualizations"
        / f"experiment-{experiment_slug}__arms-{arm_slug}__view-{digest}"
    ).resolve()


def _load_archives(
    bundle_metadata_paths: Sequence[str | Path],
) -> list[BundleVisualizationArchive]:
    archives = [_load_archive(path) for path in bundle_metadata_paths]
    archives.sort(key=_archive_sort_key)
    return archives


def _load_archive(path: str | Path) -> BundleVisualizationArchive:
    metadata_path = Path(path).resolve()
    metadata = load_simulator_result_bundle_metadata(metadata_path)
    bundle_paths = discover_simulator_result_bundle_paths(metadata)
    extension_artifacts = {
        item["artifact_id"]: {
            "artifact_id": str(item["artifact_id"]),
            "path": Path(str(item["path"])).resolve(),
            "format": str(item["format"]),
            "artifact_scope": str(item["artifact_scope"]),
        }
        for item in discover_simulator_extension_artifacts(metadata)
    }
    ui_payload = _load_json_if_exists(extension_artifacts.get("ui_comparison_payload", {}).get("path"))
    trace_time_ms, trace_readout_ids, trace_values = _load_trace_archive(bundle_paths["readout_traces"])
    metrics_rows = tuple(_load_metrics_rows(bundle_paths["metrics_table"]))
    state_summary_rows = tuple(_load_state_summary_rows(bundle_paths["state_summary"]))
    wave_payload = _load_wave_payload(extension_artifacts)
    return BundleVisualizationArchive(
        metadata_path=metadata_path,
        metadata=metadata,
        bundle_paths=bundle_paths,
        extension_artifacts=extension_artifacts,
        ui_payload=ui_payload,
        trace_time_ms=trace_time_ms,
        trace_readout_ids=trace_readout_ids,
        trace_values=trace_values,
        metrics_rows=metrics_rows,
        state_summary_rows=state_summary_rows,
        wave_payload=wave_payload,
    )


def _archive_sort_key(archive: BundleVisualizationArchive) -> tuple[Any, ...]:
    model_rank = 0 if archive.model_mode == "baseline" else 1 if archive.model_mode == "surface_wave" else 2
    baseline_rank = archive.baseline_family or ""
    return (
        archive.experiment_id,
        model_rank,
        baseline_rank,
        archive.arm_id,
        archive.bundle_id,
    )


def _load_trace_archive(path: Path) -> tuple[np.ndarray, tuple[str, ...], np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        time_ms = np.asarray(payload["time_ms"], dtype=np.float64)
        readout_ids = tuple(str(item) for item in payload["readout_ids"].tolist())
        values = np.asarray(payload["values"], dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(f"readout_traces.values must be a rank-2 array, got shape {values.shape}.")
    return time_ms, readout_ids, values


def _load_metrics_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            normalized = dict(row)
            normalized["value"] = float(row["value"])
            rows.append(normalized)
    return rows


def _load_state_summary_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("state_summary.json must contain a list of summary rows.")
    return [dict(row) for row in payload]


def _load_wave_payload(
    extension_artifacts: Mapping[str, Mapping[str, Any]],
) -> WaveVisualizationPayload | None:
    summary_artifact = extension_artifacts.get("surface_wave_summary")
    patch_artifact = extension_artifacts.get("surface_wave_patch_traces")
    coupling_artifact = extension_artifacts.get("surface_wave_coupling_events")
    if summary_artifact is None or patch_artifact is None or coupling_artifact is None:
        return None
    summary = _load_json_if_exists(Path(str(summary_artifact["path"])))
    coupling_payload = _load_json_if_exists(Path(str(coupling_artifact["path"])))
    if summary is None or coupling_payload is None:
        return None
    with np.load(Path(str(patch_artifact["path"])).resolve(), allow_pickle=False) as payload:
        patch_traces = {
            key: np.asarray(payload[key])
            for key in payload.files
        }
    return WaveVisualizationPayload(
        summary=summary,
        patch_traces=patch_traces,
        coupling_payload=coupling_payload,
    )


def _load_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else None


def _build_summary(
    *,
    archives: Sequence[BundleVisualizationArchive],
    output_dir: Path,
    report_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    shared_readout_ids = sorted({readout_id for archive in archives for readout_id in archive.trace_readout_ids})
    comparison_metrics = _build_metric_comparison_rows(archives)
    wave_archives = [archive for archive in archives if archive.wave_payload is not None]
    return {
        "report_version": SIMULATOR_VISUALIZATION_REPORT_VERSION,
        "output_dir": str(output_dir),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "experiment_id": archives[0].experiment_id,
        "bundle_count": len(archives),
        "bundle_ids": [archive.bundle_id for archive in archives],
        "shared_readout_ids": shared_readout_ids,
        "wave_bundle_count": len(wave_archives),
        "compared_bundles": [
            {
                "arm_id": archive.arm_id,
                "model_mode": archive.model_mode,
                "baseline_family": archive.baseline_family,
                "bundle_id": archive.bundle_id,
                "metadata_path": str(archive.metadata_path),
                "bundle_directory": str(archive.bundle_directory),
                "trace_sample_count": int(archive.trace_values.shape[0]),
                "readout_ids": list(archive.trace_readout_ids),
                "wave_artifacts_present": archive.wave_payload is not None,
            }
            for archive in archives
        ],
        "metric_comparison_rows": comparison_metrics,
        "wave_bundle_summaries": [
            _build_wave_summary_row(archive)
            for archive in wave_archives
        ],
    }


def _build_wave_summary_row(archive: BundleVisualizationArchive) -> dict[str, Any]:
    assert archive.wave_payload is not None
    payload = archive.wave_payload
    coupling = dict(payload.summary.get("coupling", {}))
    final_state = dict(payload.summary.get("final_state_overview", {}))
    return {
        "arm_id": archive.arm_id,
        "bundle_id": archive.bundle_id,
        "coupling_event_count": int(coupling.get("coupling_event_count", 0)),
        "component_count": int(coupling.get("component_count", 0)),
        "topology_condition": str(coupling.get("topology_condition", "")),
        "shared_output_mean": float(final_state.get("shared_output_mean", 0.0)),
        "root_count": len(payload.patch_traces.get("root_ids", [])),
    }


def _build_metric_comparison_rows(
    archives: Sequence[BundleVisualizationArchive],
) -> list[dict[str, Any]]:
    keyed_rows: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for archive in archives:
        for row in archive.metrics_rows:
            key = (
                str(row["metric_id"]),
                str(row["readout_id"]),
                str(row["scope"]),
                str(row["window_id"]),
                str(row["units"]),
            )
            entry = keyed_rows.setdefault(
                key,
                {
                    "metric_id": key[0],
                    "readout_id": key[1],
                    "scope": key[2],
                    "window_id": key[3],
                    "units": key[4],
                    "values_by_arm": {},
                },
            )
            entry["values_by_arm"][archive.arm_id] = float(row["value"])
    rows = list(keyed_rows.values())
    rows.sort(key=lambda item: (item["readout_id"], item["metric_id"], item["window_id"], item["scope"]))
    return rows


def _render_report_html(
    *,
    archives: Sequence[BundleVisualizationArchive],
    summary: Mapping[str, Any],
) -> str:
    experiment_id = html.escape(str(summary["experiment_id"]))
    arm_list = ", ".join(html.escape(archive.arm_id) for archive in archives)
    top_cards = _render_summary_cards(archives, summary)
    readout_sections = _render_readout_sections(archives)
    bundle_sections = "".join(_render_bundle_section(archive) for archive in archives)
    wave_sections = "".join(
        _render_wave_section(archive)
        for archive in archives
        if archive.wave_payload is not None
    )
    metric_table = _render_metric_comparison_table(summary["metric_comparison_rows"], archives)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simulator Result Viewer</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffaf2;
      --ink: #1c1917;
      --muted: #6b6259;
      --line: #d7c6ae;
      --accent: #0f766e;
      --accent-2: #b45309;
      --accent-3: #1d4ed8;
      --shadow: rgba(28, 25, 23, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(29, 78, 216, 0.08), transparent 32rem),
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 28rem),
        linear-gradient(180deg, #f9f5ee 0%, var(--bg) 100%);
    }}
    main {{
      width: min(1200px, calc(100vw - 2rem));
      margin: 0 auto;
      padding: 2rem 0 4rem;
    }}
    .hero {{
      padding: 1.5rem 1.75rem;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 250, 242, 0.8);
      backdrop-filter: blur(10px);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .hero h1 {{
      margin: 0;
      font-size: clamp(1.8rem, 4vw, 3rem);
      line-height: 1.05;
    }}
    .hero p {{
      margin: 0.35rem 0 0;
      color: var(--muted);
      max-width: 60rem;
    }}
    section {{
      margin-top: 1.5rem;
      padding: 1.25rem;
      background: var(--panel);
      border: 1px solid rgba(215, 198, 174, 0.9);
      border-radius: 1rem;
      box-shadow: 0 18px 36px var(--shadow);
    }}
    h2, h3 {{
      margin-top: 0;
      margin-bottom: 0.85rem;
    }}
    .grid {{
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .card {{
      padding: 1rem;
      border-radius: 0.9rem;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(252, 246, 237, 0.95));
    }}
    .card .eyebrow {{
      display: inline-block;
      font-size: 0.75rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 0.3rem;
    }}
    .card strong {{
      display: block;
      font-size: 1.1rem;
    }}
    .muted {{
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      text-align: left;
      vertical-align: top;
      padding: 0.55rem 0.6rem;
      border-top: 1px solid var(--line);
    }}
    thead th {{
      border-top: 0;
      color: var(--muted);
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    code {{
      font-family: "SFMono-Regular", "Menlo", "Monaco", monospace;
      font-size: 0.9em;
      background: rgba(28, 25, 23, 0.06);
      padding: 0.1rem 0.25rem;
      border-radius: 0.25rem;
    }}
    .chart-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 0.85rem;
      background: linear-gradient(180deg, #fffdf8 0%, #f7efe3 100%);
      padding: 0.75rem;
    }}
    .chart-caption {{
      margin-top: 0.55rem;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .bundle-title {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 0.75rem;
      align-items: baseline;
    }}
    .pill {{
      display: inline-block;
      padding: 0.22rem 0.55rem;
      border-radius: 999px;
      font-size: 0.82rem;
      border: 1px solid var(--line);
      background: rgba(15, 118, 110, 0.08);
      color: var(--ink);
    }}
    details {{
      margin-top: 1rem;
      border-top: 1px dashed var(--line);
      padding-top: 1rem;
    }}
    summary {{
      cursor: pointer;
      color: var(--accent-3);
      font-weight: 600;
    }}
    @media (max-width: 720px) {{
      main {{ width: min(100vw - 1rem, 1200px); }}
      .hero {{ padding: 1.2rem; }}
      section {{ padding: 1rem; }}
    }}
  </style>
</head>
<body>
  <div class="hero">
    <main>
      <h1>Simulator Result Viewer</h1>
      <p>Experiment <code>{experiment_id}</code> comparing {arm_list}. This report is built directly from the produced simulator bundles, so the plots and tables reflect the exact artifacts written by the current local runs.</p>
    </main>
  </div>
  <main>
    <section>
      <h2>At A Glance</h2>
      {top_cards}
    </section>
    <section>
      <h2>Metric Comparison</h2>
      {metric_table}
    </section>
    {readout_sections}
    {bundle_sections}
    {wave_sections}
  </main>
</body>
</html>
"""


def _render_summary_cards(
    archives: Sequence[BundleVisualizationArchive],
    summary: Mapping[str, Any],
) -> str:
    shared_readouts = ", ".join(str(item) for item in summary["shared_readout_ids"]) or "none"
    cards = [
        _render_card("Report version", str(summary["report_version"]), "Deterministic offline viewer"),
        _render_card("Compared arms", str(summary["bundle_count"]), ", ".join(archive.arm_id for archive in archives)),
        _render_card("Shared readouts", shared_readouts, "Loaded from each run's trace archive"),
        _render_card("Wave bundles", str(summary["wave_bundle_count"]), "Wave-specific patch and coupling sections included when present"),
    ]
    return f'<div class="grid">{"".join(cards)}</div>'


def _render_card(label: str, value: str, detail: str) -> str:
    detail_html = f'<div class="muted">{html.escape(detail)}</div>' if detail else ""
    return (
        '<div class="card">'
        f'<div class="eyebrow">{html.escape(label)}</div>'
        f'<strong>{html.escape(value)}</strong>'
        f"{detail_html}"
        "</div>"
    )


def _render_metric_comparison_table(
    rows: Sequence[Mapping[str, Any]],
    archives: Sequence[BundleVisualizationArchive],
) -> str:
    header_cells = "".join(f"<th>{html.escape(archive.arm_id)}</th>" for archive in archives)
    body_rows: list[str] = []
    for row in rows:
        value_cells = []
        values_by_arm = dict(row["values_by_arm"])
        for archive in archives:
            value = values_by_arm.get(archive.arm_id)
            value_cells.append(f"<td>{html.escape(_format_float(value)) if value is not None else '—'}</td>")
        body_rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(row['metric_id']))}</code></td>"
            f"<td><code>{html.escape(str(row['readout_id']))}</code></td>"
            f"<td>{html.escape(str(row['window_id']))}</td>"
            f"<td>{html.escape(str(row['units']))}</td>"
            + "".join(value_cells)
            + "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Metric</th><th>Readout</th><th>Window</th><th>Units</th>"
        f"{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _render_readout_sections(archives: Sequence[BundleVisualizationArchive]) -> str:
    readout_ids = sorted({readout_id for archive in archives for readout_id in archive.trace_readout_ids})
    sections: list[str] = []
    for readout_id in readout_ids:
        trace_series = []
        for color_index, archive in enumerate(archives):
            if readout_id not in archive.trace_readout_ids:
                continue
            trace_index = archive.trace_readout_ids.index(readout_id)
            trace_series.append(
                {
                    "label": archive.arm_id,
                    "color": _PALETTE[color_index % len(_PALETTE)],
                    "time_ms": archive.trace_time_ms,
                    "values": archive.trace_values[:, trace_index],
                }
            )
        normalized_chart = _build_line_chart_svg(
            title=f"{readout_id} normalized overlay",
            traces=trace_series,
            transform="normalized",
        )
        log_chart = _build_line_chart_svg(
            title=f"{readout_id} signed log10 overlay",
            traces=trace_series,
            transform="signed_log10",
        )
        sections.append(
            "<section>"
            f"<h2>Readout: <code>{html.escape(readout_id)}</code></h2>"
            '<div class="grid">'
            '<div><div class="chart-wrap">'
            f"{normalized_chart}"
            '</div><div class="chart-caption">Each trace is scaled by its own peak absolute value so we can compare shape even when bundle magnitudes diverge heavily.</div></div>'
            '<div><div class="chart-wrap">'
            f"{log_chart}"
            '</div><div class="chart-caption">Signed <code>log10(1 + |value|)</code> view for inspecting large dynamic-range gaps without flattening the smaller run.</div></div>'
            "</div>"
            "</section>"
        )
    return "".join(sections)


def _render_bundle_section(archive: BundleVisualizationArchive) -> str:
    metadata_rows = [
        ("arm", archive.arm_id),
        ("model mode", archive.model_mode),
        ("baseline family", archive.baseline_family or "none"),
        ("bundle id", archive.bundle_id),
        ("metadata path", str(archive.metadata_path)),
    ]
    if archive.ui_payload is not None:
        context = dict(archive.ui_payload.get("comparison_context", {}))
        metadata_rows.extend(
            [
                ("topology condition", str(context.get("topology_condition", ""))),
                ("morphology condition", str(context.get("morphology_condition", ""))),
                ("primary metric", str(context.get("primary_metric", ""))),
            ]
        )
    trace_cards = "".join(
        _render_card(
            f"{readout_id} samples",
            str(archive.trace_values.shape[0]),
            f"Range {_format_float(float(np.min(archive.trace_values[:, idx])))} to {_format_float(float(np.max(archive.trace_values[:, idx])))}",
        )
        for idx, readout_id in enumerate(archive.trace_readout_ids)
    )
    trace_charts = "".join(
        '<div class="chart-wrap">'
        + _build_line_chart_svg(
            title=f"{archive.arm_id}: {readout_id}",
            traces=[
                {
                    "label": archive.arm_id,
                    "color": _PALETTE[idx % len(_PALETTE)],
                    "time_ms": archive.trace_time_ms,
                    "values": archive.trace_values[:, idx],
                }
            ],
            transform="identity",
        )
        + "</div>"
        for idx, readout_id in enumerate(archive.trace_readout_ids)
    )
    metrics_table = _render_bundle_metrics_table(archive.metrics_rows)
    state_table = _render_state_summary_table(archive.state_summary_rows)
    return (
        "<section>"
        '<div class="bundle-title">'
        f"<h2>{html.escape(archive.arm_id)}</h2>"
        f'<div><span class="pill">{html.escape(archive.model_mode)}</span></div>'
        "</div>"
        f'<div class="grid">{"".join(_render_card(label, value, "") for label, value in metadata_rows[:4])}{trace_cards}</div>'
        f"<div style=\"margin-top: 1rem;\">{trace_charts}</div>"
        "<details open><summary>Metrics</summary>"
        f"{metrics_table}</details>"
        "<details><summary>State summary</summary>"
        f"{state_table}</details>"
        "</section>"
    )


def _render_bundle_metrics_table(rows: Sequence[Mapping[str, Any]]) -> str:
    body_rows = [
        "<tr>"
        f"<td><code>{html.escape(str(row['metric_id']))}</code></td>"
        f"<td><code>{html.escape(str(row['readout_id']))}</code></td>"
        f"<td>{html.escape(str(row['statistic']))}</td>"
        f"<td>{html.escape(_format_float(float(row['value'])))}</td>"
        f"<td>{html.escape(str(row['units']))}</td>"
        "</tr>"
        for row in rows
    ]
    return (
        "<table><thead><tr>"
        "<th>Metric</th><th>Readout</th><th>Statistic</th><th>Value</th><th>Units</th>"
        f"</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _render_state_summary_table(rows: Sequence[Mapping[str, Any]]) -> str:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("scope", "")),
            str(row.get("state_id", "")),
            str(row.get("summary_stat", "")),
        ),
    )
    body_rows = [
        "<tr>"
        f"<td>{html.escape(str(row.get('scope', '')))}</td>"
        f"<td><code>{html.escape(str(row.get('state_id', '')))}</code></td>"
        f"<td>{html.escape(str(row.get('summary_stat', '')))}</td>"
        f"<td>{html.escape(_format_float(float(row.get('value', 0.0))))}</td>"
        f"<td>{html.escape(str(row.get('units', '')))}</td>"
        "</tr>"
        for row in ordered
    ]
    return (
        "<table><thead><tr>"
        "<th>Scope</th><th>State</th><th>Summary</th><th>Value</th><th>Units</th>"
        f"</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _render_wave_section(archive: BundleVisualizationArchive) -> str:
    assert archive.wave_payload is not None
    payload = archive.wave_payload
    summary = payload.summary
    final_state = dict(summary.get("final_state_overview", {}))
    coupling = dict(summary.get("coupling", {}))
    cards = [
        _render_card("shared output mean", _format_float(final_state.get("shared_output_mean")), "Final-state overview"),
        _render_card("coupling events", str(int(coupling.get("coupling_event_count", 0))), "Applied event records captured by the run"),
        _render_card("coupling components", str(int(coupling.get("component_count", 0))), "Distinct connectivity components in the wave bundle"),
        _render_card("topology", str(coupling.get("topology_condition", "")), "Wave run comparison context"),
    ]
    patch_charts = _render_patch_trace_charts(payload.patch_traces)
    coupling_table = _render_coupling_table(payload.coupling_payload)
    return (
        "<section>"
        f"<h2>Wave Detail: {html.escape(archive.arm_id)}</h2>"
        f'<div class="grid">{"".join(cards)}</div>'
        '<div style="margin-top: 1rem;">'
        f"{patch_charts}"
        "</div>"
        "<details open><summary>Coupling summary</summary>"
        f"{coupling_table}</details>"
        "</section>"
    )


def _render_patch_trace_charts(patch_traces: Mapping[str, np.ndarray]) -> str:
    root_ids = [int(item) for item in np.asarray(patch_traces.get("root_ids", []), dtype=np.int64).tolist()]
    substep_time = np.asarray(patch_traces.get("substep_time_ms", []), dtype=np.float64)
    charts: list[str] = []
    for root_id in root_ids:
        key = f"root_{root_id}_patch_activation"
        matrix = np.asarray(patch_traces.get(key), dtype=np.float64)
        if matrix.size == 0 or matrix.ndim != 2:
            continue
        traces = [
            {
                "label": f"patch {patch_index}",
                "color": _PALETTE[patch_index % len(_PALETTE)],
                "time_ms": substep_time,
                "values": matrix[:, patch_index],
            }
            for patch_index in range(matrix.shape[1])
        ]
        charts.append(
            '<div class="chart-wrap" style="margin-top: 1rem;">'
            + _build_line_chart_svg(
                title=f"Root {root_id} patch activation (normalized)",
                traces=traces,
                transform="normalized",
            )
            + '</div><div class="chart-caption">Patch traces are normalized per root so local patch structure remains visible even when the absolute wave magnitude is very large.</div>'
        )
    return "".join(charts) or '<div class="muted">No patch trace arrays were available for this wave bundle.</div>'


def _render_coupling_table(coupling_payload: Mapping[str, Any]) -> str:
    events = coupling_payload.get("events", [])
    if not isinstance(events, list) or not events:
        return '<div class="muted">No coupling events were recorded for this bundle.</div>'
    grouped: dict[tuple[int, int, str], dict[str, Any]] = defaultdict(
        lambda: {
            "event_count": 0,
            "component_ids": set(),
            "max_abs_source_value": 0.0,
            "max_abs_target_drive": 0.0,
            "mean_signed_weight_total_sum": 0.0,
        }
    )
    for event in events:
        if not isinstance(event, Mapping):
            continue
        key = (
            int(event.get("pre_root_id", 0)),
            int(event.get("post_root_id", 0)),
            str(event.get("sign_label", "")),
        )
        group = grouped[key]
        group["event_count"] += 1
        group["component_ids"].add(str(event.get("component_id", "")))
        group["mean_signed_weight_total_sum"] += float(event.get("signed_weight_total", 0.0))
        group["max_abs_source_value"] = max(
            float(group["max_abs_source_value"]),
            abs(float(event.get("source_value", 0.0))),
        )
        target_patch_drive = event.get("target_patch_drive", [])
        if isinstance(target_patch_drive, list) and target_patch_drive:
            group["max_abs_target_drive"] = max(
                float(group["max_abs_target_drive"]),
                max(abs(float(item)) for item in target_patch_drive),
            )
    rows = []
    for (pre_root_id, post_root_id, sign_label), payload in sorted(grouped.items()):
        event_count = int(payload["event_count"])
        mean_weight = float(payload["mean_signed_weight_total_sum"]) / max(event_count, 1)
        rows.append(
            "<tr>"
            f"<td>{pre_root_id} → {post_root_id}</td>"
            f"<td>{html.escape(sign_label)}</td>"
            f"<td>{event_count}</td>"
            f"<td>{len(payload['component_ids'])}</td>"
            f"<td>{html.escape(_format_float(mean_weight))}</td>"
            f"<td>{html.escape(_format_float(float(payload['max_abs_source_value'])))}</td>"
            f"<td>{html.escape(_format_float(float(payload['max_abs_target_drive'])))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Edge</th><th>Sign</th><th>Events</th><th>Components</th><th>Mean signed weight</th><th>Max |source|</th><th>Max |target drive|</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _build_line_chart_svg(
    *,
    title: str,
    traces: Sequence[Mapping[str, Any]],
    transform: str,
    width: int = 820,
    height: int = 260,
) -> str:
    if not traces:
        return "<svg viewBox='0 0 820 260'><text x='24' y='36'>No trace data available.</text></svg>"
    left = 56
    right = 18
    top = 30
    bottom = 32
    plot_width = width - left - right
    plot_height = height - top - bottom
    prepared: list[dict[str, Any]] = []
    x_min = math.inf
    x_max = -math.inf
    y_min = math.inf
    y_max = -math.inf
    for trace in traces:
        x = np.asarray(trace["time_ms"], dtype=np.float64)
        y = np.asarray(trace["values"], dtype=np.float64)
        x, y = _downsample_series(x, y)
        transformed, detail = _transform_values(y, transform)
        if x.size == 0 or transformed.size == 0:
            continue
        x_min = min(x_min, float(np.min(x)))
        x_max = max(x_max, float(np.max(x)))
        y_min = min(y_min, float(np.min(transformed)))
        y_max = max(y_max, float(np.max(transformed)))
        prepared.append(
            {
                "label": str(trace["label"]),
                "color": str(trace["color"]),
                "x": x,
                "y": transformed,
                "detail": detail,
            }
        )
    if not prepared:
        return "<svg viewBox='0 0 820 260'><text x='24' y='36'>No trace data available.</text></svg>"
    if not math.isfinite(y_min) or not math.isfinite(y_max):
        y_min, y_max = -1.0, 1.0
    if math.isclose(x_min, x_max):
        x_min -= 1.0
        x_max += 1.0
    if math.isclose(y_min, y_max):
        pad = 1.0 if math.isclose(y_min, 0.0) else abs(y_min) * 0.1
        y_min -= pad
        y_max += pad

    def x_px(value: float) -> float:
        return left + ((value - x_min) / (x_max - x_min)) * plot_width

    def y_px(value: float) -> float:
        return top + plot_height - ((value - y_min) / (y_max - y_min)) * plot_height

    grid_lines = []
    for tick in range(5):
        fraction = tick / 4.0
        y_value = y_min + fraction * (y_max - y_min)
        py = y_px(y_value)
        grid_lines.append(
            f"<line x1='{left:.2f}' y1='{py:.2f}' x2='{left + plot_width:.2f}' y2='{py:.2f}' stroke='#e6d8c6' stroke-width='1' />"
        )
        grid_lines.append(
            f"<text x='8' y='{py + 4:.2f}' font-size='11' fill='#6b6259'>{html.escape(_format_float(y_value))}</text>"
        )
    path_elements = []
    legend = []
    for index, trace in enumerate(prepared):
        points = [
            f"{x_px(float(x_value)):.2f},{y_px(float(y_value)):.2f}"
            for x_value, y_value in zip(trace["x"], trace["y"], strict=False)
        ]
        if not points:
            continue
        path_elements.append(
            f"<polyline fill='none' stroke='{trace['color']}' stroke-width='2.2' points='{' '.join(points)}' />"
        )
        legend_y = 16 + index * 16
        legend.append(
            f"<line x1='{width - 210:.2f}' y1='{legend_y:.2f}' x2='{width - 186:.2f}' y2='{legend_y:.2f}' stroke='{trace['color']}' stroke-width='3' />"
            f"<text x='{width - 178:.2f}' y='{legend_y + 4:.2f}' font-size='12' fill='#1c1917'>{html.escape(trace['label'])}</text>"
        )
    x_labels = [
        f"<text x='{left:.2f}' y='{height - 8:.2f}' font-size='11' fill='#6b6259'>{html.escape(_format_float(x_min))} ms</text>",
        f"<text x='{left + plot_width - 52:.2f}' y='{height - 8:.2f}' font-size='11' fill='#6b6259'>{html.escape(_format_float(x_max))} ms</text>",
    ]
    subtitle = {
        "identity": "raw values",
        "normalized": "normalized to each series max |value|",
        "signed_log10": "signed log10(1 + |value|)",
    }[transform]
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{html.escape(title)}'>"
        f"<text x='{left:.2f}' y='18' font-size='15' font-weight='700' fill='#1c1917'>{html.escape(title)}</text>"
        f"<text x='{left + 240:.2f}' y='18' font-size='12' fill='#6b6259'>{html.escape(subtitle)}</text>"
        f"<rect x='{left:.2f}' y='{top:.2f}' width='{plot_width:.2f}' height='{plot_height:.2f}' fill='#fffaf2' stroke='#d7c6ae' rx='10' />"
        + "".join(grid_lines)
        + f"<line x1='{left:.2f}' y1='{top + plot_height:.2f}' x2='{left + plot_width:.2f}' y2='{top + plot_height:.2f}' stroke='#6b6259' stroke-width='1.1' />"
        + "".join(path_elements)
        + "".join(legend)
        + "".join(x_labels)
        + "</svg>"
    )


def _transform_values(values: np.ndarray, mode: str) -> tuple[np.ndarray, str]:
    normalized = np.asarray(values, dtype=np.float64)
    if mode == "identity":
        return normalized, "raw"
    if mode == "normalized":
        scale = float(np.max(np.abs(normalized)))
        if scale <= 0.0:
            scale = 1.0
        return normalized / scale, f"normalized by {scale}"
    if mode == "signed_log10":
        return np.sign(normalized) * np.log10(1.0 + np.abs(normalized)), "signed log10"
    raise ValueError(f"Unsupported trace transform {mode!r}.")


def _downsample_series(
    x_values: np.ndarray,
    y_values: np.ndarray,
    *,
    max_points: int = 400,
) -> tuple[np.ndarray, np.ndarray]:
    if x_values.shape != y_values.shape:
        raise ValueError("x_values and y_values must share the same shape for chart downsampling.")
    if x_values.size <= max_points:
        return x_values, y_values
    sample_indices = np.linspace(0, x_values.size - 1, num=max_points, dtype=np.int64)
    sample_indices = np.unique(sample_indices)
    return x_values[sample_indices], y_values[sample_indices]


def _resolve_processed_simulator_results_dir(bundle_directory: Path) -> Path:
    resolved = bundle_directory.resolve()
    for parent in resolved.parents:
        if parent.name == "bundles":
            return parent.parent.resolve()
    raise ValueError(
        f"Could not resolve processed_simulator_results_dir from bundle directory {resolved}."
    )


def _slugify(value: str) -> str:
    collapsed = []
    last_was_dash = False
    for char in value.lower():
        if char.isalnum():
            collapsed.append(char)
            last_was_dash = False
        else:
            if not last_was_dash:
                collapsed.append("-")
            last_was_dash = True
    return "".join(collapsed).strip("-") or "item"


def _format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    numeric = float(value)
    if not math.isfinite(numeric):
        return str(numeric)
    if numeric == 0.0:
        return "0"
    magnitude = abs(numeric)
    if magnitude >= 1_000.0 or magnitude < 0.01:
        return f"{numeric:.3e}"
    return f"{numeric:.4f}".rstrip("0").rstrip(".")


__all__ = [
    "SIMULATOR_VISUALIZATION_REPORT_VERSION",
    "build_simulator_visualization_output_dir",
    "generate_simulator_visualization_report",
]
