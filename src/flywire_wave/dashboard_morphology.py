from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from .dashboard_session_contract import (
    MORPHOLOGY_PANE_ID,
    SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
)
from .hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from .simulator_result_contract import (
    discover_simulator_root_morphology_metadata,
    load_simulator_root_state_payload,
    load_simulator_shared_readout_payload,
)


DASHBOARD_MORPHOLOGY_CONTEXT_VERSION = "dashboard_morphology_context.v1"
DASHBOARD_MORPHOLOGY_VIEW_MODEL_VERSION = "dashboard_morphology_view_model.v1"

_SUPPORTED_MORPHOLOGY_OVERLAY_IDS = (
    SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
)


def build_dashboard_morphology_context(
    *,
    circuit_context: Mapping[str, Any],
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
    analysis_ui_payload: Mapping[str, Any],
    selected_neuron_id: str | int | None,
) -> dict[str, Any]:
    root_catalog = _require_sequence(
        circuit_context.get("root_catalog"),
        field_name="circuit_context.root_catalog",
    )
    mixed_root_records = _mixed_root_record_map(wave_metadata)
    root_state_payloads = _root_state_payload_map(
        wave_metadata=wave_metadata,
        root_ids=[int(_require_mapping(item, field_name="circuit_context.root_catalog[]")["root_id"]) for item in root_catalog],
    )
    phase_map_root_ids = _phase_map_root_ids(analysis_ui_payload)
    shared_overlay = _build_shared_readout_overlay(
        baseline_metadata=baseline_metadata,
        wave_metadata=wave_metadata,
    )

    normalized_root_catalog: list[dict[str, Any]] = []
    for raw_root in root_catalog:
        root = _require_mapping(raw_root, field_name="circuit_context.root_catalog[]")
        root_id = int(root["root_id"])
        mixed_record = copy.deepcopy(mixed_root_records.get(root_id, {}))
        root_state_payload = root_state_payloads.get(root_id)
        morphology_class = _resolve_root_morphology_class(
            root=root,
            mixed_record=mixed_record,
        )
        available_representations = _available_representations(
            root=root,
            morphology_class=morphology_class,
        )
        render_geometry = _build_render_geometry(
            root=root,
            morphology_class=morphology_class,
            root_state_payload=root_state_payload,
        )
        wave_overlay = _build_wave_overlay_payload(
            root_state_payload=root_state_payload,
            render_geometry=render_geometry,
        )
        phase_map_reference = {
            "availability": "available" if root_id in phase_map_root_ids else "unavailable",
            "reason": None if root_id in phase_map_root_ids else "no packaged phase-map reference targets this root",
            "matching_root_id_count": 1 if root_id in phase_map_root_ids else 0,
        }
        normalized_root_catalog.append(
            {
                "root_id": root_id,
                "cell_type": str(root.get("cell_type", "")),
                "project_role": str(root.get("project_role", "")),
                "morphology_class": morphology_class,
                "available_representations": available_representations,
                "preferred_representation": str(render_geometry["representation_id"]),
                "displayable": bool(render_geometry["displayable"]),
                "geometry_assets": copy.deepcopy(dict(root["geometry_assets"])),
                "mixed_morphology": mixed_record,
                "render_geometry": render_geometry,
                "camera_focus": copy.deepcopy(dict(render_geometry["camera_focus"])),
                "inspection": _build_root_inspection(
                    root=root,
                    morphology_class=morphology_class,
                    render_geometry=render_geometry,
                    root_state_payload=root_state_payload,
                    wave_overlay=wave_overlay,
                    phase_map_reference=phase_map_reference,
                ),
                "overlay_samples": {
                    WAVE_PATCH_ACTIVITY_OVERLAY_ID: wave_overlay,
                },
                "phase_map_reference": phase_map_reference,
            }
        )

    selected_root_ids = [int(item["root_id"]) for item in normalized_root_catalog]
    if not selected_root_ids:
        raise ValueError("Dashboard morphology context requires at least one selected root.")
    if selected_neuron_id is None:
        resolved_selected_neuron_id = selected_root_ids[0]
    else:
        resolved_selected_neuron_id = int(selected_neuron_id)
        if resolved_selected_neuron_id not in set(selected_root_ids):
            raise ValueError(
                "selected_neuron_id must be present in the dashboard selected-root subset, "
                f"got {resolved_selected_neuron_id!r}."
            )
    selected_root_record = next(
        item
        for item in normalized_root_catalog
        if int(item["root_id"]) == resolved_selected_neuron_id
    )
    if not bool(selected_root_record["displayable"]):
        raise ValueError(
            "Insufficient morphology metadata for requested selected_neuron_id "
            f"{resolved_selected_neuron_id!r}; no surface mesh, skeleton, or explicit "
            "point-neuron fallback is available."
        )

    overlay_support = {
        SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID: {
            "overlay_id": SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
            "availability": "available",
            "scope_label": "context",
            "reason": None,
            "supported_in_pane": True,
            "available_root_ids": list(selected_root_ids),
        },
        SHARED_READOUT_ACTIVITY_OVERLAY_ID: shared_overlay,
        WAVE_PATCH_ACTIVITY_OVERLAY_ID: {
            "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
            "availability": (
                "available"
                if any(
                    str(item["overlay_samples"][WAVE_PATCH_ACTIVITY_OVERLAY_ID]["availability"])
                    == "available"
                    for item in normalized_root_catalog
                )
                else "unavailable"
            ),
            "scope_label": "wave_only_diagnostic",
            "reason": None,
            "supported_in_pane": True,
            "available_root_ids": [
                int(item["root_id"])
                for item in normalized_root_catalog
                if str(item["overlay_samples"][WAVE_PATCH_ACTIVITY_OVERLAY_ID]["availability"])
                == "available"
            ],
        },
    }
    if not overlay_support[WAVE_PATCH_ACTIVITY_OVERLAY_ID]["available_root_ids"]:
        overlay_support[WAVE_PATCH_ACTIVITY_OVERLAY_ID]["reason"] = (
            "no mixed-fidelity wave projection traces are packaged for the selected roots"
        )

    fidelity_counts: dict[str, int] = {}
    for item in normalized_root_catalog:
        fidelity_counts[str(item["morphology_class"])] = (
            fidelity_counts.get(str(item["morphology_class"]), 0) + 1
        )

    return {
        "pane_id": MORPHOLOGY_PANE_ID,
        "context_version": DASHBOARD_MORPHOLOGY_CONTEXT_VERSION,
        "selected_neuron_id": int(resolved_selected_neuron_id),
        "root_catalog": normalized_root_catalog,
        "displayable_root_ids": [
            int(item["root_id"]) for item in normalized_root_catalog if bool(item["displayable"])
        ],
        "overlay_support": overlay_support,
        "supported_overlay_ids": list(_SUPPORTED_MORPHOLOGY_OVERLAY_IDS),
        "fidelity_summary": {
            "class_counts": fidelity_counts,
            "selected_root_count": len(selected_root_ids),
        },
    }


def resolve_dashboard_morphology_view_model(
    morphology_context: Mapping[str, Any],
    *,
    selected_neuron_id: int,
    active_overlay_id: str,
    selected_readout_id: str,
    comparison_mode: str,
    active_arm_id: str,
    sample_index: int,
    hovered_neuron_id: int | None = None,
) -> dict[str, Any]:
    context = _require_mapping(
        morphology_context,
        field_name="morphology_context",
    )
    root_catalog = [
        _require_mapping(item, field_name="morphology_context.root_catalog[]")
        for item in _require_sequence(
            context.get("root_catalog"),
            field_name="morphology_context.root_catalog",
        )
    ]
    if not root_catalog:
        raise ValueError("morphology_context.root_catalog must not be empty.")
    selected_root = next(
        (
            item
            for item in root_catalog
            if int(item["root_id"]) == int(selected_neuron_id)
        ),
        None,
    )
    if selected_root is None:
        raise ValueError(
            f"selected_neuron_id {int(selected_neuron_id)!r} is not present in morphology_context.root_catalog."
        )
    hovered_root = next(
        (
            item
            for item in root_catalog
            if hovered_neuron_id is not None and int(item["root_id"]) == int(hovered_neuron_id)
        ),
        None,
    )
    overlay_state = _resolve_overlay_state(
        context=context,
        selected_root=selected_root,
        active_overlay_id=str(active_overlay_id),
        selected_readout_id=str(selected_readout_id),
        comparison_mode=str(comparison_mode),
        active_arm_id=str(active_arm_id),
        sample_index=int(sample_index),
    )
    return {
        "format_version": DASHBOARD_MORPHOLOGY_VIEW_MODEL_VERSION,
        "selected_root": copy.deepcopy(dict(selected_root)),
        "hovered_root": None if hovered_root is None else copy.deepcopy(dict(hovered_root)),
        "camera_focus": copy.deepcopy(dict(selected_root["camera_focus"])),
        "overlay_state": overlay_state,
    }


def _mixed_root_record_map(wave_metadata: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    try:
        roots = discover_simulator_root_morphology_metadata(wave_metadata)
    except ValueError:
        return {}
    return {
        int(item["root_id"]): copy.deepcopy(dict(item))
        for item in roots
    }


def _root_state_payload_map(
    *,
    wave_metadata: Mapping[str, Any],
    root_ids: Sequence[int],
) -> dict[int, dict[str, Any]]:
    payloads: dict[int, dict[str, Any]] = {}
    for root_id in sorted({int(item) for item in root_ids}):
        try:
            payloads[root_id] = load_simulator_root_state_payload(
                wave_metadata,
                root_id=root_id,
            )
        except ValueError:
            continue
    return payloads


def _phase_map_root_ids(analysis_ui_payload: Mapping[str, Any]) -> set[int]:
    wave_only = _require_mapping(
        analysis_ui_payload.get("wave_only_diagnostics", {}),
        field_name="analysis_ui_payload.wave_only_diagnostics",
    )
    root_ids: set[int] = set()
    for item in wave_only.get("phase_map_references", []):
        if not isinstance(item, Mapping):
            continue
        for root_id in item.get("root_ids", []):
            root_ids.add(int(root_id))
    return root_ids


def _build_shared_readout_overlay(
    *,
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    baseline_payload = load_simulator_shared_readout_payload(baseline_metadata)
    wave_payload = load_simulator_shared_readout_payload(wave_metadata)
    baseline_ids = tuple(str(item) for item in baseline_payload["readout_ids"])
    wave_ids = tuple(str(item) for item in wave_payload["readout_ids"])
    if baseline_ids != wave_ids:
        raise ValueError(
            "Dashboard morphology shared overlay requires matching baseline and wave readout_ids."
        )
    if not np.allclose(
        np.asarray(baseline_payload["time_ms"], dtype=np.float64),
        np.asarray(wave_payload["time_ms"], dtype=np.float64),
        rtol=0.0,
        atol=1.0e-9,
    ):
        raise ValueError(
            "Dashboard morphology shared overlay requires matching baseline and wave readout time arrays."
        )
    readout_catalog = []
    baseline_values = np.asarray(baseline_payload["values"], dtype=np.float64)
    wave_values = np.asarray(wave_payload["values"], dtype=np.float64)
    for index, readout_id in enumerate(baseline_ids):
        baseline_series = baseline_values[:, index]
        wave_series = wave_values[:, index]
        delta_series = wave_series - baseline_series
        domain = np.asarray(
            [
                *baseline_series.tolist(),
                *wave_series.tolist(),
                *delta_series.tolist(),
            ],
            dtype=np.float64,
        )
        scale = float(max(np.max(np.abs(domain)), 1.0e-9))
        readout_catalog.append(
            {
                "readout_id": str(readout_id),
                "time_ms": baseline_payload["time_ms"].astype(np.float64).tolist(),
                "baseline_values": baseline_series.astype(np.float64).tolist(),
                "wave_values": wave_series.astype(np.float64).tolist(),
                "delta_values": delta_series.astype(np.float64).tolist(),
                "abs_value_scale": scale,
            }
        )
    return {
        "overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
        "availability": "available" if readout_catalog else "unavailable",
        "scope_label": "shared_comparison",
        "reason": None if readout_catalog else "no shared comparable readouts are available",
        "supported_in_pane": True,
        "readout_catalog": readout_catalog,
    }


def _resolve_root_morphology_class(
    *,
    root: Mapping[str, Any],
    mixed_record: Mapping[str, Any],
) -> str:
    if mixed_record.get("morphology_class"):
        return str(mixed_record["morphology_class"])
    return str(root.get("morphology_class", POINT_NEURON_CLASS))


def _available_representations(
    *,
    root: Mapping[str, Any],
    morphology_class: str,
) -> list[str]:
    geometry_assets = _require_mapping(
        root.get("geometry_assets"),
        field_name="root.geometry_assets",
    )
    available: list[str] = []
    if bool(_require_mapping(geometry_assets["simplified_mesh"], field_name="root.geometry_assets.simplified_mesh")["exists"]):
        available.append("surface_mesh")
    if bool(_require_mapping(geometry_assets["raw_skeleton"], field_name="root.geometry_assets.raw_skeleton")["exists"]):
        available.append("skeleton")
    if str(morphology_class) == POINT_NEURON_CLASS:
        available.append("point_fallback")
    return available


def _build_render_geometry(
    *,
    root: Mapping[str, Any],
    morphology_class: str,
    root_state_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    geometry_assets = _require_mapping(
        root.get("geometry_assets"),
        field_name="root.geometry_assets",
    )
    simplified_mesh = _require_mapping(
        geometry_assets["simplified_mesh"],
        field_name="root.geometry_assets.simplified_mesh",
    )
    raw_skeleton = _require_mapping(
        geometry_assets["raw_skeleton"],
        field_name="root.geometry_assets.raw_skeleton",
    )

    if str(morphology_class) == SURFACE_NEURON_CLASS:
        if bool(simplified_mesh.get("exists")):
            surface_geometry = _surface_mesh_geometry(Path(str(simplified_mesh["path"])).resolve())
            if surface_geometry is not None:
                return surface_geometry
        proxy_geometry = _surface_patch_proxy_geometry(root_state_payload)
        if proxy_geometry is not None:
            return proxy_geometry
        if bool(raw_skeleton.get("exists")):
            skeleton_geometry = _skeleton_geometry(Path(str(raw_skeleton["path"])).resolve())
            if skeleton_geometry is not None:
                skeleton_geometry["truth_note"] = (
                    "Surface fidelity is selected for this root, but the packaged session only exposes a renderable skeleton proxy."
                )
                return skeleton_geometry

    if str(morphology_class) == SKELETON_NEURON_CLASS and bool(raw_skeleton.get("exists")):
        skeleton_geometry = _skeleton_geometry(Path(str(raw_skeleton["path"])).resolve())
        if skeleton_geometry is not None:
            return skeleton_geometry

    if str(morphology_class) == SKELETON_NEURON_CLASS:
        proxy_geometry = _linear_proxy_geometry(
            root_state_payload=root_state_payload,
            representation_id="skeleton_proxy",
            title="Skeleton Proxy",
            truth_note="Skeleton fidelity is selected, but the packaged session does not include a renderable SWC. The pane falls back to a state-shaped proxy.",
        )
        if proxy_geometry is not None:
            return proxy_geometry

    return _point_geometry(
        truth_note=(
            "Point-neuron fallback is active for this root."
            if str(morphology_class) == POINT_NEURON_CLASS
            else "No higher-fidelity renderable geometry is packaged for this root, so the pane falls back to a point marker."
        )
    )


def _surface_mesh_geometry(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        mesh = trimesh.load_mesh(path, process=False)
    except Exception:
        return None
    if isinstance(mesh, trimesh.Scene):
        if not mesh.geometry:
            return None
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    vertices = np.asarray(getattr(mesh, "vertices", np.empty((0, 3))), dtype=np.float64)
    faces = np.asarray(getattr(mesh, "faces", np.empty((0, 3))), dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[0] == 0:
        return None
    projected, view_box = _project_points(vertices)
    polygons = []
    if faces.ndim == 2 and faces.shape[1] >= 3 and faces.shape[0] > 0:
        for face_index, face in enumerate(faces.tolist()):
            points = [projected[int(vertex_index)] for vertex_index in face[:3]]
            polygons.append(
                {
                    "element_id": f"face_{face_index}",
                    "kind": "polygon",
                    "points": points,
                }
            )
    else:
        order = np.argsort(projected[:, 0])
        polygons.append(
            {
                "element_id": "surface_outline",
                "kind": "polyline",
                "points": [projected[int(index)] for index in order.tolist()],
            }
        )
    return {
        "displayable": True,
        "representation_id": "surface_mesh",
        "title": "Surface Mesh",
        "truth_note": "Rendering the packaged simplified surface mesh.",
        "view_box": view_box,
        "camera_focus": _camera_focus(view_box),
        "mesh_polygons": polygons,
        "segments": [],
        "point": None,
        "overlay_elements": [],
    }


def _surface_patch_proxy_geometry(
    root_state_payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if root_state_payload is None:
        return None
    projection_trace = np.asarray(root_state_payload.get("projection_trace", []), dtype=np.float64)
    if projection_trace.ndim != 2 or projection_trace.shape[1] < 2:
        return None
    patch_count = int(projection_trace.shape[1])
    polygons = []
    overlay_elements = []
    for index in range(patch_count):
        x0 = float(index) * 1.2
        x1 = x0 + 1.0
        y0 = 0.0
        y1 = 1.0 + 0.22 * float(index % 2)
        points = [
            [x0, y0],
            [x1, y0],
            [x1, y1],
            [x0, y1],
        ]
        polygons.append(
            {
                "element_id": f"patch_{index}",
                "kind": "polygon",
                "points": points,
            }
        )
        overlay_elements.append(
            {
                "element_id": f"patch_{index}",
                "kind": "polygon",
                "points": points,
                "label": f"patch {index + 1}",
            }
        )
    view_box = [-0.4, -0.4, max(2.0, patch_count * 1.2 + 0.4), 2.1]
    return {
        "displayable": True,
        "representation_id": "surface_patch_proxy",
        "title": "Surface Patch Proxy",
        "truth_note": "A surface-resolved state proxy is shown because the packaged session exposes patch activity but not a renderable mesh.",
        "view_box": view_box,
        "camera_focus": _camera_focus(view_box),
        "mesh_polygons": polygons,
        "segments": [],
        "point": None,
        "overlay_elements": overlay_elements,
    }


def _skeleton_geometry(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    nodes: list[tuple[int, np.ndarray, int]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 7:
                raise ValueError(f"Invalid SWC row in {path}: expected 7 columns, got {len(parts)}")
            node_id = int(parts[0])
            coords = np.asarray(
                [float(parts[2]), float(parts[3]), float(parts[4])],
                dtype=np.float64,
            )
            parent_id = int(parts[6])
            nodes.append((node_id, coords, parent_id))
    if not nodes:
        return None
    node_index = {node_id: index for index, (node_id, _coords, _parent_id) in enumerate(nodes)}
    projected, view_box = _project_points(np.vstack([coords for _node_id, coords, _parent_id in nodes]))
    segments = []
    for index, (_node_id, _coords, parent_id) in enumerate(nodes):
        if parent_id not in node_index:
            continue
        parent_index = node_index[parent_id]
        segments.append(
            {
                "element_id": f"segment_{len(segments)}",
                "kind": "segment",
                "points": [projected[parent_index], projected[index]],
            }
        )
    overlay_elements = [
        {
            "element_id": f"node_{index}",
            "kind": "point",
            "center": projected[index],
            "label": f"node {index + 1}",
        }
        for index in range(len(nodes))
    ]
    return {
        "displayable": True,
        "representation_id": "skeleton",
        "title": "Skeleton Approximation",
        "truth_note": "Rendering the packaged SWC skeleton approximation for this mixed-fidelity root.",
        "view_box": view_box,
        "camera_focus": _camera_focus(view_box),
        "mesh_polygons": [],
        "segments": segments,
        "point": None,
        "overlay_elements": overlay_elements,
    }


def _linear_proxy_geometry(
    *,
    root_state_payload: Mapping[str, Any] | None,
    representation_id: str,
    title: str,
    truth_note: str,
) -> dict[str, Any] | None:
    if root_state_payload is None:
        return None
    projection_trace = np.asarray(root_state_payload.get("projection_trace", []), dtype=np.float64)
    if projection_trace.ndim != 2 or projection_trace.shape[1] < 2:
        return None
    element_count = int(projection_trace.shape[1])
    centers = [[float(index) * 1.25, 0.0] for index in range(element_count)]
    segments = [
        {
            "element_id": f"segment_{index}",
            "kind": "segment",
            "points": [centers[index], centers[index + 1]],
        }
        for index in range(element_count - 1)
    ]
    overlay_elements = [
        {
            "element_id": f"node_{index}",
            "kind": "point",
            "center": center,
            "label": f"node {index + 1}",
        }
        for index, center in enumerate(centers)
    ]
    view_box = [-0.5, -1.0, max(2.0, element_count * 1.25), 2.0]
    return {
        "displayable": True,
        "representation_id": representation_id,
        "title": title,
        "truth_note": truth_note,
        "view_box": view_box,
        "camera_focus": _camera_focus(view_box),
        "mesh_polygons": [],
        "segments": segments,
        "point": None,
        "overlay_elements": overlay_elements,
    }


def _point_geometry(*, truth_note: str) -> dict[str, Any]:
    view_box = [-1.0, -1.0, 2.0, 2.0]
    return {
        "displayable": True,
        "representation_id": "point_fallback",
        "title": "Point Fallback",
        "truth_note": truth_note,
        "view_box": view_box,
        "camera_focus": _camera_focus(view_box),
        "mesh_polygons": [],
        "segments": [],
        "point": {
            "element_id": "point_root",
            "center": [0.0, 0.0],
            "radius": 0.34,
        },
        "overlay_elements": [
            {
                "element_id": "point_root",
                "kind": "point",
                "center": [0.0, 0.0],
                "label": "point root",
            }
        ],
    }


def _build_wave_overlay_payload(
    *,
    root_state_payload: Mapping[str, Any] | None,
    render_geometry: Mapping[str, Any],
) -> dict[str, Any]:
    if root_state_payload is None:
        return {
            "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
            "availability": "unavailable",
            "reason": "no mixed-fidelity root state payload is packaged for this root",
            "scope_label": "wave_only_diagnostic",
            "time_ms": [],
            "element_count": 0,
            "element_series": [],
            "projection_semantics": None,
            "summary": {
                "max_abs_value": 0.0,
                "sample_count": 0,
            },
        }
    time_ms = np.asarray(root_state_payload.get("projection_time_ms", []), dtype=np.float64)
    projection_trace = np.asarray(root_state_payload.get("projection_trace", []), dtype=np.float64)
    if projection_trace.ndim != 2 or projection_trace.shape[0] == 0:
        return {
            "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
            "availability": "unavailable",
            "reason": "the packaged root state payload does not include a usable projection trace",
            "scope_label": "wave_only_diagnostic",
            "time_ms": [],
            "element_count": 0,
            "element_series": [],
            "projection_semantics": str(root_state_payload.get("projection_semantics")),
            "summary": {
                "max_abs_value": 0.0,
                "sample_count": 0,
            },
        }
    element_ids = [
        str(item["element_id"])
        for item in _require_sequence(
            render_geometry.get("overlay_elements"),
            field_name="render_geometry.overlay_elements",
        )
    ]
    element_count = min(len(element_ids), int(projection_trace.shape[1]))
    if element_count == 0 and render_geometry.get("point") is not None:
        element_ids = ["point_root"]
        element_count = 1
    if element_count == 0:
        return {
            "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
            "availability": "unavailable",
            "reason": "the selected geometry does not expose overlay elements for wave diagnostics",
            "scope_label": "wave_only_diagnostic",
            "time_ms": time_ms.astype(np.float64).tolist(),
            "element_count": 0,
            "element_series": [],
            "projection_semantics": str(root_state_payload.get("projection_semantics")),
            "summary": {
                "max_abs_value": float(np.max(np.abs(projection_trace))) if projection_trace.size else 0.0,
                "sample_count": int(projection_trace.shape[0]),
            },
        }
    trimmed = projection_trace[:, :element_count]
    element_series = [
        {
            "element_id": element_ids[index],
            "values": trimmed[:, index].astype(np.float64).tolist(),
        }
        for index in range(element_count)
    ]
    return {
        "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
        "availability": "available",
        "reason": None,
        "scope_label": "wave_only_diagnostic",
        "time_ms": time_ms.astype(np.float64).tolist(),
        "element_count": element_count,
        "element_series": element_series,
        "projection_semantics": str(root_state_payload.get("projection_semantics")),
        "summary": {
            "max_abs_value": float(max(np.max(np.abs(trimmed)), 1.0e-9)),
            "sample_count": int(trimmed.shape[0]),
            "final_mean_value": float(np.mean(trimmed[-1])),
        },
    }


def _build_root_inspection(
    *,
    root: Mapping[str, Any],
    morphology_class: str,
    render_geometry: Mapping[str, Any],
    root_state_payload: Mapping[str, Any] | None,
    wave_overlay: Mapping[str, Any],
    phase_map_reference: Mapping[str, Any],
) -> dict[str, Any]:
    state_dimension = 0
    shared_readout_ids: list[str] = []
    if root_state_payload is not None:
        projection_trace = np.asarray(root_state_payload.get("projection_trace", []), dtype=np.float64)
        if projection_trace.ndim == 2:
            state_dimension = int(projection_trace.shape[1])
        shared_readout_ids = [str(item) for item in root_state_payload.get("shared_readout_ids", [])]
    geometry_assets = _require_mapping(
        root.get("geometry_assets"),
        field_name="root.geometry_assets",
    )
    return {
        "morphology_class": str(morphology_class),
        "representation_title": str(render_geometry["title"]),
        "truth_note": str(render_geometry["truth_note"]),
        "surface_mesh_available": bool(_require_mapping(geometry_assets["simplified_mesh"], field_name="root.geometry_assets.simplified_mesh")["exists"]),
        "raw_skeleton_available": bool(_require_mapping(geometry_assets["raw_skeleton"], field_name="root.geometry_assets.raw_skeleton")["exists"]),
        "state_dimension": state_dimension,
        "shared_readout_ids": shared_readout_ids,
        "wave_overlay_availability": str(wave_overlay["availability"]),
        "phase_map_availability": str(phase_map_reference["availability"]),
    }


def _resolve_overlay_state(
    *,
    context: Mapping[str, Any],
    selected_root: Mapping[str, Any],
    active_overlay_id: str,
    selected_readout_id: str,
    comparison_mode: str,
    active_arm_id: str,
    sample_index: int,
) -> dict[str, Any]:
    overlay_support = _require_mapping(
        context.get("overlay_support"),
        field_name="morphology_context.overlay_support",
    )
    if active_overlay_id not in _SUPPORTED_MORPHOLOGY_OVERLAY_IDS:
        return {
            "overlay_id": str(active_overlay_id),
            "availability": "inapplicable",
            "reason": "this overlay belongs in another pane and is not supported in the morphology pane",
            "scope_label": "other_pane_only",
            "sample_index": int(sample_index),
            "comparison_mode": str(comparison_mode),
        }
    if active_overlay_id == SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID:
        return {
            "overlay_id": SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
            "availability": "available",
            "reason": None,
            "scope_label": "context",
            "sample_index": int(sample_index),
            "comparison_mode": str(comparison_mode),
        }
    if active_overlay_id == SHARED_READOUT_ACTIVITY_OVERLAY_ID:
        shared_overlay = _require_mapping(
            overlay_support.get(SHARED_READOUT_ACTIVITY_OVERLAY_ID),
            field_name="morphology_context.overlay_support.shared_readout_activity",
        )
        if str(shared_overlay["availability"]) != "available":
            return {
                "overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                "availability": str(shared_overlay["availability"]),
                "reason": shared_overlay.get("reason"),
                "scope_label": str(shared_overlay["scope_label"]),
                "sample_index": int(sample_index),
                "comparison_mode": str(comparison_mode),
            }
        readout_record = next(
            (
                _require_mapping(item, field_name="morphology_context.overlay_support.shared_readout_activity.readout_catalog[]")
                for item in _require_sequence(
                    shared_overlay.get("readout_catalog"),
                    field_name="morphology_context.overlay_support.shared_readout_activity.readout_catalog",
                )
                if str(_require_mapping(item, field_name="morphology_context.overlay_support.shared_readout_activity.readout_catalog[]")["readout_id"])
                == str(selected_readout_id)
            ),
            None,
        )
        if readout_record is None:
            return {
                "overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                "availability": "unavailable",
                "reason": f"selected readout {selected_readout_id!r} is not packaged for shared morphology overlays",
                "scope_label": str(shared_overlay["scope_label"]),
                "sample_index": int(sample_index),
                "comparison_mode": str(comparison_mode),
            }
        sample = _clamp_sample_index(
            requested_index=sample_index,
            sample_count=len(readout_record["time_ms"]),
        )
        baseline_value = float(readout_record["baseline_values"][sample])
        wave_value = float(readout_record["wave_values"][sample])
        delta_value = float(readout_record["delta_values"][sample])
        if str(comparison_mode) == "paired_delta":
            comparison_value = delta_value
        elif str(active_arm_id).endswith("wave") or "surface_wave" in str(active_arm_id):
            comparison_value = wave_value
        else:
            comparison_value = baseline_value
        return {
            "overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
            "availability": "available",
            "reason": None,
            "scope_label": str(shared_overlay["scope_label"]),
            "sample_index": sample,
            "comparison_mode": str(comparison_mode),
            "readout_id": str(selected_readout_id),
            "time_ms": float(readout_record["time_ms"][sample]),
            "baseline_value": baseline_value,
            "wave_value": wave_value,
            "delta_value": delta_value,
            "comparison_value": comparison_value,
            "normalized_scalar": _normalize_scalar(
                comparison_value,
                abs_scale=float(readout_record["abs_value_scale"]),
            ),
        }
    wave_overlay = _require_mapping(
        _require_mapping(
            selected_root.get("overlay_samples"),
            field_name="selected_root.overlay_samples",
        ).get(WAVE_PATCH_ACTIVITY_OVERLAY_ID),
        field_name="selected_root.overlay_samples.wave_patch_activity",
    )
    if str(wave_overlay["availability"]) != "available":
        return {
            "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
            "availability": str(wave_overlay["availability"]),
            "reason": wave_overlay.get("reason"),
            "scope_label": str(wave_overlay["scope_label"]),
            "sample_index": int(sample_index),
            "comparison_mode": str(comparison_mode),
        }
    sample = _clamp_sample_index(
        requested_index=sample_index,
        sample_count=len(wave_overlay["time_ms"]),
    )
    element_values = [
        {
            "element_id": str(item["element_id"]),
            "value": float(item["values"][sample]),
        }
        for item in _require_sequence(
            wave_overlay.get("element_series"),
            field_name="selected_root.overlay_samples.wave_patch_activity.element_series",
        )
    ]
    abs_scale = float(
        _require_mapping(
            wave_overlay.get("summary"),
            field_name="selected_root.overlay_samples.wave_patch_activity.summary",
        ).get("max_abs_value", 1.0)
    )
    for item in element_values:
        item["normalized_scalar"] = _normalize_scalar(
            float(item["value"]),
            abs_scale=abs_scale,
        )
    return {
        "overlay_id": WAVE_PATCH_ACTIVITY_OVERLAY_ID,
        "availability": "available",
        "reason": None,
        "scope_label": str(wave_overlay["scope_label"]),
        "sample_index": sample,
        "comparison_mode": str(comparison_mode),
        "time_ms": float(wave_overlay["time_ms"][sample]),
        "projection_semantics": wave_overlay.get("projection_semantics"),
        "element_values": element_values,
    }


def _project_points(points: np.ndarray) -> tuple[list[list[float]], list[float]]:
    coords = np.asarray(points, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[0] == 0:
        raise ValueError("Point projection requires a non-empty rank-2 array.")
    if coords.shape[1] == 1:
        projected = np.column_stack([coords[:, 0], np.zeros(coords.shape[0], dtype=np.float64)])
    elif coords.shape[1] == 2:
        projected = coords[:, :2]
    else:
        variances = np.var(coords, axis=0)
        order = np.argsort(variances)[::-1]
        projected = coords[:, order[:2]]
    min_xy = np.min(projected, axis=0)
    max_xy = np.max(projected, axis=0)
    extent = np.maximum(max_xy - min_xy, np.asarray([1.0e-6, 1.0e-6], dtype=np.float64))
    center = (min_xy + max_xy) / 2.0
    span = float(max(extent.max(), 1.0))
    normalized = (projected - center[None, :]) / span
    normalized[:, 1] *= -1.0
    margin = 0.18
    view_box = [
        float(np.min(normalized[:, 0]) - margin),
        float(np.min(normalized[:, 1]) - margin),
        float(np.max(normalized[:, 0]) - np.min(normalized[:, 0]) + 2 * margin),
        float(np.max(normalized[:, 1]) - np.min(normalized[:, 1]) + 2 * margin),
    ]
    return normalized.astype(np.float64).tolist(), view_box


def _camera_focus(view_box: Sequence[float]) -> dict[str, Any]:
    normalized = [float(item) for item in view_box]
    return {
        "view_box": normalized,
        "center": [
            normalized[0] + normalized[2] / 2.0,
            normalized[1] + normalized[3] / 2.0,
        ],
        "span": max(normalized[2], normalized[3]),
    }


def _clamp_sample_index(*, requested_index: int, sample_count: int) -> int:
    if sample_count <= 0:
        return 0
    return max(0, min(int(sample_count) - 1, int(requested_index)))


def _normalize_scalar(value: float, *, abs_scale: float) -> float:
    if abs_scale <= 0.0:
        return 0.5
    normalized = 0.5 + 0.5 * float(value) / float(abs_scale)
    return max(0.0, min(1.0, normalized))


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    return value


__all__ = [
    "DASHBOARD_MORPHOLOGY_CONTEXT_VERSION",
    "DASHBOARD_MORPHOLOGY_VIEW_MODEL_VERSION",
    "build_dashboard_morphology_context",
    "resolve_dashboard_morphology_view_model",
]
