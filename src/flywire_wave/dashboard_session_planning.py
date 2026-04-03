from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_app_shell import build_dashboard_app_shell
from .dashboard_analysis import build_dashboard_analysis_context
from .dashboard_morphology import build_dashboard_morphology_context
from .dashboard_replay import (
    build_dashboard_replay_state,
    build_dashboard_time_series_context,
)
from .dashboard_scene_circuit import (
    DASHBOARD_WHOLE_BRAIN_CONTEXT_VERSION,
    load_dashboard_whole_brain_context,
    normalize_dashboard_circuit_context,
    resolve_dashboard_scene_context,
)
from .config import get_config_path, get_project_root, load_config
from .dashboard_session_contract import (
    ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_OFFLINE_REPORT_ROLE_ID,
    ANALYSIS_PANE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    APP_SHELL_INDEX_ARTIFACT_ID,
    BASELINE_BUNDLE_METADATA_ROLE_ID,
    BASELINE_UI_PAYLOAD_ROLE_ID,
    CIRCUIT_PANE_ID,
    DASHBOARD_APP_SHELL_ROLE_ID,
    DASHBOARD_SESSION_CONTRACT_VERSION,
    DASHBOARD_SESSION_DESIGN_NOTE,
    DEFAULT_COMPARISON_MODE,
    DEFAULT_EXPORT_TARGET_ID,
    DEFAULT_UI_DELIVERY_MODEL,
    DEFAULT_ACTIVE_OVERLAY_ID,
    METADATA_JSON_KEY,
    MORPHOLOGY_PANE_ID,
    PAIRED_READOUT_DELTA_OVERLAY_ID,
    PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
    STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    SINGLE_ARM_COMPARISON_MODE,
    TIME_SERIES_PANE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_OFFLINE_REPORT_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    VALIDATION_STATUS_BADGES_OVERLAY_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_QUERY_CATALOG_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_VIEW_PAYLOAD_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_VIEW_STATE_ROLE_ID,
    WAVE_BUNDLE_METADATA_ROLE_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    WAVE_UI_PAYLOAD_ROLE_ID,
    build_dashboard_global_interaction_state,
    build_dashboard_selected_arm_pair_reference,
    build_dashboard_session_artifact_reference,
    build_dashboard_session_contract_metadata,
    build_dashboard_session_metadata,
    build_dashboard_time_cursor,
    discover_dashboard_overlays,
    discover_dashboard_session_bundle_paths,
    parse_dashboard_session_contract_metadata,
    write_dashboard_session_metadata,
)
from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    COMPARISON_MATRICES_ARTIFACT_ID,
    DEFAULT_ANALYSIS_DIRECTORY_NAME,
    EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    VISUALIZATION_CATALOG_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
    parse_experiment_analysis_bundle_metadata,
)
from .experiment_comparison_analysis import discover_experiment_bundle_set
from .io_utils import read_root_ids, write_json
from .simulation_planning import resolve_manifest_simulation_plan
from .simulator_result_contract import (
    BASELINE_MODEL_MODE,
    DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    METRICS_TABLE_KEY,
    MODEL_ARTIFACTS_KEY,
    READOUT_TRACES_KEY,
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    STATE_SUMMARY_KEY,
    SURFACE_WAVE_MODEL_MODE,
    discover_simulator_extension_artifacts,
    discover_simulator_result_bundle_paths,
    load_simulator_result_bundle_metadata,
    parse_simulator_result_bundle_metadata,
)
from .validation_contract import (
    DEFAULT_VALIDATION_DIRECTORY_NAME,
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
    REVIEW_HANDOFF_ARTIFACT_ID,
    VALIDATOR_FINDINGS_ARTIFACT_ID,
    VALIDATION_LADDER_CONTRACT_VERSION,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    discover_validation_bundle_paths,
    load_validation_bundle_metadata,
    parse_validation_bundle_metadata,
)
from .whole_brain_context_contract import (
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
    discover_whole_brain_context_session_bundle_paths,
    load_whole_brain_context_session_metadata,
    parse_whole_brain_context_session_metadata,
)
from .stimulus_contract import (
    ASSET_STATUS_READY,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_int,
)


DASHBOARD_SESSION_PLAN_VERSION = "dashboard_session_plan.v1"
DASHBOARD_SESSION_PAYLOAD_VERSION = "json_dashboard_session_payload.v1"
DASHBOARD_SESSION_STATE_VERSION = "json_dashboard_session_state.v1"
DASHBOARD_SESSION_SOURCE_MODE_MANIFEST = "manifest"
DASHBOARD_SESSION_SOURCE_MODE_EXPERIMENT = "experiment"
DASHBOARD_SESSION_SOURCE_MODE_EXPLICIT = "explicit_bundle_inputs"


def resolve_manifest_dashboard_session_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    **overrides: Any,
) -> dict[str, Any]:
    return resolve_dashboard_session_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        **overrides,
    )


def resolve_dashboard_session_plan(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    experiment_id: str | None = None,
    baseline_bundle_metadata: Mapping[str, Any] | None = None,
    baseline_bundle_metadata_path: str | Path | None = None,
    wave_bundle_metadata: Mapping[str, Any] | None = None,
    wave_bundle_metadata_path: str | Path | None = None,
    analysis_bundle_metadata: Mapping[str, Any] | None = None,
    analysis_bundle_metadata_path: str | Path | None = None,
    validation_bundle_metadata: Mapping[str, Any] | None = None,
    validation_bundle_metadata_path: str | Path | None = None,
    whole_brain_context_metadata: Mapping[str, Any] | None = None,
    whole_brain_context_metadata_path: str | Path | None = None,
    baseline_arm_id: str | None = None,
    wave_arm_id: str | None = None,
    active_arm_id: str | None = None,
    preferred_seed: int | str | None = None,
    preferred_condition_ids: Sequence[str] | None = None,
    selected_neuron_id: str | int | None = None,
    selected_readout_id: str | None = None,
    active_overlay_id: str = DEFAULT_ACTIVE_OVERLAY_ID,
    comparison_mode: str = DEFAULT_COMPARISON_MODE,
    enabled_export_target_ids: Sequence[str] | None = None,
    default_export_target_id: str = DEFAULT_EXPORT_TARGET_ID,
    ui_delivery_model: str = DEFAULT_UI_DELIVERY_MODEL,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")

    normalized_contract = parse_dashboard_session_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_dashboard_session_contract_metadata()
    )
    processed_dir = Path(
        cfg["paths"].get("processed_simulator_results_dir", DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR)
    ).resolve()

    explicit_baseline = _resolve_optional_simulator_bundle(
        bundle_metadata=baseline_bundle_metadata,
        bundle_metadata_path=baseline_bundle_metadata_path,
        field_name="baseline_bundle_metadata",
    )
    explicit_wave = _resolve_optional_simulator_bundle(
        bundle_metadata=wave_bundle_metadata,
        bundle_metadata_path=wave_bundle_metadata_path,
        field_name="wave_bundle_metadata",
    )
    explicit_analysis = _resolve_optional_analysis_bundle(
        bundle_metadata=analysis_bundle_metadata,
        bundle_metadata_path=analysis_bundle_metadata_path,
        field_name="analysis_bundle_metadata",
    )
    explicit_validation = _resolve_optional_validation_bundle(
        bundle_metadata=validation_bundle_metadata,
        bundle_metadata_path=validation_bundle_metadata_path,
        field_name="validation_bundle_metadata",
    )
    explicit_whole_brain_context = _resolve_optional_whole_brain_context_bundle(
        bundle_metadata=whole_brain_context_metadata,
        bundle_metadata_path=whole_brain_context_metadata_path,
        field_name="whole_brain_context_metadata",
    )

    source_mode = _resolve_source_mode(
        manifest_path=manifest_path,
        experiment_id=experiment_id,
        explicit_baseline=explicit_baseline,
        explicit_wave=explicit_wave,
        explicit_analysis=explicit_analysis,
        explicit_validation=explicit_validation,
    )
    normalized_experiment_id = _resolve_experiment_id(
        manifest_path=manifest_path,
        experiment_id=experiment_id,
        explicit_baseline=explicit_baseline,
        explicit_wave=explicit_wave,
        explicit_analysis=explicit_analysis,
        explicit_validation=explicit_validation,
    )

    simulation_plan = None
    bundle_set = None
    if manifest_path is not None:
        if schema_path is None or design_lock_path is None:
            raise ValueError(
                "Manifest-driven dashboard planning requires schema_path and design_lock_path."
            )
        simulation_plan = resolve_manifest_simulation_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
        bundle_set = discover_experiment_bundle_set(
            simulation_plan=simulation_plan,
            analysis_plan=simulation_plan["readout_analysis_plan"],
        )
        normalized_experiment_id = str(simulation_plan["manifest_reference"]["experiment_id"])

    resolved_analysis_bundle = _resolve_analysis_bundle(
        explicit_analysis=explicit_analysis,
        experiment_id=normalized_experiment_id,
        processed_simulator_results_dir=processed_dir,
        manifest_path=manifest_path,
    )
    inventory = _bundle_inventory_from_context(
        bundle_set=bundle_set,
        analysis_bundle=resolved_analysis_bundle,
    )

    resolved_validation_bundle = _resolve_validation_bundle(
        explicit_validation=explicit_validation,
        experiment_id=normalized_experiment_id,
        processed_simulator_results_dir=processed_dir,
        analysis_bundle=resolved_analysis_bundle,
        selected_arm_ids=_selected_arm_ids_from_overrides(
            explicit_baseline=explicit_baseline,
            explicit_wave=explicit_wave,
            baseline_arm_id=baseline_arm_id,
            wave_arm_id=wave_arm_id,
        ),
    )
    _ensure_processed_dir_alignment(
        processed_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        analysis_bundle=resolved_analysis_bundle,
        validation_bundle=resolved_validation_bundle,
        baseline_bundle=explicit_baseline,
        wave_bundle=explicit_wave,
    )

    arm_pair = _resolve_arm_pair(
        explicit_baseline=explicit_baseline,
        explicit_wave=explicit_wave,
        inventory=inventory,
        simulation_plan=simulation_plan,
        baseline_arm_id=baseline_arm_id,
        wave_arm_id=wave_arm_id,
    )
    baseline_item = _select_inventory_item(
        inventory=inventory,
        arm_id=arm_pair["baseline_arm_id"],
        explicit_bundle=explicit_baseline,
        simulation_plan=simulation_plan,
        preferred_seed=preferred_seed,
        preferred_condition_ids=preferred_condition_ids,
    )
    wave_item = _select_inventory_item(
        inventory=inventory,
        arm_id=arm_pair["wave_arm_id"],
        explicit_bundle=explicit_wave,
        simulation_plan=simulation_plan,
        preferred_seed=preferred_seed,
        preferred_condition_ids=preferred_condition_ids,
    )

    baseline_metadata = _inventory_item_metadata(baseline_item)
    wave_metadata = _inventory_item_metadata(wave_item)
    _validate_bundle_pair(
        baseline_item=baseline_item,
        wave_item=wave_item,
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
    )
    _validate_analysis_bundle_alignment(
        analysis_bundle=resolved_analysis_bundle,
        baseline_bundle_id=str(baseline_metadata["bundle_id"]),
        wave_bundle_id=str(wave_metadata["bundle_id"]),
        baseline_arm_id=arm_pair["baseline_arm_id"],
        wave_arm_id=arm_pair["wave_arm_id"],
    )
    _validate_validation_bundle_alignment(
        validation_bundle=resolved_validation_bundle,
        analysis_bundle=resolved_analysis_bundle,
        baseline_bundle_id=str(baseline_metadata["bundle_id"]),
        wave_bundle_id=str(wave_metadata["bundle_id"]),
        baseline_arm_id=arm_pair["baseline_arm_id"],
        wave_arm_id=arm_pair["wave_arm_id"],
    )

    baseline_paths = discover_simulator_result_bundle_paths(baseline_metadata)
    wave_paths = discover_simulator_result_bundle_paths(wave_metadata)
    _require_existing_path(
        baseline_paths[READOUT_TRACES_KEY],
        field_name="baseline_bundle.readout_traces",
    )
    _require_existing_path(
        wave_paths[READOUT_TRACES_KEY],
        field_name="wave_bundle.readout_traces",
    )

    scene_context = _resolve_scene_context(
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
        condition_ids=baseline_item["condition_ids"],
    )
    selection_context = _resolve_selection_context(
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
    )
    circuit_context = _resolve_circuit_context(
        geometry_manifest_path=Path(selection_context["geometry_manifest_path"]),
        selected_root_ids=selection_context["selected_root_ids"],
        local_synapse_registry_path=Path(selection_context["local_synapse_registry_path"]),
    )
    circuit_context["whole_brain_context"] = _resolve_whole_brain_context(
        whole_brain_context_bundle=explicit_whole_brain_context,
        selected_root_ids=selection_context["selected_root_ids"],
    )
    raw_analysis_context = _resolve_analysis_context(resolved_analysis_bundle)
    morphology_context = _resolve_morphology_context(
        circuit_context=circuit_context,
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
        analysis_context=raw_analysis_context,
        selected_neuron_id=selected_neuron_id,
    )
    time_series_context = _resolve_time_series_context(
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
        morphology_context=morphology_context,
        selected_readout_id=selected_readout_id,
    )
    raw_validation_context = _resolve_validation_context(resolved_validation_bundle)
    analysis_context = build_dashboard_analysis_context(
        analysis_context=raw_analysis_context,
        validation_context=raw_validation_context,
        contract_metadata=normalized_contract,
    )

    selected_arm_pair = build_dashboard_selected_arm_pair_reference(
        baseline_arm_id=arm_pair["baseline_arm_id"],
        wave_arm_id=arm_pair["wave_arm_id"],
        active_arm_id=(
            wave_item["arm_id"]
            if active_arm_id is None
            else _normalize_identifier(active_arm_id, field_name="active_arm_id")
        ),
    )
    global_interaction_state = build_dashboard_global_interaction_state(
        selected_arm_pair=selected_arm_pair,
        selected_neuron_id=morphology_context["selected_neuron_id"],
        selected_readout_id=time_series_context["selected_readout_id"],
        active_overlay_id=active_overlay_id,
        comparison_mode=comparison_mode,
        time_cursor=build_dashboard_time_cursor(),
    )
    external_artifact_references = _build_external_artifact_references(
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
        analysis_bundle=resolved_analysis_bundle,
        validation_bundle=resolved_validation_bundle,
        whole_brain_context_bundle=explicit_whole_brain_context,
    )
    overlay_resolution = _resolve_overlay_catalog(
        contract_metadata=normalized_contract,
        global_interaction_state=global_interaction_state,
        artifact_references=external_artifact_references,
        scene_context=scene_context,
        time_series_context=time_series_context,
        analysis_context=raw_analysis_context,
        validation_context=raw_validation_context,
    )
    if overlay_resolution["active_overlay_unavailable_reason"] is not None:
        raise ValueError(
            "Requested dashboard active_overlay_id "
            f"{global_interaction_state['active_overlay_id']!r} is unavailable: "
            f"{overlay_resolution['active_overlay_unavailable_reason']}."
        )

    dashboard_session = build_dashboard_session_metadata(
        manifest_reference=_resolved_manifest_reference(
            simulation_plan=simulation_plan,
            baseline_metadata=baseline_metadata,
            analysis_bundle=resolved_analysis_bundle,
        ),
        global_interaction_state=global_interaction_state,
        artifact_references=external_artifact_references,
        processed_simulator_results_dir=processed_dir,
        enabled_export_target_ids=enabled_export_target_ids,
        default_export_target_id=default_export_target_id,
        ui_delivery_model=ui_delivery_model,
        session_payload_status=ASSET_STATUS_READY,
        session_state_status=ASSET_STATUS_READY,
        app_shell_status=ASSET_STATUS_READY,
        contract_metadata=normalized_contract,
    )
    dashboard_payload = _build_dashboard_session_payload(
        dashboard_session=dashboard_session,
        selection_context=selection_context,
        selected_bundle_pair={
            "baseline": _bundle_payload_summary(baseline_item, baseline_metadata),
            "wave": _bundle_payload_summary(wave_item, wave_metadata),
            "shared_seed": int(baseline_item["seed"]),
            "condition_ids": list(baseline_item["condition_ids"]),
            "condition_signature": str(baseline_item["condition_signature"]),
        },
        scene_context=scene_context,
        circuit_context=circuit_context,
        morphology_context=morphology_context,
        time_series_context=time_series_context,
        analysis_context=analysis_context,
        overlay_resolution=overlay_resolution,
        inventory=inventory,
    )
    dashboard_state = _build_dashboard_session_state(
        dashboard_session=dashboard_session,
        time_series_context=time_series_context,
    )
    output_locations = _build_output_locations(dashboard_session)
    return {
        "plan_version": DASHBOARD_SESSION_PLAN_VERSION,
        "source_mode": source_mode,
        "manifest_reference": copy.deepcopy(dict(dashboard_session["manifest_reference"])),
        "config_reference": {
            "config_path": str(Path(config_file).resolve()),
            "project_root": str(Path(project_root).resolve()),
        },
        "selection": selection_context,
        "selected_bundle_pair": copy.deepcopy(
            dashboard_payload["selected_bundle_pair"]
        ),
        "pane_inputs": copy.deepcopy(dashboard_payload["pane_inputs"]),
        "overlay_catalog": copy.deepcopy(overlay_resolution),
        "enabled_export_target_ids": list(dashboard_session["enabled_export_target_ids"]),
        "default_export_target_id": str(dashboard_session["default_export_target_id"]),
        "dashboard_session": dashboard_session,
        "dashboard_session_payload": dashboard_payload,
        "dashboard_session_state": dashboard_state,
        "output_locations": output_locations,
    }


def package_dashboard_session(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != DASHBOARD_SESSION_PLAN_VERSION:
        raise ValueError(
            f"plan.plan_version must be {DASHBOARD_SESSION_PLAN_VERSION!r}."
        )
    dashboard_session = _require_mapping(
        normalized_plan.get("dashboard_session"),
        field_name="plan.dashboard_session",
    )
    dashboard_payload = _require_mapping(
        normalized_plan.get("dashboard_session_payload"),
        field_name="plan.dashboard_session_payload",
    )
    dashboard_state = _require_mapping(
        normalized_plan.get("dashboard_session_state"),
        field_name="plan.dashboard_session_state",
    )

    metadata_path = write_dashboard_session_metadata(dashboard_session)
    bundle_paths = discover_dashboard_session_bundle_paths(dashboard_session)
    write_json(dashboard_payload, bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID])
    write_json(dashboard_state, bundle_paths[SESSION_STATE_ARTIFACT_ID])
    app_shell_result = build_dashboard_app_shell(
        metadata=dashboard_session,
        payload=dashboard_payload,
        session_state=dashboard_state,
        app_shell_path=bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID],
    )
    return {
        "bundle_id": str(dashboard_session["bundle_id"]),
        "metadata_path": str(metadata_path.resolve()),
        "session_payload_path": str(bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID].resolve()),
        "session_state_path": str(bundle_paths[SESSION_STATE_ARTIFACT_ID].resolve()),
        "app_shell_path": str(bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID].resolve()),
        "bundle_directory": str(
            Path(dashboard_session["bundle_layout"]["bundle_directory"]).resolve()
        ),
        "asset_manifest_path": str(Path(app_shell_result["asset_manifest_path"]).resolve()),
        "style_asset_path": str(Path(app_shell_result["style_asset_path"]).resolve()),
        "script_asset_path": str(Path(app_shell_result["script_asset_path"]).resolve()),
        "app_shell_file_url": str(app_shell_result["app_shell_file_url"]),
        "bootstrap_hash": str(app_shell_result["bootstrap_hash"]),
    }


def _resolve_source_mode(
    *,
    manifest_path: str | Path | None,
    experiment_id: str | None,
    explicit_baseline: Mapping[str, Any] | None,
    explicit_wave: Mapping[str, Any] | None,
    explicit_analysis: Mapping[str, Any] | None,
    explicit_validation: Mapping[str, Any] | None,
) -> str:
    if manifest_path is not None:
        return DASHBOARD_SESSION_SOURCE_MODE_MANIFEST
    if any(
        item is not None
        for item in (explicit_baseline, explicit_wave, explicit_analysis, explicit_validation)
    ):
        return DASHBOARD_SESSION_SOURCE_MODE_EXPLICIT
    if experiment_id is not None:
        return DASHBOARD_SESSION_SOURCE_MODE_EXPERIMENT
    raise ValueError(
        "Dashboard session planning requires one of manifest_path, experiment_id, or "
        "explicit baseline/wave/analysis/validation bundle metadata inputs."
    )


def _resolve_experiment_id(
    *,
    manifest_path: str | Path | None,
    experiment_id: str | None,
    explicit_baseline: Mapping[str, Any] | None,
    explicit_wave: Mapping[str, Any] | None,
    explicit_analysis: Mapping[str, Any] | None,
    explicit_validation: Mapping[str, Any] | None,
) -> str:
    candidates: set[str] = set()
    if experiment_id is not None:
        candidates.add(_normalize_identifier(experiment_id, field_name="experiment_id"))
    for metadata in (explicit_baseline, explicit_wave):
        if metadata is None:
            continue
        candidates.add(str(metadata["manifest_reference"]["experiment_id"]))
    if explicit_analysis is not None:
        candidates.add(str(explicit_analysis["experiment_id"]))
    if explicit_validation is not None:
        candidates.add(str(explicit_validation["experiment_id"]))
    if manifest_path is not None and experiment_id is None and not candidates:
        return ""
    if len(candidates) > 1:
        raise ValueError(
            "Dashboard session planning received conflicting experiment identifiers "
            f"{sorted(candidates)!r}."
        )
    return next(iter(candidates), "")


def _resolve_optional_simulator_bundle(
    *,
    bundle_metadata: Mapping[str, Any] | None,
    bundle_metadata_path: str | Path | None,
    field_name: str,
) -> dict[str, Any] | None:
    if bundle_metadata is not None:
        return parse_simulator_result_bundle_metadata(bundle_metadata)
    if bundle_metadata_path is not None:
        return load_simulator_result_bundle_metadata(bundle_metadata_path)
    return None


def _resolve_optional_analysis_bundle(
    *,
    bundle_metadata: Mapping[str, Any] | None,
    bundle_metadata_path: str | Path | None,
    field_name: str,
) -> dict[str, Any] | None:
    del field_name
    if bundle_metadata is not None:
        return parse_experiment_analysis_bundle_metadata(bundle_metadata)
    if bundle_metadata_path is not None:
        return load_experiment_analysis_bundle_metadata(bundle_metadata_path)
    return None


def _resolve_optional_validation_bundle(
    *,
    bundle_metadata: Mapping[str, Any] | None,
    bundle_metadata_path: str | Path | None,
    field_name: str,
) -> dict[str, Any] | None:
    del field_name
    if bundle_metadata is not None:
        return parse_validation_bundle_metadata(bundle_metadata)
    if bundle_metadata_path is not None:
        return load_validation_bundle_metadata(bundle_metadata_path)
    return None


def _resolve_optional_whole_brain_context_bundle(
    *,
    bundle_metadata: Mapping[str, Any] | None,
    bundle_metadata_path: str | Path | None,
    field_name: str,
) -> dict[str, Any] | None:
    del field_name
    if bundle_metadata is not None:
        return parse_whole_brain_context_session_metadata(bundle_metadata)
    if bundle_metadata_path is not None:
        return load_whole_brain_context_session_metadata(bundle_metadata_path)
    return None


def _resolve_analysis_bundle(
    *,
    explicit_analysis: Mapping[str, Any] | None,
    experiment_id: str,
    processed_simulator_results_dir: Path,
    manifest_path: str | Path | None,
) -> dict[str, Any]:
    if explicit_analysis is not None:
        return copy.deepcopy(dict(explicit_analysis))
    if not experiment_id:
        raise ValueError(
            "Dashboard session planning requires experiment_id when analysis_bundle metadata "
            "is not provided explicitly."
        )
    analysis_root = (
        processed_simulator_results_dir
        / DEFAULT_ANALYSIS_DIRECTORY_NAME
        / experiment_id
    ).resolve()
    candidate_paths = sorted(analysis_root.glob("*/experiment_analysis_bundle.json"))
    if not candidate_paths:
        raise ValueError(
            f"Dashboard session planning requires a local experiment_analysis_bundle for "
            f"experiment_id {experiment_id!r} under {analysis_root}."
        )
    candidates = [
        load_experiment_analysis_bundle_metadata(path)
        for path in candidate_paths
    ]
    if manifest_path is not None:
        requested_manifest_path = str(Path(manifest_path).resolve())
        candidates = [
            metadata
            for metadata in candidates
            if str(metadata["manifest_reference"]["manifest_path"]) == requested_manifest_path
        ]
    if not candidates:
        raise ValueError(
            "Dashboard session planning could not find an experiment_analysis_bundle that "
            f"matches manifest_path {Path(manifest_path).resolve()}."
        )
    if len(candidates) > 1:
        raise ValueError(
            "Experiment-driven dashboard planning found multiple local experiment_analysis_bundle "
            f"candidates for experiment_id {experiment_id!r}. Pass analysis_bundle_metadata_path "
            "or manifest_path explicitly to disambiguate."
        )
    return candidates[0]


def _resolve_validation_bundle(
    *,
    explicit_validation: Mapping[str, Any] | None,
    experiment_id: str,
    processed_simulator_results_dir: Path,
    analysis_bundle: Mapping[str, Any],
    selected_arm_ids: tuple[str | None, str | None],
) -> dict[str, Any]:
    if explicit_validation is not None:
        return copy.deepcopy(dict(explicit_validation))
    if not experiment_id:
        raise ValueError(
            "Dashboard session planning requires experiment_id when validation_bundle metadata "
            "is not provided explicitly."
        )
    validation_root = (
        processed_simulator_results_dir
        / DEFAULT_VALIDATION_DIRECTORY_NAME
        / experiment_id
    ).resolve()
    candidate_paths = sorted(validation_root.glob("*/validation_bundle.json"))
    if not candidate_paths:
        raise ValueError(
            f"Dashboard session planning requires a local validation_bundle for experiment_id "
            f"{experiment_id!r} under {validation_root}."
        )
    candidates = [
        load_validation_bundle_metadata(path)
        for path in candidate_paths
    ]
    filtered: list[dict[str, Any]] = []
    expected_analysis_bundle_id = str(analysis_bundle["bundle_id"])
    for metadata in candidates:
        evidence_refs = metadata["validation_plan_reference"].get("evidence_bundle_references", {})
        analysis_ref = evidence_refs.get("experiment_analysis_bundle")
        if isinstance(analysis_ref, Mapping) and str(analysis_ref.get("bundle_id", "")) not in {
            "",
            expected_analysis_bundle_id,
        }:
            continue
        target_arm_ids = {
            str(arm_id)
            for arm_id in metadata["validation_plan_reference"].get("target_arm_ids", [])
        }
        baseline_arm_id, wave_arm_id = selected_arm_ids
        if target_arm_ids and (
            (baseline_arm_id is not None and baseline_arm_id not in target_arm_ids)
            or (wave_arm_id is not None and wave_arm_id not in target_arm_ids)
        ):
            continue
        filtered.append(metadata)
    if not filtered:
        raise ValueError(
            "Dashboard session planning could not find a validation_bundle aligned with "
            f"analysis bundle {expected_analysis_bundle_id!r}."
        )
    if len(filtered) > 1:
        raise ValueError(
            "Experiment-driven dashboard planning found multiple validation_bundle candidates "
            f"for experiment_id {experiment_id!r}. Pass validation_bundle_metadata_path "
            "explicitly to disambiguate."
        )
    return filtered[0]


def _ensure_processed_dir_alignment(
    *,
    processed_dir: Path,
    experiment_id: str,
    analysis_bundle: Mapping[str, Any],
    validation_bundle: Mapping[str, Any] | None,
    baseline_bundle: Mapping[str, Any] | None,
    wave_bundle: Mapping[str, Any] | None,
) -> None:
    analysis_dir = Path(
        analysis_bundle["bundle_set_reference"]["processed_simulator_results_dir"]
    ).resolve()
    if analysis_dir != processed_dir:
        raise ValueError(
            "analysis_bundle processed_simulator_results_dir does not match the active config: "
            f"{analysis_dir} != {processed_dir}."
        )
    if validation_bundle is not None:
        validation_dir = Path(
            validation_bundle["output_root_reference"]["processed_simulator_results_dir"]
        ).resolve()
        if validation_dir != processed_dir:
            raise ValueError(
                "validation_bundle processed_simulator_results_dir does not match the active config: "
                f"{validation_dir} != {processed_dir}."
            )
    for label, metadata in (("baseline", baseline_bundle), ("wave", wave_bundle)):
        if metadata is None:
            continue
        metadata_path = Path(metadata["artifacts"][METADATA_JSON_KEY]["path"]).resolve()
        if processed_dir not in metadata_path.parents:
            raise ValueError(
                f"Explicit {label} simulator bundle {metadata_path} does not live under the "
                f"configured processed_simulator_results_dir {processed_dir} for experiment "
                f"{experiment_id!r}."
            )


def _bundle_inventory_from_context(
    *,
    bundle_set: Mapping[str, Any] | None,
    analysis_bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if bundle_set is not None:
        inventory = [copy.deepcopy(dict(item)) for item in bundle_set["bundle_inventory"]]
    else:
        inventory = [
            copy.deepcopy(dict(item))
            for item in analysis_bundle["bundle_set_reference"]["bundle_inventory"]
        ]
    inventory.sort(
        key=lambda item: (
            str(item["arm_id"]),
            int(item["seed"]),
            str(item["condition_signature"]),
            str(item["bundle_id"]),
        )
    )
    return inventory


def _selected_arm_ids_from_overrides(
    *,
    explicit_baseline: Mapping[str, Any] | None,
    explicit_wave: Mapping[str, Any] | None,
    baseline_arm_id: str | None,
    wave_arm_id: str | None,
) -> tuple[str | None, str | None]:
    resolved_baseline = (
        str(explicit_baseline["arm_reference"]["arm_id"])
        if explicit_baseline is not None
        else (
            None
            if baseline_arm_id is None
            else _normalize_identifier(baseline_arm_id, field_name="baseline_arm_id")
        )
    )
    resolved_wave = (
        str(explicit_wave["arm_reference"]["arm_id"])
        if explicit_wave is not None
        else (
            None
            if wave_arm_id is None
            else _normalize_identifier(wave_arm_id, field_name="wave_arm_id")
        )
    )
    return resolved_baseline, resolved_wave


def _resolve_arm_pair(
    *,
    explicit_baseline: Mapping[str, Any] | None,
    explicit_wave: Mapping[str, Any] | None,
    inventory: Sequence[Mapping[str, Any]],
    simulation_plan: Mapping[str, Any] | None,
    baseline_arm_id: str | None,
    wave_arm_id: str | None,
) -> dict[str, str]:
    if explicit_baseline is not None and str(explicit_baseline["arm_reference"]["model_mode"]) != BASELINE_MODEL_MODE:
        raise ValueError("Explicit baseline_bundle_metadata must use model_mode 'baseline'.")
    if explicit_wave is not None and str(explicit_wave["arm_reference"]["model_mode"]) != SURFACE_WAVE_MODEL_MODE:
        raise ValueError("Explicit wave_bundle_metadata must use model_mode 'surface_wave'.")
    resolved_baseline_arm_id, resolved_wave_arm_id = _selected_arm_ids_from_overrides(
        explicit_baseline=explicit_baseline,
        explicit_wave=explicit_wave,
        baseline_arm_id=baseline_arm_id,
        wave_arm_id=wave_arm_id,
    )
    if resolved_baseline_arm_id is None or resolved_wave_arm_id is None:
        if simulation_plan is not None:
            arm_pair_catalog = simulation_plan["readout_analysis_plan"].get("arm_pair_catalog", [])
            if arm_pair_catalog:
                default_pair = sorted(
                    (dict(item) for item in arm_pair_catalog),
                    key=lambda item: (
                        str(item["baseline_family"]),
                        str(item["topology_condition"]),
                        str(item["group_id"]),
                    ),
                )[0]
                resolved_baseline_arm_id = str(default_pair["baseline_arm_id"])
                resolved_wave_arm_id = str(default_pair["surface_wave_arm_id"])
        if resolved_baseline_arm_id is None or resolved_wave_arm_id is None:
            ordered_arm_ids = []
            for item in inventory:
                arm_id = str(item["arm_id"])
                if arm_id not in ordered_arm_ids:
                    ordered_arm_ids.append(arm_id)
            baseline_candidates = [
                arm_id
                for arm_id in ordered_arm_ids
                if any(
                    str(item["arm_id"]) == arm_id and str(item["model_mode"]) == BASELINE_MODEL_MODE
                    for item in inventory
                )
            ]
            wave_candidates = [
                arm_id
                for arm_id in ordered_arm_ids
                if any(
                    str(item["arm_id"]) == arm_id and str(item["model_mode"]) == SURFACE_WAVE_MODEL_MODE
                    for item in inventory
                )
            ]
            if not baseline_candidates or not wave_candidates:
                raise ValueError(
                    "Dashboard session planning requires at least one baseline arm and one "
                    "surface_wave arm in the local bundle inventory."
                )
            resolved_baseline_arm_id = baseline_candidates[0]
            resolved_wave_arm_id = wave_candidates[0]
    if resolved_baseline_arm_id == resolved_wave_arm_id:
        raise ValueError("baseline_arm_id and wave_arm_id must differ.")
    return {
        "baseline_arm_id": resolved_baseline_arm_id,
        "wave_arm_id": resolved_wave_arm_id,
    }


def _select_inventory_item(
    *,
    inventory: Sequence[Mapping[str, Any]],
    arm_id: str,
    explicit_bundle: Mapping[str, Any] | None,
    simulation_plan: Mapping[str, Any] | None,
    preferred_seed: int | str | None,
    preferred_condition_ids: Sequence[str] | None,
) -> dict[str, Any]:
    candidates = [
        copy.deepcopy(dict(item))
        for item in inventory
        if str(item["arm_id"]) == str(arm_id)
    ]
    if not candidates:
        raise ValueError(f"Bundle inventory does not contain arm_id {arm_id!r}.")
    if explicit_bundle is not None:
        explicit_bundle_id = str(explicit_bundle["bundle_id"])
        matches = [item for item in candidates if str(item["bundle_id"]) == explicit_bundle_id]
        if len(matches) != 1:
            raise ValueError(
                f"Explicit simulator bundle {explicit_bundle_id!r} is not present in the "
                "selected experiment_analysis_bundle coverage."
            )
        matches[0]["metadata"] = copy.deepcopy(dict(explicit_bundle))
        return matches[0]

    normalized_condition_ids = None
    if preferred_condition_ids is not None:
        normalized_condition_ids = sorted(
            _normalize_identifier(value, field_name="preferred_condition_ids")
            for value in preferred_condition_ids
        )
    if preferred_seed is not None or normalized_condition_ids is not None:
        matches = []
        for item in candidates:
            if preferred_seed is not None and int(item["seed"]) != int(preferred_seed):
                continue
            if normalized_condition_ids is not None and list(item["condition_ids"]) != normalized_condition_ids:
                continue
            matches.append(item)
        if len(matches) != 1:
            raise ValueError(
                f"Dashboard session planning could not resolve one bundle for arm_id {arm_id!r} "
                f"with preferred_seed={preferred_seed!r} and "
                f"preferred_condition_ids={normalized_condition_ids!r}."
            )
        return matches[0]

    if simulation_plan is not None:
        matching_arm_plans = [
            dict(item)
            for item in simulation_plan["arm_plans"]
            if str(item["arm_reference"]["arm_id"]) == str(arm_id)
        ]
        if matching_arm_plans:
            expected_bundle_id = str(
                matching_arm_plans[0]["result_bundle"]["reference"]["bundle_id"]
            )
            matches = [item for item in candidates if str(item["bundle_id"]) == expected_bundle_id]
            if len(matches) == 1:
                return matches[0]
            raise ValueError(
                f"Dashboard session planning expected the canonical manifest-selected bundle "
                f"{expected_bundle_id!r} for arm_id {arm_id!r}, but it was not found in the "
                "local experiment bundle inventory. Pass preferred_seed and "
                "preferred_condition_ids or explicit bundle metadata to disambiguate."
            )

    if len(candidates) == 1:
        return candidates[0]
    raise ValueError(
        f"Dashboard session planning found multiple bundles for arm_id {arm_id!r} and cannot "
        "choose a scientifically safe default without manifest-derived run identity. Pass "
        "manifest_path or explicit preferred_seed and preferred_condition_ids."
    )


def _inventory_item_metadata(item: Mapping[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping):
        return parse_simulator_result_bundle_metadata(metadata)
    return load_simulator_result_bundle_metadata(item["metadata_path"])


def _validate_bundle_pair(
    *,
    baseline_item: Mapping[str, Any],
    wave_item: Mapping[str, Any],
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
) -> None:
    if int(baseline_item["seed"]) != int(wave_item["seed"]):
        raise ValueError(
            "Dashboard paired baseline and wave bundles must use the same seed for a fair "
            f"comparison, got {baseline_item['seed']!r} and {wave_item['seed']!r}."
        )
    if list(baseline_item["condition_ids"]) != list(wave_item["condition_ids"]):
        raise ValueError(
            "Dashboard paired baseline and wave bundles must resolve the same stimulus "
            f"condition_ids, got {baseline_item['condition_ids']!r} and "
            f"{wave_item['condition_ids']!r}."
        )
    if dict(baseline_metadata["timebase"]) != dict(wave_metadata["timebase"]):
        raise ValueError(
            "Dashboard planning requires baseline and wave bundles to share one canonical "
            f"timebase, got {baseline_metadata['timebase']!r} and {wave_metadata['timebase']!r}."
        )


def _validate_analysis_bundle_alignment(
    *,
    analysis_bundle: Mapping[str, Any],
    baseline_bundle_id: str,
    wave_bundle_id: str,
    baseline_arm_id: str,
    wave_arm_id: str,
) -> None:
    inventory_ids = {
        str(item["bundle_id"])
        for item in analysis_bundle["bundle_set_reference"]["bundle_inventory"]
    }
    missing = sorted(
        {baseline_bundle_id, wave_bundle_id} - inventory_ids
    )
    if missing:
        raise ValueError(
            "analysis_bundle does not correspond to the selected simulator runs; missing "
            f"bundle_ids {missing!r} from its bundle_set coverage."
        )
    covered_arm_ids = set(analysis_bundle["bundle_set_reference"]["expected_arm_ids"])
    if baseline_arm_id not in covered_arm_ids or wave_arm_id not in covered_arm_ids:
        raise ValueError(
            "analysis_bundle expected_arm_ids do not cover the selected dashboard arm pair "
            f"{baseline_arm_id!r}, {wave_arm_id!r}."
        )


def _validate_validation_bundle_alignment(
    *,
    validation_bundle: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
    baseline_bundle_id: str,
    wave_bundle_id: str,
    baseline_arm_id: str,
    wave_arm_id: str,
) -> None:
    plan_ref = validation_bundle["validation_plan_reference"]
    evidence_refs = plan_ref.get("evidence_bundle_references", {})
    analysis_ref = evidence_refs.get("experiment_analysis_bundle")
    if isinstance(analysis_ref, Mapping):
        if str(analysis_ref.get("bundle_id", "")) != str(analysis_bundle["bundle_id"]):
            raise ValueError(
                "validation_bundle does not correspond to the selected analysis_bundle: "
                f"{analysis_ref.get('bundle_id')!r} != {analysis_bundle['bundle_id']!r}."
            )
    bundle_ids = set(
        _require_mapping(
            evidence_refs.get("simulator_result_bundle", {}),
            field_name="validation_plan_reference.evidence_bundle_references.simulator_result_bundle",
        ).get("bundle_ids", [])
    )
    missing_bundle_ids = sorted({baseline_bundle_id, wave_bundle_id} - bundle_ids)
    if missing_bundle_ids:
        raise ValueError(
            "validation_bundle evidence does not cover the selected simulator runs; missing "
            f"bundle_ids {missing_bundle_ids!r}."
        )
    target_arm_ids = set(plan_ref.get("target_arm_ids", []))
    if target_arm_ids and (
        baseline_arm_id not in target_arm_ids or wave_arm_id not in target_arm_ids
    ):
        raise ValueError(
            "validation_bundle target_arm_ids do not cover the selected dashboard arm pair "
            f"{baseline_arm_id!r}, {wave_arm_id!r}."
        )


def _resolve_scene_context(
    *,
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
    condition_ids: Sequence[str],
) -> dict[str, Any]:
    baseline_input = _selected_asset_reference(baseline_metadata, asset_role="input_bundle")
    wave_input = _selected_asset_reference(wave_metadata, asset_role="input_bundle")
    if (
        str(baseline_input["artifact_type"]) != str(wave_input["artifact_type"])
        or str(baseline_input["bundle_id"]) != str(wave_input["bundle_id"])
    ):
        raise ValueError(
            "Dashboard paired baseline and wave bundles must share the same input bundle, got "
            f"{baseline_input['bundle_id']!r} and {wave_input['bundle_id']!r}."
        )
    metadata_path = Path(str(baseline_input["path"])).resolve()
    _require_existing_path(metadata_path, field_name="scene.input_bundle_metadata")
    artifact_type = str(baseline_input["artifact_type"])
    if artifact_type not in {"stimulus_bundle", "retinal_bundle"}:
        raise ValueError(
            f"Unsupported dashboard scene input artifact_type {artifact_type!r}."
        )
    return resolve_dashboard_scene_context(
        source_kind=artifact_type,
        metadata_path=metadata_path,
        selected_condition_ids=condition_ids,
    )


def _resolve_selection_context(
    *,
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    baseline_roster = _selected_asset_reference(baseline_metadata, asset_role="selected_root_ids")
    wave_roster = _selected_asset_reference(wave_metadata, asset_role="selected_root_ids")
    baseline_roster_path = Path(str(baseline_roster["path"])).resolve()
    wave_roster_path = Path(str(wave_roster["path"])).resolve()
    if baseline_roster_path != wave_roster_path:
        raise ValueError(
            "Dashboard paired bundles must share one selected-root roster, got "
            f"{baseline_roster_path} and {wave_roster_path}."
        )
    _require_existing_path(baseline_roster_path, field_name="selected_root_ids_path")
    baseline_geometry = _selected_asset_reference(baseline_metadata, asset_role="geometry_manifest")
    wave_geometry = _selected_asset_reference(wave_metadata, asset_role="geometry_manifest")
    geometry_manifest_path = Path(str(baseline_geometry["path"])).resolve()
    if geometry_manifest_path != Path(str(wave_geometry["path"])).resolve():
        raise ValueError(
            "Dashboard paired bundles must share one geometry_manifest selected asset."
        )
    baseline_coupling = _selected_asset_reference(
        baseline_metadata,
        asset_role="coupling_synapse_registry",
    )
    wave_coupling = _selected_asset_reference(
        wave_metadata,
        asset_role="coupling_synapse_registry",
    )
    local_synapse_registry_path = Path(str(baseline_coupling["path"])).resolve()
    if local_synapse_registry_path != Path(str(wave_coupling["path"])).resolve():
        raise ValueError(
            "Dashboard paired bundles must share one local synapse registry asset."
        )
    selected_root_ids = sorted(read_root_ids(baseline_roster_path))
    return {
        "selected_root_ids_path": str(baseline_roster_path),
        "selected_root_ids": selected_root_ids,
        "selected_root_count": len(selected_root_ids),
        "geometry_manifest_path": str(geometry_manifest_path),
        "local_synapse_registry_path": str(local_synapse_registry_path),
    }


def _resolve_circuit_context(
    *,
    geometry_manifest_path: Path,
    selected_root_ids: Sequence[int],
    local_synapse_registry_path: Path,
) -> dict[str, Any]:
    _require_existing_path(geometry_manifest_path, field_name="geometry_manifest_path")
    _require_existing_path(local_synapse_registry_path, field_name="local_synapse_registry_path")
    return normalize_dashboard_circuit_context(
        geometry_manifest_path=geometry_manifest_path,
        selected_root_ids=selected_root_ids,
        local_synapse_registry_path=local_synapse_registry_path,
    )


def _resolve_whole_brain_context(
    *,
    whole_brain_context_bundle: Mapping[str, Any] | None,
    selected_root_ids: Sequence[int],
) -> dict[str, Any]:
    if whole_brain_context_bundle is None:
        return {
            "context_version": DASHBOARD_WHOLE_BRAIN_CONTEXT_VERSION,
            "availability": "absent",
            "reason": "No packaged whole-brain context session is linked to this dashboard package.",
        }
    bundle_paths = discover_whole_brain_context_session_bundle_paths(
        whole_brain_context_bundle
    )
    return load_dashboard_whole_brain_context(
        metadata_path=bundle_paths[METADATA_JSON_KEY],
        selected_root_ids=selected_root_ids,
    )


def _resolve_morphology_context(
    *,
    circuit_context: Mapping[str, Any],
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    selected_neuron_id: str | int | None,
) -> dict[str, Any]:
    return build_dashboard_morphology_context(
        circuit_context=circuit_context,
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
        analysis_ui_payload=_require_mapping(
            analysis_context.get("analysis_ui_payload"),
            field_name="analysis_context.analysis_ui_payload",
        ),
        selected_neuron_id=selected_neuron_id,
    )


def _resolve_time_series_context(
    *,
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
    morphology_context: Mapping[str, Any],
    selected_readout_id: str | None,
) -> dict[str, Any]:
    return build_dashboard_time_series_context(
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
        morphology_context=morphology_context,
        selected_readout_id=selected_readout_id,
    )


def _resolve_analysis_context(
    analysis_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    paths = discover_experiment_analysis_bundle_paths(analysis_bundle)
    ui_payload_path = paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID].resolve()
    _require_existing_path(ui_payload_path, field_name="analysis_bundle.analysis_ui_payload")
    ui_payload = _load_json_mapping(
        ui_payload_path,
        field_name="analysis_bundle.analysis_ui_payload",
    )
    comparison_summary_path = paths[EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID].resolve()
    visualization_catalog_path = paths[VISUALIZATION_CATALOG_ARTIFACT_ID].resolve()
    comparison_matrices_path = paths[COMPARISON_MATRICES_ARTIFACT_ID].resolve()
    offline_report_path = paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID].resolve()
    comparison_summary = (
        {}
        if not comparison_summary_path.exists()
        else _load_json_mapping(
            comparison_summary_path,
            field_name="analysis_bundle.experiment_comparison_summary",
        )
    )
    visualization_catalog = (
        {"phase_map_references": []}
        if not visualization_catalog_path.exists()
        else _load_json_mapping(
            visualization_catalog_path,
            field_name="analysis_bundle.visualization_catalog",
        )
    )
    comparison_matrices = (
        {"matrices": []}
        if not comparison_matrices_path.exists()
        else _load_json_mapping(
            comparison_matrices_path,
            field_name="analysis_bundle.comparison_matrices",
        )
    )
    return {
        "pane_id": ANALYSIS_PANE_ID,
        "bundle_id": str(analysis_bundle["bundle_id"]),
        "metadata_path": str(paths[METADATA_JSON_KEY].resolve()),
        "analysis_ui_payload_path": str(ui_payload_path),
        "comparison_summary_path": str(comparison_summary_path),
        "comparison_summary_exists": comparison_summary_path.exists(),
        "visualization_catalog_path": str(visualization_catalog_path),
        "visualization_catalog_exists": visualization_catalog_path.exists(),
        "comparison_matrices_path": str(comparison_matrices_path),
        "comparison_matrices_exists": comparison_matrices_path.exists(),
        "offline_report_path": str(offline_report_path),
        "offline_report_exists": offline_report_path.exists(),
        "analysis_ui_payload": ui_payload,
        "comparison_summary": comparison_summary,
        "visualization_catalog": visualization_catalog,
        "comparison_matrices": comparison_matrices,
        "phase_map_reference_count": len(
            _require_mapping(
                ui_payload.get("wave_only_diagnostics", {}),
                field_name="analysis_ui_payload.wave_only_diagnostics",
            ).get("phase_map_references", [])
        ),
        "wave_diagnostic_card_count": len(
            _require_mapping(
                ui_payload.get("wave_only_diagnostics", {}),
                field_name="analysis_ui_payload.wave_only_diagnostics",
            ).get("diagnostic_cards", [])
        ),
    }


def _resolve_validation_context(
    validation_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    paths = discover_validation_bundle_paths(validation_bundle)
    summary_path = paths[VALIDATION_SUMMARY_ARTIFACT_ID].resolve()
    findings_path = paths[VALIDATOR_FINDINGS_ARTIFACT_ID].resolve()
    review_handoff_path = paths[REVIEW_HANDOFF_ARTIFACT_ID].resolve()
    _require_existing_path(summary_path, field_name="validation_bundle.validation_summary")
    _require_existing_path(findings_path, field_name="validation_bundle.validator_findings")
    _require_existing_path(review_handoff_path, field_name="validation_bundle.review_handoff")
    summary_payload = _load_json_mapping(
        summary_path,
        field_name="validation_bundle.validation_summary",
    )
    findings_payload = _load_json_mapping(
        findings_path,
        field_name="validation_bundle.validator_findings",
    )
    review_handoff_payload = _load_json_mapping(
        review_handoff_path,
        field_name="validation_bundle.review_handoff",
    )
    offline_report_path = paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID].resolve()
    return {
        "bundle_id": str(validation_bundle["bundle_id"]),
        "metadata_path": str(paths[METADATA_JSON_KEY].resolve()),
        "summary_path": str(summary_path),
        "findings_path": str(findings_path),
        "review_handoff_path": str(review_handoff_path),
        "offline_report_path": str(offline_report_path),
        "offline_report_exists": offline_report_path.exists(),
        "summary": summary_payload,
        "findings": findings_payload,
        "review_handoff": review_handoff_payload,
    }


def _build_external_artifact_references(
    *,
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
    validation_bundle: Mapping[str, Any],
    whole_brain_context_bundle: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    baseline_paths = discover_simulator_result_bundle_paths(baseline_metadata)
    wave_paths = discover_simulator_result_bundle_paths(wave_metadata)
    analysis_paths = discover_experiment_analysis_bundle_paths(analysis_bundle)
    validation_paths = discover_validation_bundle_paths(validation_bundle)
    references = [
        build_dashboard_session_artifact_reference(
            artifact_role_id=BASELINE_BUNDLE_METADATA_ROLE_ID,
            source_kind="simulator_result_bundle",
            path=baseline_paths[METADATA_JSON_KEY],
            contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            bundle_id=str(baseline_metadata["bundle_id"]),
            artifact_id=METADATA_JSON_KEY,
            format=str(baseline_metadata["artifacts"][METADATA_JSON_KEY]["format"]),
            artifact_scope=str(
                baseline_metadata["artifacts"][METADATA_JSON_KEY]["artifact_scope"]
            ),
            status=str(baseline_metadata["artifacts"][METADATA_JSON_KEY]["status"]),
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=WAVE_BUNDLE_METADATA_ROLE_ID,
            source_kind="simulator_result_bundle",
            path=wave_paths[METADATA_JSON_KEY],
            contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            bundle_id=str(wave_metadata["bundle_id"]),
            artifact_id=METADATA_JSON_KEY,
            format=str(wave_metadata["artifacts"][METADATA_JSON_KEY]["format"]),
            artifact_scope=str(wave_metadata["artifacts"][METADATA_JSON_KEY]["artifact_scope"]),
            status=str(wave_metadata["artifacts"][METADATA_JSON_KEY]["status"]),
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=ANALYSIS_BUNDLE_METADATA_ROLE_ID,
            source_kind="experiment_analysis_bundle",
            path=analysis_paths[METADATA_JSON_KEY],
            contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
            bundle_id=str(analysis_bundle["bundle_id"]),
            artifact_id=METADATA_JSON_KEY,
            format=str(analysis_bundle["artifacts"][METADATA_JSON_KEY]["format"]),
            artifact_scope=str(analysis_bundle["artifacts"][METADATA_JSON_KEY]["artifact_scope"]),
            status=str(analysis_bundle["artifacts"][METADATA_JSON_KEY]["status"]),
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
            source_kind="experiment_analysis_bundle",
            path=analysis_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID],
            contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
            bundle_id=str(analysis_bundle["bundle_id"]),
            artifact_id=ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
            format=str(analysis_bundle["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["format"]),
            artifact_scope=str(analysis_bundle["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["artifact_scope"]),
            status=str(analysis_bundle["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["status"]),
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=VALIDATION_BUNDLE_METADATA_ROLE_ID,
            source_kind="validation_bundle",
            path=validation_paths[METADATA_JSON_KEY],
            contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            bundle_id=str(validation_bundle["bundle_id"]),
            artifact_id=METADATA_JSON_KEY,
            format=str(validation_bundle["artifacts"][METADATA_JSON_KEY]["format"]),
            artifact_scope=str(validation_bundle["artifacts"][METADATA_JSON_KEY]["artifact_scope"]),
            status=str(validation_bundle["artifacts"][METADATA_JSON_KEY]["status"]),
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=VALIDATION_SUMMARY_ROLE_ID,
            source_kind="validation_bundle",
            path=validation_paths[VALIDATION_SUMMARY_ARTIFACT_ID],
            contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            bundle_id=str(validation_bundle["bundle_id"]),
            artifact_id=VALIDATION_SUMMARY_ARTIFACT_ID,
            format=str(validation_bundle["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["format"]),
            artifact_scope=str(validation_bundle["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["artifact_scope"]),
            status=str(validation_bundle["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["status"]),
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
            source_kind="validation_bundle",
            path=validation_paths[REVIEW_HANDOFF_ARTIFACT_ID],
            contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            bundle_id=str(validation_bundle["bundle_id"]),
            artifact_id=REVIEW_HANDOFF_ARTIFACT_ID,
            format=str(validation_bundle["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["format"]),
            artifact_scope=str(validation_bundle["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["artifact_scope"]),
            status=str(validation_bundle["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["status"]),
        ),
    ]
    baseline_ui_ref = _optional_simulator_ui_artifact_reference(
        role_id=BASELINE_UI_PAYLOAD_ROLE_ID,
        bundle_metadata=baseline_metadata,
    )
    if baseline_ui_ref is not None:
        references.append(baseline_ui_ref)
    wave_ui_ref = _optional_simulator_ui_artifact_reference(
        role_id=WAVE_UI_PAYLOAD_ROLE_ID,
        bundle_metadata=wave_metadata,
    )
    if wave_ui_ref is not None:
        references.append(wave_ui_ref)
    if Path(analysis_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID]).resolve().exists():
        references.append(
            build_dashboard_session_artifact_reference(
                artifact_role_id=ANALYSIS_OFFLINE_REPORT_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID],
                contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
                bundle_id=str(analysis_bundle["bundle_id"]),
                artifact_id=OFFLINE_REPORT_INDEX_ARTIFACT_ID,
                format=str(analysis_bundle["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["format"]),
                artifact_scope=str(analysis_bundle["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["artifact_scope"]),
                status=str(analysis_bundle["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["status"]),
            )
        )
    if Path(validation_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID]).resolve().exists():
        references.append(
            build_dashboard_session_artifact_reference(
                artifact_role_id=VALIDATION_OFFLINE_REPORT_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_bundle["bundle_id"]),
                artifact_id=OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
                format=str(validation_bundle["artifacts"][OFFLINE_REVIEW_REPORT_ARTIFACT_ID]["format"]),
                artifact_scope=str(validation_bundle["artifacts"][OFFLINE_REVIEW_REPORT_ARTIFACT_ID]["artifact_scope"]),
                status=str(validation_bundle["artifacts"][OFFLINE_REVIEW_REPORT_ARTIFACT_ID]["status"]),
            )
        )
    if whole_brain_context_bundle is not None:
        whole_brain_paths = discover_whole_brain_context_session_bundle_paths(
            whole_brain_context_bundle
        )
        references.extend(
            [
                build_dashboard_session_artifact_reference(
                    artifact_role_id=WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
                    source_kind="whole_brain_context_session_package",
                    path=whole_brain_paths[METADATA_JSON_KEY],
                    contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
                    bundle_id=str(whole_brain_context_bundle["bundle_id"]),
                    artifact_id=METADATA_JSON_KEY,
                    format=str(
                        whole_brain_context_bundle["artifacts"][METADATA_JSON_KEY]["format"]
                    ),
                    artifact_scope=str(
                        whole_brain_context_bundle["artifacts"][METADATA_JSON_KEY]["artifact_scope"]
                    ),
                    status=str(
                        whole_brain_context_bundle["artifacts"][METADATA_JSON_KEY]["status"]
                    ),
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id=WHOLE_BRAIN_CONTEXT_VIEW_PAYLOAD_ROLE_ID,
                    source_kind="whole_brain_context_session_package",
                    path=whole_brain_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID],
                    contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
                    bundle_id=str(whole_brain_context_bundle["bundle_id"]),
                    artifact_id=CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
                    format=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["format"]
                    ),
                    artifact_scope=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["artifact_scope"]
                    ),
                    status=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["status"]
                    ),
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id=WHOLE_BRAIN_CONTEXT_QUERY_CATALOG_ROLE_ID,
                    source_kind="whole_brain_context_session_package",
                    path=whole_brain_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID],
                    contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
                    bundle_id=str(whole_brain_context_bundle["bundle_id"]),
                    artifact_id=CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
                    format=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["format"]
                    ),
                    artifact_scope=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["artifact_scope"]
                    ),
                    status=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["status"]
                    ),
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id=WHOLE_BRAIN_CONTEXT_VIEW_STATE_ROLE_ID,
                    source_kind="whole_brain_context_session_package",
                    path=whole_brain_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID],
                    contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
                    bundle_id=str(whole_brain_context_bundle["bundle_id"]),
                    artifact_id=CONTEXT_VIEW_STATE_ARTIFACT_ID,
                    format=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_VIEW_STATE_ARTIFACT_ID]["format"]
                    ),
                    artifact_scope=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_VIEW_STATE_ARTIFACT_ID]["artifact_scope"]
                    ),
                    status=str(
                        whole_brain_context_bundle["artifacts"][CONTEXT_VIEW_STATE_ARTIFACT_ID]["status"]
                    ),
                ),
            ]
        )
    return references


def _optional_simulator_ui_artifact_reference(
    *,
    role_id: str,
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    for artifact in bundle_metadata["artifacts"].get(MODEL_ARTIFACTS_KEY, []):
        if str(artifact.get("artifact_id")) != "ui_comparison_payload":
            continue
        if str(artifact.get("status")) != ASSET_STATUS_READY:
            return None
        return build_dashboard_session_artifact_reference(
            artifact_role_id=role_id,
            source_kind="simulator_result_bundle",
            path=artifact["path"],
            contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            bundle_id=str(bundle_metadata["bundle_id"]),
            artifact_id=str(artifact["artifact_id"]),
            format=str(artifact.get("format")),
            artifact_scope=str(artifact.get("artifact_scope")),
            status=str(artifact.get("status")),
        )
    return None


def _resolve_overlay_catalog(
    *,
    contract_metadata: Mapping[str, Any],
    global_interaction_state: Mapping[str, Any],
    artifact_references: Sequence[Mapping[str, Any]],
    scene_context: Mapping[str, Any],
    time_series_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
) -> dict[str, Any]:
    available: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    role_ids = {str(item["artifact_role_id"]) for item in artifact_references}
    comparison_mode = str(global_interaction_state["comparison_mode"])
    for overlay in discover_dashboard_overlays(
        contract_metadata,
        comparison_mode=comparison_mode,
    ):
        reason = _overlay_unavailable_reason(
            overlay=overlay,
            role_ids=role_ids,
            scene_context=scene_context,
            time_series_context=time_series_context,
            analysis_context=analysis_context,
            validation_context=validation_context,
        )
        record = {
            "overlay_id": str(overlay["overlay_id"]),
            "overlay_category": str(overlay["overlay_category"]),
            "display_name": str(overlay["display_name"]),
            "supported_pane_ids": list(overlay["supported_pane_ids"]),
            "required_artifact_role_ids": list(overlay["required_artifact_role_ids"]),
            "availability": "available" if reason is None else "unavailable",
            "reason": reason,
        }
        if reason is None:
            available.append(record)
        else:
            unavailable.append(record)
    active_overlay = _normalize_identifier(
        global_interaction_state["active_overlay_id"],
        field_name="global_interaction_state.active_overlay_id",
    )
    active_overlay_ids = {
        str(item["overlay_id"]) for item in available
    } | {
        str(item["overlay_id"]) for item in unavailable
    }
    active_reason = next(
        (item["reason"] for item in unavailable if str(item["overlay_id"]) == active_overlay),
        None,
    )
    if active_overlay not in active_overlay_ids:
        active_reason = (
            "overlay is not supported by the selected comparison_mode "
            f"{global_interaction_state['comparison_mode']!r}"
        )
    return {
        "active_overlay_id": active_overlay,
        "available_overlay_ids": [str(item["overlay_id"]) for item in available],
        "available_overlays": available,
        "unavailable_overlays": unavailable,
        "active_overlay_unavailable_reason": active_reason,
    }


def _overlay_unavailable_reason(
    *,
    overlay: Mapping[str, Any],
    role_ids: set[str],
    scene_context: Mapping[str, Any],
    time_series_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
) -> str | None:
    missing_roles = sorted(set(overlay["required_artifact_role_ids"]) - role_ids)
    if missing_roles:
        return f"missing required artifact roles {missing_roles!r}"
    overlay_id = str(overlay["overlay_id"])
    if overlay_id == SHARED_READOUT_ACTIVITY_OVERLAY_ID:
        if not time_series_context["comparable_readout_catalog"]:
            return "no shared comparable readouts are available"
    if overlay_id == WAVE_PATCH_ACTIVITY_OVERLAY_ID:
        if not (
            analysis_context["wave_diagnostic_card_count"] > 0
            or _analysis_payload_has_phase_or_patch_extension(analysis_context["analysis_ui_payload"])
        ):
            return "requested wave-only diagnostics are absent from the packaged analysis payload"
    if overlay_id == VALIDATION_STATUS_BADGES_OVERLAY_ID:
        if "overall_status" not in validation_context["summary"]:
            return "validation summary is missing overall_status"
    if overlay_id == REVIEWER_FINDINGS_OVERLAY_ID:
        if not validation_context["review_handoff"]:
            return "validation review handoff is empty"
    if overlay_id == STIMULUS_CONTEXT_FRAME_OVERLAY_ID:
        if scene_context["source_kind"] not in {"stimulus_bundle", "retinal_bundle"}:
            return "scene source kind is unsupported"
        if str(scene_context.get("render_status")) != "available":
            return str(
                _require_mapping(
                    scene_context.get("frame_discovery", {}),
                    field_name="scene_context.frame_discovery",
                ).get("unavailable_reason", "scene render layer is unavailable")
            )
    if overlay_id == PAIRED_READOUT_DELTA_OVERLAY_ID:
        if not time_series_context["comparable_readout_catalog"]:
            return "no shared comparable readouts are available"
    if overlay_id == PHASE_MAP_REFERENCE_OVERLAY_ID:
        if int(analysis_context["phase_map_reference_count"]) < 1:
            return "requested wave-only diagnostics are absent from the packaged analysis payload"
    return None


def _analysis_payload_has_phase_or_patch_extension(
    payload: Mapping[str, Any],
) -> bool:
    wave_only = _require_mapping(
        payload.get("wave_only_diagnostics", {}),
        field_name="analysis_ui_payload.wave_only_diagnostics",
    )
    return bool(wave_only.get("phase_map_references")) or bool(
        wave_only.get("diagnostic_cards")
    )


def _build_dashboard_session_payload(
    *,
    dashboard_session: Mapping[str, Any],
    selection_context: Mapping[str, Any],
    selected_bundle_pair: Mapping[str, Any],
    scene_context: Mapping[str, Any],
    circuit_context: Mapping[str, Any],
    morphology_context: Mapping[str, Any],
    time_series_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    overlay_resolution: Mapping[str, Any],
    inventory: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "format_version": DASHBOARD_SESSION_PAYLOAD_VERSION,
        "contract_version": DASHBOARD_SESSION_CONTRACT_VERSION,
        "design_note": DASHBOARD_SESSION_DESIGN_NOTE,
        "plan_version": DASHBOARD_SESSION_PLAN_VERSION,
        "bundle_reference": {
            "bundle_id": str(dashboard_session["bundle_id"]),
            "session_spec_hash": str(dashboard_session["session_spec_hash"]),
            "bundle_directory": str(
                dashboard_session["bundle_layout"]["bundle_directory"]
            ),
        },
        "manifest_reference": copy.deepcopy(dict(dashboard_session["manifest_reference"])),
        "global_interaction_state": copy.deepcopy(
            dict(dashboard_session["global_interaction_state"])
        ),
        "enabled_export_target_ids": list(dashboard_session["enabled_export_target_ids"]),
        "default_export_target_id": str(dashboard_session["default_export_target_id"]),
        "selection": copy.deepcopy(dict(selection_context)),
        "selected_bundle_pair": copy.deepcopy(dict(selected_bundle_pair)),
        "pane_inputs": {
            SCENE_PANE_ID: copy.deepcopy(dict(scene_context)),
            CIRCUIT_PANE_ID: copy.deepcopy(dict(circuit_context)),
            MORPHOLOGY_PANE_ID: copy.deepcopy(dict(morphology_context)),
            TIME_SERIES_PANE_ID: copy.deepcopy(dict(time_series_context)),
            ANALYSIS_PANE_ID: copy.deepcopy(dict(analysis_context)),
        },
        "overlay_catalog": copy.deepcopy(dict(overlay_resolution)),
        "simulator_bundle_inventory": [
            {
                "bundle_id": str(item["bundle_id"]),
                "metadata_path": str(Path(item["metadata_path"]).resolve()),
                "arm_id": str(item["arm_id"]),
                "model_mode": str(item["model_mode"]),
                "baseline_family": item.get("baseline_family"),
                "seed": int(item["seed"]),
                "condition_ids": list(item["condition_ids"]),
                "condition_signature": str(item["condition_signature"]),
            }
            for item in inventory
        ],
        "artifact_inventory": [
            copy.deepcopy(dict(item))
            for item in dashboard_session["artifact_references"]
        ],
    }


def _build_dashboard_session_state(
    *,
    dashboard_session: Mapping[str, Any],
    time_series_context: Mapping[str, Any],
) -> dict[str, Any]:
    replay_model = _require_mapping(
        time_series_context.get("replay_model"),
        field_name="time_series_context.replay_model",
    )
    replay_state = build_dashboard_replay_state(
        global_interaction_state=_require_mapping(
            dashboard_session.get("global_interaction_state"),
            field_name="dashboard_session.global_interaction_state",
        ),
        replay_model=replay_model,
    )
    return {
        "format_version": DASHBOARD_SESSION_STATE_VERSION,
        "bundle_reference": {
            "bundle_id": str(dashboard_session["bundle_id"]),
            "session_spec_hash": str(dashboard_session["session_spec_hash"]),
        },
        "manifest_reference": copy.deepcopy(dict(dashboard_session["manifest_reference"])),
        "global_interaction_state": copy.deepcopy(
            dict(dashboard_session["global_interaction_state"])
        ),
        "replay_state": replay_state,
        "enabled_export_target_ids": list(dashboard_session["enabled_export_target_ids"]),
        "default_export_target_id": str(dashboard_session["default_export_target_id"]),
    }


def _build_output_locations(dashboard_session: Mapping[str, Any]) -> dict[str, Any]:
    bundle_paths = discover_dashboard_session_bundle_paths(dashboard_session)
    return {
        "bundle_directory": str(
            Path(dashboard_session["bundle_layout"]["bundle_directory"]).resolve()
        ),
        "app_directory": str(
            Path(dashboard_session["bundle_layout"]["app_directory"]).resolve()
        ),
        "metadata_path": str(bundle_paths[METADATA_JSON_KEY].resolve()),
        "session_payload_path": str(bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID].resolve()),
        "session_state_path": str(bundle_paths[SESSION_STATE_ARTIFACT_ID].resolve()),
        "app_shell_path": str(bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID].resolve()),
    }


def _bundle_payload_summary(
    item: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    extension_artifacts = {
        str(artifact["artifact_id"]): {
            "path": str(Path(artifact["path"]).resolve()),
            "status": str(artifact["status"]),
            "format": str(artifact["format"]),
            "artifact_scope": str(artifact["artifact_scope"]),
        }
        for artifact in metadata["artifacts"].get(MODEL_ARTIFACTS_KEY, [])
    }
    return {
        "bundle_id": str(metadata["bundle_id"]),
        "metadata_path": str(Path(item["metadata_path"]).resolve()),
        "arm_id": str(item["arm_id"]),
        "model_mode": str(item["model_mode"]),
        "baseline_family": item.get("baseline_family"),
        "seed": int(item["seed"]),
        "condition_ids": list(item["condition_ids"]),
        "condition_signature": str(item["condition_signature"]),
        "timebase": copy.deepcopy(dict(metadata["timebase"])),
        "readout_catalog": [
            copy.deepcopy(dict(readout))
            for readout in metadata["readout_catalog"]
        ],
        "extension_artifacts": extension_artifacts,
    }


def _resolved_manifest_reference(
    *,
    simulation_plan: Mapping[str, Any] | None,
    baseline_metadata: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    if simulation_plan is not None:
        return copy.deepcopy(dict(simulation_plan["manifest_reference"]))
    manifest_reference = analysis_bundle.get("manifest_reference")
    if isinstance(manifest_reference, Mapping):
        return copy.deepcopy(dict(manifest_reference))
    return copy.deepcopy(dict(baseline_metadata["manifest_reference"]))


def _selected_asset_reference(
    bundle_metadata: Mapping[str, Any],
    *,
    asset_role: str,
) -> dict[str, Any]:
    matches = [
        copy.deepcopy(dict(item))
        for item in bundle_metadata["selected_assets"]
        if str(item["asset_role"]) == str(asset_role)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"simulator bundle {bundle_metadata['bundle_id']!r} must contain exactly one "
            f"selected asset with asset_role {asset_role!r}."
        )
    return matches[0]


def _comparable_readout_catalog(
    baseline_catalog: Sequence[Mapping[str, Any]],
    wave_catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    wave_by_id = {
        str(item["readout_id"]): dict(item)
        for item in wave_catalog
    }
    comparable: list[dict[str, Any]] = []
    for item in baseline_catalog:
        readout_id = str(item["readout_id"])
        wave_item = wave_by_id.get(readout_id)
        if wave_item is None:
            continue
        if any(
            str(item[field_name]) != str(wave_item[field_name])
            for field_name in ("scope", "aggregation", "units", "value_semantics")
        ):
            raise ValueError(
                f"Dashboard planning found incompatible shared readout definitions for "
                f"readout_id {readout_id!r}."
            )
        comparable.append(copy.deepcopy(dict(item)))
    comparable.sort(key=lambda item: str(item["readout_id"]))
    return comparable


def _path_status_record(record: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(
        _normalize_nonempty_string(record.get("path"), field_name="asset.path")
    ).resolve()
    status = _normalize_nonempty_string(record.get("status"), field_name="asset.status")
    return {
        "path": str(path),
        "status": status,
        "exists": path.exists(),
    }


def _load_json_mapping(path: Path, *, field_name: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping JSON payload.")
    return copy.deepcopy(dict(payload))


def _require_existing_path(path: Path, *, field_name: str) -> None:
    if not path.exists():
        raise ValueError(f"{field_name} is missing at {path}.")


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


__all__ = [
    "DASHBOARD_SESSION_PAYLOAD_VERSION",
    "DASHBOARD_SESSION_PLAN_VERSION",
    "DASHBOARD_SESSION_STATE_VERSION",
    "package_dashboard_session",
    "resolve_dashboard_session_plan",
    "resolve_manifest_dashboard_session_plan",
]
