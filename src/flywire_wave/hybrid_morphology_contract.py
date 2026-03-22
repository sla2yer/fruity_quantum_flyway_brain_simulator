from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .registry import (
    ROLE_POINT_SIMULATED,
    ROLE_SKELETON_SIMULATED,
    ROLE_SURFACE_SIMULATED,
)
from .skeleton_runtime_assets import SKELETON_RUNTIME_ASSET_KEY
from .stimulus_contract import _normalize_identifier, _normalize_nonempty_string


HYBRID_MORPHOLOGY_CONTRACT_VERSION = "hybrid_morphology.v1"
HYBRID_MORPHOLOGY_DESIGN_NOTE = "docs/hybrid_morphology_design.md"
HYBRID_MORPHOLOGY_DESIGN_NOTE_VERSION = "hybrid_morphology_design_note.v1"

SURFACE_NEURON_CLASS = "surface_neuron"
SKELETON_NEURON_CLASS = "skeleton_neuron"
POINT_NEURON_CLASS = "point_neuron"

HYBRID_MORPHOLOGY_PROMOTION_ORDER = (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
SUPPORTED_HYBRID_MORPHOLOGY_CLASSES = HYBRID_MORPHOLOGY_PROMOTION_ORDER

DEFAULT_HYBRID_MORPHOLOGY_MODEL_MODE = "surface_wave"
DEFAULT_HYBRID_MORPHOLOGY_INTEGRATION_STRATEGY = "per_root_morphology_class_metadata"
DEFAULT_HYBRID_MORPHOLOGY_FIELD_NAME = "surface_wave_execution_plan.hybrid_morphology"
DEFAULT_SHARED_READOUT_VALUE_SEMANTICS = "shared_downstream_activation"

_DEFAULT_RESULT_SERIALIZATION_REQUIREMENTS = {
    "execution_plan_field": DEFAULT_HYBRID_MORPHOLOGY_FIELD_NAME,
    "execution_provenance_field": "model_execution.hybrid_morphology",
    "wave_summary_field": "surface_wave_summary.hybrid_morphology",
}

_PROMOTION_INVARIANTS = (
    "selected_root_ids_and_manifest_arm_identity_do_not_change_across_fidelity_promotion",
    "shared_readout_ids_units_and_timebase_semantics_remain_fixed_across_classes",
    "coupling_bundle_sign_delay_and_aggregation_semantics_are_preserved_across_classes",
    "root_local_input_identity_and_output_comparison_scope_remain_fixed_across_classes",
    "promotion_changes_only_intraneuron_state_resolution_not_the_selected_connectome_edges",
    "class_specific_diagnostics_may_expand_under_extensions_without_mutating_shared_result_bundle_payloads",
)

_CLASS_SPECS: dict[str, dict[str, Any]] = {
    POINT_NEURON_CLASS: {
        "canonical_project_role": ROLE_POINT_SIMULATED,
        "promotion_rank": 0,
        "required_local_assets": [
            "root_local_synapse_registry",
            "incoming_anchor_map",
            "outgoing_anchor_map",
            "root_coupling_index",
            "selected_edge_coupling_bundles",
        ],
        "optional_local_assets": [
            "raw_swc_skeleton",
            "processed_surface_mesh",
            "geometry_descriptors",
        ],
        "realized_state_space": {
            "state_space_kind": "single_root_lumped_state",
            "state_axes": "per_root",
            "state_layout_semantics": "root_activation_with_optional_auxiliary_terms",
            "local_geometry_resolution": "no_intraneuron_spatial_resolution",
        },
        "readout_surface": {
            "local_readout_surface": "root_state_scalar",
            "shared_readout_value_semantics": DEFAULT_SHARED_READOUT_VALUE_SEMANTICS,
            "comparison_observable": "root_local_activation_summary",
        },
        "coupling_anchor_resolution": {
            "outgoing_resolution": "lumped_root_state",
            "incoming_resolution": "lumped_root_state",
            "outgoing_anchor_type": "point_state",
            "incoming_anchor_type": "point_state",
        },
        "serialization_requirements": {
            "planner_record_fields": [
                "root_id",
                "morphology_class",
                "source_project_role",
                "promotion_rank",
            ],
            "shared_readout_requirement": (
                "emit the same shared readout IDs on simulator_result_bundle.v1 timebase"
            ),
            "class_specific_extension_policy": (
                "point-neuron runs may serialize scalar diagnostics, but shared traces stay on the common readout surface"
            ),
        },
        "approximation_notes": [
            "Approximates the neuron as one root-local state and does not resolve intraneuron propagation or branch-local timing.",
            "Preserves root identity plus coupling sign, delay, and total signed weight semantics from coupling_bundle.v1.",
        ],
        "class_specific_behaviors": [
            "Cannot express morphology-local spread, geodesic delays, or patch-selective readout variation inside one neuron.",
        ],
    },
    SKELETON_NEURON_CLASS: {
        "canonical_project_role": ROLE_SKELETON_SIMULATED,
        "promotion_rank": 1,
        "required_local_assets": [
            "raw_swc_skeleton",
            SKELETON_RUNTIME_ASSET_KEY,
            "root_local_synapse_registry",
            "incoming_anchor_map",
            "outgoing_anchor_map",
            "root_coupling_index",
            "selected_edge_coupling_bundles",
        ],
        "optional_local_assets": [
            "processed_surface_mesh",
            "surface_transfer_operators",
            "geometry_descriptors",
        ],
        "realized_state_space": {
            "state_space_kind": "distributed_skeleton_path_state",
            "state_axes": "per_skeleton_node_or_segment",
            "state_layout_semantics": "skeleton_local_activation_with_optional_auxiliary_terms",
            "local_geometry_resolution": "branch_and_path_resolved_without_surface_sheet_detail",
        },
        "readout_surface": {
            "local_readout_surface": "skeleton_anchor_cloud",
            "shared_readout_value_semantics": DEFAULT_SHARED_READOUT_VALUE_SEMANTICS,
            "comparison_observable": "root_local_activation_summary",
        },
        "coupling_anchor_resolution": {
            "outgoing_resolution": "skeleton_node",
            "incoming_resolution": "skeleton_node",
            "outgoing_anchor_type": "skeleton_node",
            "incoming_anchor_type": "skeleton_node",
        },
        "serialization_requirements": {
            "planner_record_fields": [
                "root_id",
                "morphology_class",
                "source_project_role",
                "promotion_rank",
            ],
            "shared_readout_requirement": (
                "emit the same shared readout IDs on simulator_result_bundle.v1 timebase"
            ),
            "class_specific_extension_policy": (
                "skeleton-resolved diagnostics may live under extensions while shared comparison artifacts remain unchanged"
            ),
        },
        "approximation_notes": [
            "Resolves branch-local and path-local variation while omitting explicit surface-sheet geometry and patch-level tangential spread.",
            "May use skeleton-node anchors for coupling and readout, but promotion must preserve coupling sign, delay, and root-level observable semantics.",
        ],
        "class_specific_behaviors": [
            "Can express branch-local timing or attenuation that a point neuron cannot, but not surface-sheet effects reserved for surface neurons.",
        ],
    },
    SURFACE_NEURON_CLASS: {
        "canonical_project_role": ROLE_SURFACE_SIMULATED,
        "promotion_rank": 2,
        "required_local_assets": [
            "processed_surface_mesh",
            "fine_surface_operator",
            "coarse_patch_operator",
            "surface_transfer_operators",
            "surface_operator_metadata",
            "root_local_synapse_registry",
            "incoming_anchor_map",
            "outgoing_anchor_map",
            "root_coupling_index",
            "selected_edge_coupling_bundles",
        ],
        "optional_local_assets": [
            "raw_mesh",
            "raw_swc_skeleton",
            "geometry_descriptors",
            "geometry_qa",
        ],
        "realized_state_space": {
            "state_space_kind": "distributed_surface_field",
            "state_axes": "per_surface_vertex_with_patch_projection",
            "state_layout_semantics": "surface_activation_velocity_optional_recovery",
            "local_geometry_resolution": "simplified_surface_mesh_with_coarse_patch_readout",
        },
        "readout_surface": {
            "local_readout_surface": "coarse_patch_cloud",
            "shared_readout_value_semantics": DEFAULT_SHARED_READOUT_VALUE_SEMANTICS,
            "comparison_observable": "root_local_activation_summary",
        },
        "coupling_anchor_resolution": {
            "outgoing_resolution": "coarse_patch",
            "incoming_resolution": "coarse_patch",
            "outgoing_anchor_type": "surface_patch",
            "incoming_anchor_type": "surface_patch",
        },
        "serialization_requirements": {
            "planner_record_fields": [
                "root_id",
                "morphology_class",
                "source_project_role",
                "promotion_rank",
            ],
            "shared_readout_requirement": (
                "emit the same shared readout IDs on simulator_result_bundle.v1 timebase"
            ),
            "class_specific_extension_policy": (
                "surface-resolved diagnostics may be written under extensions, but shared comparison payloads remain class-invariant"
            ),
        },
        "approximation_notes": [
            "Resolves surface-local spread on the simplified mesh and patch projection while abstracting away raw membrane biophysics and per-synapse state.",
            "May change local spatial patterning relative to lower fidelities, but promotion must preserve root identity plus coupling sign, delay, and comparison-readout semantics.",
        ],
        "class_specific_behaviors": [
            "Can express geodesic spread, patch-local heterogeneity, anisotropy, and descriptor-scaled branching when the wave model enables them.",
        ],
    },
}

_CLASS_ALIASES = {
    POINT_NEURON_CLASS: {
        POINT_NEURON_CLASS,
        ROLE_POINT_SIMULATED,
    },
    SKELETON_NEURON_CLASS: {
        SKELETON_NEURON_CLASS,
        ROLE_SKELETON_SIMULATED,
    },
    SURFACE_NEURON_CLASS: {
        SURFACE_NEURON_CLASS,
        ROLE_SURFACE_SIMULATED,
    },
}


def build_hybrid_morphology_contract_metadata() -> dict[str, Any]:
    class_catalog = [
        _build_class_definition(class_name)
        for class_name in HYBRID_MORPHOLOGY_PROMOTION_ORDER
    ]
    return {
        "contract_version": HYBRID_MORPHOLOGY_CONTRACT_VERSION,
        "design_note": HYBRID_MORPHOLOGY_DESIGN_NOTE,
        "design_note_version": HYBRID_MORPHOLOGY_DESIGN_NOTE_VERSION,
        "supported_morphology_classes": list(HYBRID_MORPHOLOGY_PROMOTION_ORDER),
        "promotion_order": list(HYBRID_MORPHOLOGY_PROMOTION_ORDER),
        "shared_readout_value_semantics": DEFAULT_SHARED_READOUT_VALUE_SEMANTICS,
        "class_catalog": class_catalog,
        "allowed_cross_class_coupling_routes": _build_allowed_cross_class_coupling_routes(
            class_catalog
        ),
        "promotion_invariants": list(_PROMOTION_INVARIANTS),
    }


def build_hybrid_morphology_plan_metadata(
    *,
    root_records: Sequence[Mapping[str, Any]],
    model_mode: str = DEFAULT_HYBRID_MORPHOLOGY_MODEL_MODE,
) -> dict[str, Any]:
    payload = {
        "contract_version": HYBRID_MORPHOLOGY_CONTRACT_VERSION,
        "design_note": HYBRID_MORPHOLOGY_DESIGN_NOTE,
        "design_note_version": HYBRID_MORPHOLOGY_DESIGN_NOTE_VERSION,
        "planner_integration": {
            "model_mode": model_mode,
            "strategy": DEFAULT_HYBRID_MORPHOLOGY_INTEGRATION_STRATEGY,
            "field_name": DEFAULT_HYBRID_MORPHOLOGY_FIELD_NAME,
        },
        "per_root_class_metadata": [
            copy.deepcopy(dict(record))
            for record in root_records
        ],
    }
    return parse_hybrid_morphology_plan_metadata(payload)


def parse_hybrid_morphology_plan_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Hybrid morphology plan metadata must be a mapping.")

    contract_version = _normalize_nonempty_string(
        payload.get("contract_version", HYBRID_MORPHOLOGY_CONTRACT_VERSION),
        field_name="hybrid_morphology.contract_version",
    )
    if contract_version != HYBRID_MORPHOLOGY_CONTRACT_VERSION:
        raise ValueError(
            "Hybrid morphology plan metadata contract_version must be "
            f"{HYBRID_MORPHOLOGY_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        payload.get("design_note", HYBRID_MORPHOLOGY_DESIGN_NOTE),
        field_name="hybrid_morphology.design_note",
    )
    if design_note != HYBRID_MORPHOLOGY_DESIGN_NOTE:
        raise ValueError(
            "Hybrid morphology plan metadata design_note must be "
            f"{HYBRID_MORPHOLOGY_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        payload.get("design_note_version", HYBRID_MORPHOLOGY_DESIGN_NOTE_VERSION),
        field_name="hybrid_morphology.design_note_version",
    )
    if design_note_version != HYBRID_MORPHOLOGY_DESIGN_NOTE_VERSION:
        raise ValueError(
            "Hybrid morphology plan metadata design_note_version must be "
            f"{HYBRID_MORPHOLOGY_DESIGN_NOTE_VERSION!r}."
        )

    planner_integration = _normalize_planner_integration(
        payload.get("planner_integration"),
    )
    per_root_raw = _require_sequence(
        payload.get("per_root_class_metadata", ()),
        field_name="hybrid_morphology.per_root_class_metadata",
    )
    normalized_per_root = [
        normalize_hybrid_morphology_root_metadata(item)
        for item in per_root_raw
    ]
    root_ids = [int(item["root_id"]) for item in normalized_per_root]
    if len(set(root_ids)) != len(root_ids):
        raise ValueError(
            "hybrid_morphology.per_root_class_metadata contains duplicate root_id values."
        )
    normalized_per_root.sort(key=lambda item: int(item["root_id"]))

    contract_metadata = build_hybrid_morphology_contract_metadata()
    contract_metadata["planner_integration"] = planner_integration
    contract_metadata["discovered_morphology_classes"] = discover_hybrid_morphology_classes(
        normalized_per_root
    )
    contract_metadata["per_root_class_metadata"] = normalized_per_root
    contract_metadata["result_serialization_requirements"] = copy.deepcopy(
        _DEFAULT_RESULT_SERIALIZATION_REQUIREMENTS
    )
    return contract_metadata


def normalize_hybrid_morphology_root_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Hybrid morphology root metadata must be a mapping.")
    if "root_id" not in payload:
        raise ValueError("Hybrid morphology root metadata requires root_id.")
    root_id = int(payload["root_id"])
    cell_type = str(payload.get("cell_type", ""))
    source_token = payload.get("morphology_class", payload.get("project_role"))
    if source_token is None:
        raise ValueError(
            "Hybrid morphology root metadata requires either morphology_class or project_role."
        )
    morphology_class = normalize_hybrid_morphology_class(
        source_token,
        field_name=f"hybrid_morphology.root[{root_id}]",
    )
    class_definition = _build_class_definition(morphology_class)
    source_project_role = payload.get(
        "project_role",
        class_definition["canonical_project_role"],
    )
    normalized_project_role = _normalize_identifier(
        source_project_role,
        field_name=f"hybrid_morphology.root[{root_id}].project_role",
    )
    if normalize_hybrid_morphology_class(
        normalized_project_role,
        field_name=f"hybrid_morphology.root[{root_id}].project_role",
    ) != morphology_class:
        raise ValueError(
            "Hybrid morphology root metadata project_role does not match the declared "
            f"morphology_class for root {root_id}."
        )
    return {
        "root_id": root_id,
        "cell_type": cell_type,
        "source_project_role": normalized_project_role,
        "canonical_project_role": class_definition["canonical_project_role"],
        "morphology_class": morphology_class,
        "promotion_rank": int(class_definition["promotion_rank"]),
        "required_local_assets": copy.deepcopy(class_definition["required_local_assets"]),
        "optional_local_assets": copy.deepcopy(class_definition["optional_local_assets"]),
        "realized_state_space": copy.deepcopy(class_definition["realized_state_space"]),
        "readout_surface": copy.deepcopy(class_definition["readout_surface"]),
        "coupling_anchor_resolution": copy.deepcopy(
            class_definition["coupling_anchor_resolution"]
        ),
        "serialization_requirements": copy.deepcopy(
            class_definition["serialization_requirements"]
        ),
        "approximation_notes": copy.deepcopy(class_definition["approximation_notes"]),
        "class_specific_behaviors": copy.deepcopy(
            class_definition["class_specific_behaviors"]
        ),
    }


def discover_hybrid_morphology_classes(
    payloads: Sequence[Mapping[str, Any] | str],
) -> list[str]:
    if not isinstance(payloads, Sequence) or isinstance(payloads, (str, bytes)):
        raise ValueError("Hybrid morphology discovery expects a list of class records.")
    discovered: set[str] = set()
    for index, payload in enumerate(payloads):
        if isinstance(payload, Mapping):
            token = payload.get("morphology_class", payload.get("project_role"))
            if token is None:
                raise ValueError(
                    "Hybrid morphology class discovery requires morphology_class or "
                    f"project_role in record {index}."
                )
        else:
            token = payload
        discovered.add(
            normalize_hybrid_morphology_class(
                token,
                field_name=f"hybrid_morphology_discovery[{index}]",
            )
        )
    return [
        class_name
        for class_name in HYBRID_MORPHOLOGY_PROMOTION_ORDER
        if class_name in discovered
    ]


def normalize_hybrid_morphology_class(value: Any, *, field_name: str) -> str:
    normalized = _normalize_identifier(value, field_name=field_name).replace("-", "_")
    for class_name in HYBRID_MORPHOLOGY_PROMOTION_ORDER:
        if normalized in _CLASS_ALIASES[class_name]:
            return class_name
    raise ValueError(
        f"{field_name} must resolve to one of {list(HYBRID_MORPHOLOGY_PROMOTION_ORDER)!r}, got {normalized!r}."
    )


def _build_allowed_cross_class_coupling_routes(
    class_catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    definitions = {
        str(item["morphology_class"]): item
        for item in class_catalog
    }
    routes: list[dict[str, Any]] = []
    for source_class in HYBRID_MORPHOLOGY_PROMOTION_ORDER:
        for target_class in HYBRID_MORPHOLOGY_PROMOTION_ORDER:
            source_definition = definitions[source_class]
            target_definition = definitions[target_class]
            routes.append(
                {
                    "route_id": f"{source_class}_to_{target_class}",
                    "source_morphology_class": source_class,
                    "target_morphology_class": target_class,
                    "source_readout_surface": source_definition["readout_surface"][
                        "local_readout_surface"
                    ],
                    "source_anchor_resolution": source_definition[
                        "coupling_anchor_resolution"
                    ]["outgoing_resolution"],
                    "target_anchor_resolution": target_definition[
                        "coupling_anchor_resolution"
                    ]["incoming_resolution"],
                    "target_landing_surface": target_definition["readout_surface"][
                        "local_readout_surface"
                    ],
                    "sign_delay_invariant": (
                        "preserve_coupling_bundle_v1_sign_delay_and_aggregation_semantics"
                    ),
                }
            )
    return routes


def _build_class_definition(class_name: str) -> dict[str, Any]:
    spec = _CLASS_SPECS[class_name]
    return {
        "morphology_class": class_name,
        "canonical_project_role": spec["canonical_project_role"],
        "accepted_aliases": sorted(_CLASS_ALIASES[class_name]),
        "promotion_rank": int(spec["promotion_rank"]),
        "required_local_assets": list(spec["required_local_assets"]),
        "optional_local_assets": list(spec["optional_local_assets"]),
        "realized_state_space": copy.deepcopy(spec["realized_state_space"]),
        "readout_surface": copy.deepcopy(spec["readout_surface"]),
        "coupling_anchor_resolution": copy.deepcopy(
            spec["coupling_anchor_resolution"]
        ),
        "serialization_requirements": copy.deepcopy(
            spec["serialization_requirements"]
        ),
        "approximation_notes": list(spec["approximation_notes"]),
        "class_specific_behaviors": list(spec["class_specific_behaviors"]),
    }


def _normalize_planner_integration(payload: Any) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError("hybrid_morphology.planner_integration must be a mapping.")
    model_mode = _normalize_identifier(
        payload.get("model_mode", DEFAULT_HYBRID_MORPHOLOGY_MODEL_MODE),
        field_name="hybrid_morphology.planner_integration.model_mode",
    )
    strategy = _normalize_identifier(
        payload.get("strategy", DEFAULT_HYBRID_MORPHOLOGY_INTEGRATION_STRATEGY),
        field_name="hybrid_morphology.planner_integration.strategy",
    )
    if strategy != DEFAULT_HYBRID_MORPHOLOGY_INTEGRATION_STRATEGY:
        raise ValueError(
            "hybrid_morphology.planner_integration.strategy must be "
            f"{DEFAULT_HYBRID_MORPHOLOGY_INTEGRATION_STRATEGY!r}."
        )
    field_name = _normalize_nonempty_string(
        payload.get("field_name", DEFAULT_HYBRID_MORPHOLOGY_FIELD_NAME),
        field_name="hybrid_morphology.planner_integration.field_name",
    )
    if field_name != DEFAULT_HYBRID_MORPHOLOGY_FIELD_NAME:
        raise ValueError(
            "hybrid_morphology.planner_integration.field_name must be "
            f"{DEFAULT_HYBRID_MORPHOLOGY_FIELD_NAME!r}."
        )
    return {
        "model_mode": model_mode,
        "strategy": strategy,
        "field_name": field_name,
    }


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a list.")
    return value
