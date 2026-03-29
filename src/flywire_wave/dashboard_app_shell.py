from __future__ import annotations

import hashlib
import html
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    CIRCUIT_PANE_ID,
    METADATA_JSON_KEY,
    MORPHOLOGY_PANE_ID,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    TIME_SERIES_PANE_ID,
    build_dashboard_session_contract_metadata,
    discover_dashboard_export_targets,
    discover_dashboard_panes,
)
from .io_utils import ensure_dir, write_json
from .stimulus_contract import DEFAULT_HASH_ALGORITHM


DASHBOARD_APP_SHELL_VERSION = "dashboard_app_shell.v1"
DASHBOARD_APP_BOOTSTRAP_FORMAT = "json_dashboard_app_bootstrap.v1"
DASHBOARD_APP_ASSET_MANIFEST_FORMAT = "json_dashboard_app_asset_manifest.v1"
DASHBOARD_LINKED_STATE_MODEL_VERSION = "dashboard_linked_state.v1"

_APP_ASSET_MANIFEST_FILE_NAME = "dashboard_asset_manifest.json"
_ASSET_DIRECTORY_NAME = "assets"
_STYLE_ASSET_STEM = "dashboard_shell"
_SCRIPT_ASSET_STEM = "dashboard_shell"


def build_dashboard_app_shell(
    *,
    metadata: Mapping[str, Any],
    payload: Mapping[str, Any],
    session_state: Mapping[str, Any],
    app_shell_path: str | Path,
) -> dict[str, Any]:
    metadata_mapping = _require_mapping(metadata, field_name="metadata")
    payload_mapping = _require_mapping(payload, field_name="payload")
    session_state_mapping = _require_mapping(
        session_state,
        field_name="session_state",
    )
    app_shell_file = Path(app_shell_path).resolve()
    app_directory = app_shell_file.parent
    asset_directory = (app_directory / _ASSET_DIRECTORY_NAME).resolve()
    asset_manifest_path = (app_directory / _APP_ASSET_MANIFEST_FILE_NAME).resolve()
    ensure_dir(asset_directory)
    _cleanup_generated_assets(asset_directory)

    style_source = _load_asset_source("dashboard_shell.css")
    script_source = _load_asset_source("dashboard_shell.js")
    style_record = _write_static_asset(
        asset_directory=asset_directory,
        asset_stem=_STYLE_ASSET_STEM,
        extension="css",
        content=style_source,
        media_type="text/css",
    )
    script_record = _write_static_asset(
        asset_directory=asset_directory,
        asset_stem=_SCRIPT_ASSET_STEM,
        extension="js",
        content=script_source,
        media_type="text/javascript",
    )

    bootstrap = _build_dashboard_app_bootstrap(
        metadata=metadata_mapping,
        payload=payload_mapping,
        session_state=session_state_mapping,
        app_directory=app_directory,
        asset_manifest_path=asset_manifest_path,
    )
    bootstrap_hash = _stable_content_hash(bootstrap)
    asset_manifest = {
        "format_version": DASHBOARD_APP_ASSET_MANIFEST_FORMAT,
        "app_shell_version": DASHBOARD_APP_SHELL_VERSION,
        "bundle_reference": copy_json(bootstrap["bundle_reference"]),
        "asset_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "bootstrap_hash": bootstrap_hash,
        "assets": {
            "style": copy_json(style_record),
            "script": copy_json(script_record),
        },
    }
    write_json(asset_manifest, asset_manifest_path)

    app_shell_file.write_text(
        _render_dashboard_app_html(
            metadata=metadata_mapping,
            bootstrap=bootstrap,
            asset_manifest=asset_manifest,
            app_shell_path=app_shell_file,
            style_path=Path(style_record["path"]).resolve(),
            script_path=Path(script_record["path"]).resolve(),
            asset_manifest_path=asset_manifest_path,
        ),
        encoding="utf-8",
    )
    return {
        "app_shell_path": str(app_shell_file),
        "app_shell_file_url": app_shell_file.as_uri(),
        "asset_manifest_path": str(asset_manifest_path),
        "style_asset_path": str(style_record["path"]),
        "script_asset_path": str(script_record["path"]),
        "bootstrap_hash": bootstrap_hash,
    }


def _cleanup_generated_assets(asset_directory: Path) -> None:
    for pattern in (
        f"{_STYLE_ASSET_STEM}.*.css",
        f"{_SCRIPT_ASSET_STEM}.*.js",
    ):
        for path in asset_directory.glob(pattern):
            if path.is_file():
                path.unlink()


def _load_asset_source(file_name: str) -> str:
    asset_path = Path(__file__).resolve().with_name("dashboard_assets") / file_name
    if not asset_path.exists():
        raise FileNotFoundError(f"Dashboard app asset source is missing: {asset_path}")
    return asset_path.read_text(encoding="utf-8")


def _write_static_asset(
    *,
    asset_directory: Path,
    asset_stem: str,
    extension: str,
    content: str,
    media_type: str,
) -> dict[str, Any]:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    asset_path = (asset_directory / f"{asset_stem}.{content_hash[:12]}.{extension}").resolve()
    asset_path.write_text(content, encoding="utf-8")
    return {
        "file_name": asset_path.name,
        "path": str(asset_path),
        "relative_path": _relative_href(asset_directory.parent, asset_path),
        "media_type": media_type,
        "content_hash": content_hash,
    }


def _build_dashboard_app_bootstrap(
    *,
    metadata: Mapping[str, Any],
    payload: Mapping[str, Any],
    session_state: Mapping[str, Any],
    app_directory: Path,
    asset_manifest_path: Path,
) -> dict[str, Any]:
    contract_metadata = build_dashboard_session_contract_metadata()
    pane_catalog = [
        {
            "pane_id": str(item["pane_id"]),
            "display_name": str(item["display_name"]),
            "description": str(item["description"]),
            "default_overlay_id": str(item["default_overlay_id"]),
            "supports_time_cursor": bool(item["supports_time_cursor"]),
            "supports_neuron_selection": bool(item["supports_neuron_selection"]),
            "supports_readout_selection": bool(item["supports_readout_selection"]),
        }
        for item in discover_dashboard_panes(contract_metadata)
    ]
    comparison_mode_catalog = [
        {
            "comparison_mode_id": str(item["comparison_mode_id"]),
            "display_name": str(item["display_name"]),
            "description": str(item["description"]),
            "required_arm_count": int(item["required_arm_count"]),
            "requires_shared_timebase": bool(item["requires_shared_timebase"]),
        }
        for item in contract_metadata["comparison_mode_catalog"]
    ]
    overlay_definitions = [
        {
            "overlay_id": str(item["overlay_id"]),
            "display_name": str(item["display_name"]),
            "description": str(item["description"]),
            "overlay_category": str(item["overlay_category"]),
            "supported_pane_ids": list(item["supported_pane_ids"]),
            "supported_comparison_modes": list(item["supported_comparison_modes"]),
        }
        for item in contract_metadata["overlay_catalog"]
    ]
    enabled_export_target_ids = {
        str(item)
        for item in session_state.get("enabled_export_target_ids", [])
    }
    export_target_catalog = [
        {
            "export_target_id": str(item["export_target_id"]),
            "display_name": str(item["display_name"]),
            "description": str(item["description"]),
            "target_kind": str(item["target_kind"]),
            "supported_pane_ids": list(item["supported_pane_ids"]),
            "requires_time_cursor": bool(item["requires_time_cursor"]),
        }
        for item in discover_dashboard_export_targets(contract_metadata)
        if str(item["export_target_id"]) in enabled_export_target_ids
    ]
    overlay_statuses = _overlay_status_catalog(payload)
    pane_inputs = _require_mapping(payload.get("pane_inputs"), field_name="payload.pane_inputs")
    analysis_context = _require_mapping(
        pane_inputs.get(ANALYSIS_PANE_ID),
        field_name="payload.pane_inputs.analysis",
    )
    validation_evidence = _require_mapping(
        analysis_context.get("validation_evidence", {}),
        field_name="payload.pane_inputs.analysis.validation_evidence",
    )
    time_series_context = _require_mapping(
        pane_inputs.get(TIME_SERIES_PANE_ID),
        field_name="payload.pane_inputs.time_series",
    )
    replay_model = _require_mapping(
        time_series_context.get("replay_model"),
        field_name="payload.pane_inputs.time_series.replay_model",
    )
    replay_state = _require_mapping(
        session_state.get("replay_state", {}),
        field_name="session_state.replay_state",
    )

    return {
        "format_version": DASHBOARD_APP_BOOTSTRAP_FORMAT,
        "app_shell_version": DASHBOARD_APP_SHELL_VERSION,
        "state_model": {
            "model_version": DASHBOARD_LINKED_STATE_MODEL_VERSION,
            "owned_state_fields": [
                "selected_arm_pair",
                "selected_neuron_id",
                "selected_readout_id",
                "active_overlay_id",
                "comparison_mode",
                "time_cursor",
            ],
            "time_cursor_fields": [
                "time_ms",
                "sample_index",
                "playback_state",
            ],
            "transient_state_fields": [
                "hovered_neuron_id",
                "hover_source_pane_id",
            ],
            "serialized_state_fields": [
                "global_interaction_state",
                "replay_state",
            ],
        },
        "bundle_reference": {
            "bundle_id": str(metadata["bundle_id"]),
            "session_spec_hash": str(metadata["session_spec_hash"]),
            "ui_delivery_model": str(metadata["ui_delivery_model"]),
            "bundle_directory": str(metadata["bundle_layout"]["bundle_directory"]),
        },
        "manifest_reference": copy_json(metadata["manifest_reference"]),
        "source_mode": payload.get("source_mode"),
        "pane_catalog": pane_catalog,
        "comparison_mode_catalog": comparison_mode_catalog,
        "overlay_catalog": {
            "active_overlay_id": str(payload["overlay_catalog"]["active_overlay_id"]),
            "available_overlay_ids": list(payload["overlay_catalog"]["available_overlay_ids"]),
            "base_availability_by_id": overlay_statuses,
            "overlay_definitions": overlay_definitions,
        },
        "export_target_catalog": export_target_catalog,
        "global_interaction_state": copy_json(session_state["global_interaction_state"]),
        "replay_model": copy_json(replay_model),
        "replay_state": copy_json(replay_state),
        "selected_bundle_pair": copy_json(payload["selected_bundle_pair"]),
        "selection": copy_json(payload["selection"]),
        "scene_context": copy_json(pane_inputs[SCENE_PANE_ID]),
        "circuit_context": copy_json(pane_inputs[CIRCUIT_PANE_ID]),
        "morphology_context": copy_json(pane_inputs[MORPHOLOGY_PANE_ID]),
        "time_series_context": copy_json(time_series_context),
        "analysis_context": copy_json(analysis_context),
        "artifact_inventory": [
            {
                "artifact_role_id": str(item["artifact_role_id"]),
                "path": str(item["path"]),
                "status": str(item["status"]),
                "artifact_scope": str(item["artifact_scope"]),
            }
            for item in payload.get("artifact_inventory", [])
            if isinstance(item, Mapping)
        ],
        "enabled_export_target_ids": list(session_state["enabled_export_target_ids"]),
        "default_export_target_id": str(session_state["default_export_target_id"]),
        "links": {
            "dashboard_session_metadata": _relative_href(
                app_directory,
                Path(metadata["artifacts"][METADATA_JSON_KEY]["path"]).resolve(),
            ),
            "dashboard_session_payload": _relative_href(
                app_directory,
                Path(metadata["artifacts"][SESSION_PAYLOAD_ARTIFACT_ID]["path"]).resolve(),
            ),
            "dashboard_session_state": _relative_href(
                app_directory,
                Path(metadata["artifacts"][SESSION_STATE_ARTIFACT_ID]["path"]).resolve(),
            ),
            "analysis_offline_report": _optional_relative_href(
                app_directory,
                analysis_context.get("offline_report_path"),
                bool(analysis_context["offline_report_exists"]),
            ),
            "validation_offline_report": _optional_relative_href(
                app_directory,
                validation_evidence.get("offline_report_path"),
                bool(validation_evidence.get("offline_report_exists", False)),
            ),
            "asset_manifest": _relative_href(app_directory, asset_manifest_path),
        },
    }


def _overlay_status_catalog(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    overlay_catalog = _require_mapping(
        payload.get("overlay_catalog"),
        field_name="payload.overlay_catalog",
    )
    status_by_id: dict[str, dict[str, Any]] = {}
    for bucket_name in ("available_overlays", "unavailable_overlays"):
        for item in overlay_catalog.get(bucket_name, []):
            if not isinstance(item, Mapping):
                continue
            overlay_id = str(item["overlay_id"])
            status_by_id[overlay_id] = {
                "availability": str(item["availability"]),
                "reason": item.get("reason"),
                "overlay_category": str(item["overlay_category"]),
                "display_name": str(item["display_name"]),
                "supported_pane_ids": list(item["supported_pane_ids"]),
            }
    return status_by_id


def _render_dashboard_app_html(
    *,
    metadata: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    asset_manifest: Mapping[str, Any],
    app_shell_path: Path,
    style_path: Path,
    script_path: Path,
    asset_manifest_path: Path,
) -> str:
    style_href = _relative_href(app_shell_path.parent, style_path)
    script_href = _relative_href(app_shell_path.parent, script_path)
    asset_manifest_href = _relative_href(app_shell_path.parent, asset_manifest_path)
    bundle_reference = bootstrap["bundle_reference"]
    state = bootstrap["global_interaction_state"]
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\" />",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
            f"  <title>{html.escape(str(metadata['experiment_id']))} Dashboard</title>",
            f"  <link rel=\"stylesheet\" href=\"{html.escape(style_href)}\" />",
            "</head>",
            "<body>",
            "  <div class=\"shell-background\" aria-hidden=\"true\">",
            "    <div class=\"shell-orb shell-orb-a\"></div>",
            "    <div class=\"shell-orb shell-orb-b\"></div>",
            "    <div class=\"shell-grid\"></div>",
            "  </div>",
            "  <div class=\"app-shell\" data-dashboard-root=\"true\">",
            "    <header class=\"shell-hero\">",
            "      <div class=\"hero-copy\">",
            "        <p class=\"eyebrow\">Milestone 14 Dashboard Session</p>",
            "        <h1>Linked offline dashboard for packaged local sessions.</h1>",
            "        <p class=\"hero-text\">The first shell stays file-system friendly: deterministic HTML, deterministic asset names, no backend, and one canonical state model shared across all five panes.</p>",
            "      </div>",
            "      <div class=\"hero-facts\">",
            _fact_card_html("Experiment", str(metadata["experiment_id"])),
            _fact_card_html("Bundle", str(bundle_reference["bundle_id"])),
            _fact_card_html("Overlay", str(state["active_overlay_id"])),
            _fact_card_html("Comparison", str(state["comparison_mode"])),
            _fact_card_html(
                "Cursor",
                f"{state['time_cursor']['time_ms']:.1f} ms / sample {state['time_cursor']['sample_index']}",
            ),
            "      </div>",
            "    </header>",
            "    <section class=\"toolbar-card\" aria-label=\"Linked controls\">",
            "      <div class=\"toolbar-header\">",
            "        <div>",
            "          <p class=\"section-kicker\">Application Controls</p>",
            "          <h2>One shared state model drives selection, overlays, comparison, and replay.</h2>",
            "        </div>",
            f"        <a class=\"manifest-link\" href=\"{html.escape(asset_manifest_href)}\">Asset manifest</a>",
            "      </div>",
            _render_toolbar_controls(bootstrap),
            "    </section>",
            "    <main class=\"dashboard-grid\" aria-label=\"Dashboard panes\">",
            _render_pane_shells(bootstrap),
            "    </main>",
            "    <footer class=\"shell-footer\">",
            "      <div class=\"artifact-links\">",
            "        <a href=\"../dashboard_session.json\">dashboard_session.json</a>",
            "        <a href=\"../dashboard_session_payload.json\">dashboard_session_payload.json</a>",
            "        <a href=\"../session_state.json\">session_state.json</a>",
            _optional_anchor_html(
                bootstrap["links"].get("analysis_offline_report"),
                "analysis_report",
            ),
            _optional_anchor_html(
                bootstrap["links"].get("validation_offline_report"),
                "validation_report",
            ),
            "      </div>",
            "      <p class=\"footer-note\">Open this bundle directly from local disk. The shell embeds its bootstrap payload so file:// review does not depend on client-side fetch privileges.</p>",
            "    </footer>",
            "  </div>",
            f"  <script id=\"dashboard-app-bootstrap\" type=\"application/json\">{html.escape(_stable_json(bootstrap))}</script>",
            f"  <script id=\"dashboard-app-asset-manifest\" type=\"application/json\">{html.escape(_stable_json(asset_manifest))}</script>",
            f"  <script src=\"{html.escape(script_href)}\"></script>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _render_toolbar_controls(bootstrap: Mapping[str, Any]) -> str:
    state = bootstrap["global_interaction_state"]
    selected_bundle_pair = bootstrap["selected_bundle_pair"]
    timebase = bootstrap["time_series_context"]["timebase"]
    return "\n".join(
        [
            "      <div class=\"toolbar-grid\">",
            "        <div class=\"control-cluster\">",
            "          <span class=\"control-label\">Active Arm</span>",
            "          <div class=\"segmented-controls\" data-active-arm-group=\"true\">",
            _arm_button_html(
                str(selected_bundle_pair["baseline"]["arm_id"]),
                "Baseline",
                str(state["selected_arm_pair"]["active_arm_id"]) == str(selected_bundle_pair["baseline"]["arm_id"]),
            ),
            _arm_button_html(
                str(selected_bundle_pair["wave"]["arm_id"]),
                "Wave",
                str(state["selected_arm_pair"]["active_arm_id"]) == str(selected_bundle_pair["wave"]["arm_id"]),
            ),
            "          </div>",
            "        </div>",
            _select_control_html(
                control_id="dashboard-comparison-mode",
                label="Comparison",
                option_records=bootstrap["comparison_mode_catalog"],
                option_value_key="comparison_mode_id",
                option_label_key="display_name",
                selected_value=str(state["comparison_mode"]),
            ),
            _overlay_select_html(bootstrap),
            _select_control_html(
                control_id="dashboard-neuron",
                label="Neuron",
                option_records=bootstrap["morphology_context"]["root_catalog"],
                option_value_key="root_id",
                option_label_key="root_id",
                selected_value=str(state["selected_neuron_id"]),
                decorate_option=_format_root_option_label,
            ),
            _select_control_html(
                control_id="dashboard-readout",
                label="Readout",
                option_records=bootstrap["time_series_context"]["comparable_readout_catalog"],
                option_value_key="readout_id",
                option_label_key="readout_id",
                selected_value=str(state["selected_readout_id"]),
                decorate_option=_format_readout_option_label,
            ),
            "        <div class=\"control-cluster playback-cluster\">",
            "          <span class=\"control-label\">Replay</span>",
            "          <div class=\"playback-controls\">",
            "            <button type=\"button\" class=\"playback-button\" data-playback-action=\"rewind\">Rewind</button>",
            "            <button type=\"button\" class=\"playback-button\" data-playback-action=\"step_back\">Back</button>",
            "            <button type=\"button\" class=\"playback-button\" data-playback-action=\"toggle\">Play</button>",
            "            <button type=\"button\" class=\"playback-button\" data-playback-action=\"step_forward\">Next</button>",
            "          </div>",
            f"          <input id=\"dashboard-time-cursor\" class=\"time-slider\" type=\"range\" min=\"0\" max=\"{int(timebase['sample_count']) - 1}\" value=\"{int(state['time_cursor']['sample_index'])}\" step=\"1\" />",
            "          <p class=\"time-readout\" data-time-readout=\"true\"></p>",
            "        </div>",
            "      </div>",
        ]
    )


def _render_pane_shells(bootstrap: Mapping[str, Any]) -> str:
    pane_markup: list[str] = []
    summaries = _initial_pane_summaries(bootstrap)
    for pane in bootstrap["pane_catalog"]:
        pane_id = str(pane["pane_id"])
        pane_markup.extend(
            [
                f"      <section class=\"dashboard-pane pane-{html.escape(pane_id)}\" data-pane-id=\"{html.escape(pane_id)}\">",
                "        <div class=\"pane-header\">",
                f"          <p class=\"section-kicker\">{html.escape(pane_id)}</p>",
                f"          <h2>{html.escape(str(pane['display_name']))}</h2>",
                f"          <p class=\"pane-description\">{html.escape(str(pane['description']))}</p>",
                "        </div>",
                f"        <div class=\"pane-body\" data-pane-body=\"{html.escape(pane_id)}\">",
                summaries[pane_id],
                "        </div>",
                "      </section>",
            ]
        )
    return "\n".join(pane_markup)


def _initial_pane_summaries(bootstrap: Mapping[str, Any]) -> dict[str, str]:
    scene = bootstrap["scene_context"]
    circuit = bootstrap["circuit_context"]
    morphology = bootstrap["morphology_context"]
    time_series = bootstrap["time_series_context"]
    analysis = bootstrap["analysis_context"]
    state = bootstrap["global_interaction_state"]
    return {
        SCENE_PANE_ID: _summary_list_html(
            [
                ("Source", str(scene["source_kind"])),
                (
                    "Stimulus",
                    str(scene.get("stimulus_name", scene.get("representation_family", "n/a"))),
                ),
                ("Conditions", ", ".join(scene.get("selected_condition_ids", [])) or "n/a"),
                ("Active Arm", str(state["selected_arm_pair"]["active_arm_id"])),
            ]
        ),
        CIRCUIT_PANE_ID: _summary_list_html(
            [
                ("Selected Roots", str(circuit["selected_root_ids"])),
                ("Root Count", str(len(circuit["selected_root_ids"]))),
                ("Local Synapses", os.path.basename(str(circuit["local_synapse_registry_path"]))),
                ("Overlay", str(state["active_overlay_id"])),
            ]
        ),
        MORPHOLOGY_PANE_ID: _summary_list_html(
            [
                ("Selected Neuron", str(morphology["selected_neuron_id"])),
                ("Displayable Roots", str(morphology["displayable_root_ids"])),
                (
                    "Fidelity Classes",
                    ", ".join(
                        f"{key}:{value}"
                        for key, value in sorted(
                            morphology.get("fidelity_summary", {})
                            .get("class_counts", {})
                            .items()
                        )
                    )
                    or "n/a",
                ),
                ("Playback", str(state["time_cursor"]["playback_state"])),
            ]
        ),
        TIME_SERIES_PANE_ID: _summary_list_html(
            [
                ("Selected Readout", str(time_series["selected_readout_id"])),
                ("dt", f"{float(time_series['timebase']['dt_ms']):.1f} ms"),
                ("Samples", str(int(time_series["timebase"]["sample_count"]))),
                ("Comparison", str(state["comparison_mode"])),
            ]
        ),
        ANALYSIS_PANE_ID: _summary_list_html(
            [
                ("Phase Maps", str(int(analysis["phase_map_reference_count"]))),
                ("Wave Cards", str(int(analysis["wave_diagnostic_card_count"]))),
                ("Validation", str(analysis["validation"]["overall_status"])),
                ("Review", str(analysis["validation"]["review_status"])),
            ]
        ),
    }


def _summary_list_html(items: list[tuple[str, str]]) -> str:
    lines = ["          <dl class=\"summary-list\">"]
    for label, value in items:
        lines.append(f"            <dt>{html.escape(label)}</dt>")
        lines.append(f"            <dd>{html.escape(value)}</dd>")
    lines.append("          </dl>")
    return "\n".join(lines)


def _fact_card_html(label: str, value: str) -> str:
    return "\n".join(
        [
            "        <article class=\"fact-card\">",
            f"          <span class=\"fact-label\">{html.escape(label)}</span>",
            f"          <span class=\"fact-value\">{html.escape(value)}</span>",
            "        </article>",
        ]
    )


def _select_control_html(
    *,
    control_id: str,
    label: str,
    option_records: list[dict[str, Any]],
    option_value_key: str,
    option_label_key: str,
    selected_value: str,
    decorate_option: Any | None = None,
) -> str:
    option_markup = []
    for item in option_records:
        option_value = str(item[option_value_key])
        label_value = (
            decorate_option(item)
            if decorate_option is not None
            else str(item[option_label_key])
        )
        selected_attr = " selected" if option_value == selected_value else ""
        option_markup.append(
            f"<option value=\"{html.escape(option_value)}\"{selected_attr}>{html.escape(label_value)}</option>"
        )
    return "\n".join(
        [
            "        <label class=\"control-cluster\">",
            f"          <span class=\"control-label\">{html.escape(label)}</span>",
            f"          <select id=\"{html.escape(control_id)}\">",
            "            " + "\n            ".join(option_markup),
            "          </select>",
            "        </label>",
        ]
    )


def _overlay_select_html(bootstrap: Mapping[str, Any]) -> str:
    state = bootstrap["global_interaction_state"]
    options = []
    overlay_definitions = bootstrap["overlay_catalog"]["overlay_definitions"]
    base_statuses = bootstrap["overlay_catalog"]["base_availability_by_id"]
    for definition in overlay_definitions:
        overlay_id = str(definition["overlay_id"])
        status = base_statuses.get(
            overlay_id,
            {
                "availability": "available",
                "reason": None,
                "display_name": definition["display_name"],
            },
        )
        disabled_attr = ""
        label_suffix = ""
        if str(status["availability"]) != "available":
            disabled_attr = " disabled"
            label_suffix = " (Unavailable)"
        selected_attr = " selected" if overlay_id == str(state["active_overlay_id"]) else ""
        options.append(
            f"<option value=\"{html.escape(overlay_id)}\"{selected_attr}{disabled_attr}>{html.escape(str(definition['display_name']) + label_suffix)}</option>"
        )
    return "\n".join(
        [
            "        <label class=\"control-cluster\">",
            "          <span class=\"control-label\">Overlay</span>",
            "          <select id=\"dashboard-overlay-mode\">",
            "            " + "\n            ".join(options),
            "          </select>",
            "        </label>",
        ]
    )


def _arm_button_html(arm_id: str, label: str, active: bool) -> str:
    active_class = " is-active" if active else ""
    return (
        f"<button type=\"button\" class=\"segment-button{active_class}\" "
        f"data-arm-id=\"{html.escape(arm_id)}\">{html.escape(label)}</button>"
    )


def _optional_anchor_html(href: str | None, label: str) -> str:
    if not href:
        return ""
    return f"        <a href=\"{html.escape(href)}\">{html.escape(label)}</a>"


def _optional_relative_href(
    app_directory: Path,
    target: Any,
    exists: bool,
) -> str | None:
    if not exists or target in {None, ""}:
        return None
    return _relative_href(app_directory, Path(str(target)).resolve())


def _relative_href(source_directory: Path, target_path: Path) -> str:
    return Path(os.path.relpath(target_path, start=source_directory)).as_posix()


def _format_root_option_label(item: Mapping[str, Any]) -> str:
    label_parts = [str(item["root_id"])]
    if item.get("cell_type"):
        label_parts.append(str(item["cell_type"]))
    if item.get("morphology_class"):
        label_parts.append(str(item["morphology_class"]))
    return " | ".join(label_parts)


def _format_readout_option_label(item: Mapping[str, Any]) -> str:
    label_parts = [str(item["readout_id"])]
    display_name = item.get("display_name")
    if display_name:
        label_parts.append(str(display_name))
    units = item.get("units")
    if units:
        label_parts.append(f"[{units}]")
    return " | ".join(label_parts)


def _stable_content_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(value)


def copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=True))
