from __future__ import annotations

import copy
import hashlib
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh

from .geometry_contract import build_geometry_bundle_paths, load_operator_bundle_metadata
from .io_utils import ensure_dir, write_json
from .surface_operators import deserialize_sparse_matrix


OPERATOR_QA_REPORT_VERSION = "operator_qa_report.v1"
SVG_WIDTH = 360
SVG_HEIGHT = 280
SVG_PADDING = 18.0
ROTATION_Z_DEGREES = 38.0
ROTATION_X_DEGREES = -28.0
PULSE_STEP_COUNT = 8
PULSE_EIGENVALUE_SAFETY = 0.9
PULSE_RADIUS_SCALE = 1.5
REPORT_PALETTE = (
    "#0f766e",
    "#c2410c",
    "#1d4ed8",
    "#b91c1c",
    "#4d7c0f",
    "#0369a1",
    "#854d0e",
    "#166534",
)
EPSILON = 1.0e-12

DEFAULT_OPERATOR_QA_THRESHOLDS: dict[str, dict[str, Any]] = {
    "fine_operator_symmetry_residual_inf": {
        "warn": 1.0e-6,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "Fine operator should stay symmetric so later engine solvers inherit a stable inner product.",
    },
    "coarse_operator_symmetry_residual_inf": {
        "warn": 1.0e-6,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "Coarse operator should stay symmetric so coarse smoke tests match the Galerkin design note.",
    },
    "fine_constant_nullspace_residual_inf": {
        "warn": 1.0e-6,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "The fine stiffness should keep the constant field in its nullspace under zero-flux assembly.",
    },
    "coarse_constant_nullspace_residual_inf": {
        "warn": 1.0e-6,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "The coarse Galerkin stiffness should preserve the constant-field nullspace.",
    },
    "fine_mass_nonpositive_count": {
        "warn": None,
        "fail": 0.0,
        "blocking": True,
        "description": "Fine lumped mass entries must stay strictly positive.",
    },
    "coarse_mass_nonpositive_count": {
        "warn": None,
        "fail": 0.0,
        "blocking": True,
        "description": "Coarse patch mass entries must stay strictly positive.",
    },
    "transfer_galerkin_operator_residual_inf": {
        "warn": 1.0e-5,
        "fail": 1.0e-3,
        "blocking": True,
        "description": "The coarse operator should match the normalized Galerkin projection of the fine operator.",
    },
    "transfer_coarse_application_residual_relative": {
        "warn": 1.0e-4,
        "fail": 1.0e-2,
        "blocking": True,
        "description": "Applying the coarse operator should agree with restrict-apply-prolong under the normalized transfer pair.",
    },
    "pulse_fine_mass_relative_drift": {
        "warn": 1.0e-7,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "The fine smoke evolution should not create or remove net mass from the localized pulse.",
    },
    "pulse_coarse_mass_relative_drift": {
        "warn": 1.0e-7,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "The coarse smoke evolution should not create or remove net mass from the localized pulse.",
    },
    "pulse_fine_energy_increase_relative": {
        "warn": 1.0e-7,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "The fine smoke evolution should not increase Dirichlet energy when stepped at the chosen stability-safe dt.",
    },
    "pulse_coarse_energy_increase_relative": {
        "warn": 1.0e-7,
        "fail": 1.0e-4,
        "blocking": True,
        "description": "The coarse smoke evolution should not increase Dirichlet energy when stepped at the chosen stability-safe dt.",
    },
    "pulse_final_coarse_vs_restricted_fine_residual_relative": {
        "warn": 0.25,
        "fail": 0.75,
        "blocking": False,
        "description": "The final coarse smoke state should stay reasonably close to the restricted fine smoke state.",
    },
    "pulse_final_fine_vs_prolongated_coarse_residual_relative": {
        "warn": 0.35,
        "fail": 0.90,
        "blocking": False,
        "description": "The prolongated coarse smoke state should stay reasonably close to the fine smoke state.",
    },
}


@dataclass(frozen=True)
class ProjectionFrame:
    rotation: np.ndarray
    center: np.ndarray
    xy_min: np.ndarray
    xy_max: np.ndarray
    scale: float


def resolve_operator_qa_thresholds(overrides: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    thresholds = copy.deepcopy(DEFAULT_OPERATOR_QA_THRESHOLDS)
    if not overrides:
        return thresholds

    for metric_name, override in overrides.items():
        if isinstance(override, Mapping):
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name].update(copy.deepcopy(dict(override)))
        else:
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name]["fail"] = override
    return thresholds


def generate_operator_qa_report(
    *,
    root_ids: Iterable[int],
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    operator_qa_dir: str | Path,
    thresholds: Mapping[str, Any] | None = None,
    pulse_step_count: int = PULSE_STEP_COUNT,
) -> dict[str, Any]:
    normalized_root_ids = _normalize_root_ids(root_ids)
    output_dir = build_operator_qa_output_dir(operator_qa_dir, normalized_root_ids)
    ensure_dir(output_dir)

    resolved_thresholds = resolve_operator_qa_thresholds(thresholds)
    root_entries = [
        _build_root_operator_entry(
            root_id=root_id,
            meshes_raw_dir=meshes_raw_dir,
            skeletons_raw_dir=skeletons_raw_dir,
            processed_mesh_dir=processed_mesh_dir,
            processed_graph_dir=processed_graph_dir,
            output_dir=output_dir,
            thresholds=resolved_thresholds,
            pulse_step_count=int(pulse_step_count),
        )
        for root_id in normalized_root_ids
    ]

    index_path = (output_dir / "index.html").resolve()
    summary_path = (output_dir / "summary.json").resolve()
    markdown_path = (output_dir / "report.md").resolve()
    root_ids_path = (output_dir / "root_ids.txt").resolve()

    status_counts = {
        "pass": sum(1 for entry in root_entries if entry["summary"]["overall_status"] == "pass"),
        "warn": sum(1 for entry in root_entries if entry["summary"]["overall_status"] == "warn"),
        "fail": sum(1 for entry in root_entries if entry["summary"]["overall_status"] == "fail"),
    }
    if status_counts["fail"] > 0:
        overall_status = "fail"
    elif status_counts["warn"] > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    aggregate_blocking_failure_count = sum(int(entry["summary"]["blocking_failure_count"]) for entry in root_entries)
    aggregate_warning_count = sum(int(entry["summary"]["warning_count"]) for entry in root_entries)
    aggregate_failure_count = sum(int(entry["summary"]["failure_count"]) for entry in root_entries)
    milestone10_gate = _milestone10_gate(
        blocking_failure_count=aggregate_blocking_failure_count,
        failure_count=aggregate_failure_count,
        warning_count=aggregate_warning_count,
    )

    summary = {
        "report_version": OPERATOR_QA_REPORT_VERSION,
        "root_ids": normalized_root_ids,
        "root_count": len(normalized_root_ids),
        "output_dir": str(output_dir.resolve()),
        "report_path": str(index_path),
        "summary_path": str(summary_path),
        "markdown_path": str(markdown_path),
        "root_ids_path": str(root_ids_path),
        "overall_status": overall_status,
        "milestone10_gate": milestone10_gate,
        "blocking_failure_count": aggregate_blocking_failure_count,
        "warning_count": aggregate_warning_count,
        "failure_count": aggregate_failure_count,
        "status_counts": status_counts,
        "roots": {
            str(entry["root_id"]): {
                "overall_status": entry["summary"]["overall_status"],
                "milestone10_gate": entry["summary"]["milestone10_gate"],
                "milestone10_engine_ready": bool(entry["summary"]["milestone10_engine_ready"]),
                "warning_count": int(entry["summary"]["warning_count"]),
                "failure_count": int(entry["summary"]["failure_count"]),
                "blocking_failure_count": int(entry["summary"]["blocking_failure_count"]),
                "boundary_vertex_count": int(entry["boundary"]["boundary_vertex_count"]),
                "boundary_edge_count": int(entry["boundary"]["boundary_edge_count"]),
                "patch_count": int(entry["counts"]["patch_count"]),
                "surface_vertex_count": int(entry["counts"]["surface_vertex_count"]),
                "pulse_step_count": int(entry["pulse"]["step_count"]),
                "artifacts": dict(entry["artifacts"]),
                "key_metrics": {
                    metric_name: float(entry["metrics"][metric_name])
                    for metric_name in (
                        "fine_operator_symmetry_residual_inf",
                        "coarse_operator_symmetry_residual_inf",
                        "transfer_galerkin_operator_residual_inf",
                        "pulse_fine_mass_relative_drift",
                        "pulse_fine_energy_increase_relative",
                        "pulse_final_fine_vs_prolongated_coarse_residual_relative",
                    )
                },
            }
            for entry in root_entries
        },
    }

    index_path.write_text(_render_report_html(root_entries=root_entries, summary=summary), encoding="utf-8")
    markdown_path.write_text(_render_report_markdown(root_entries=root_entries, summary=summary), encoding="utf-8")
    write_json(summary, summary_path)
    root_ids_path.write_text("".join(f"{root_id}\n" for root_id in normalized_root_ids), encoding="utf-8")
    return summary


def build_operator_qa_output_dir(operator_qa_dir: str | Path, root_ids: Iterable[int]) -> Path:
    return Path(operator_qa_dir).resolve() / build_operator_qa_slug(root_ids)


def build_operator_qa_slug(root_ids: Iterable[int]) -> str:
    normalized_root_ids = _normalize_root_ids(root_ids)
    joined = "-".join(str(root_id) for root_id in normalized_root_ids)
    if len(joined) <= 64:
        return f"root-ids-{joined}"
    digest = hashlib.sha1(",".join(str(root_id) for root_id in normalized_root_ids).encode("utf-8")).hexdigest()[:12]
    prefix = "-".join(str(root_id) for root_id in normalized_root_ids[:4])
    return f"root-ids-{prefix}-n{len(normalized_root_ids)}-{digest}"


def _build_root_operator_entry(
    *,
    root_id: int,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    output_dir: Path,
    thresholds: Mapping[str, Any],
    pulse_step_count: int,
) -> dict[str, Any]:
    bundle_paths = build_geometry_bundle_paths(
        root_id,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )

    _require_path(bundle_paths.fine_operator_path)
    _require_path(bundle_paths.coarse_operator_path)
    _require_path(bundle_paths.transfer_operator_path)
    _require_path(bundle_paths.operator_metadata_path)
    _require_path(bundle_paths.patch_graph_path)

    fine_payload = _load_npz_payload(bundle_paths.fine_operator_path)
    coarse_payload = _load_npz_payload(bundle_paths.coarse_operator_path)
    transfer_payload = _load_npz_payload(bundle_paths.transfer_operator_path)
    patch_graph_payload = _load_npz_payload(bundle_paths.patch_graph_path)
    descriptor_payload = _load_json_if_exists(bundle_paths.descriptor_sidecar_path)
    geometry_qa_payload = _load_json_if_exists(bundle_paths.qa_sidecar_path)
    operator_metadata = load_operator_bundle_metadata(bundle_paths.operator_metadata_path)

    vertices = np.asarray(fine_payload["vertices"], dtype=np.float64)
    faces = np.asarray(fine_payload["faces"], dtype=np.int32)
    edge_vertex_indices = np.asarray(fine_payload["edge_vertex_indices"], dtype=np.int32)
    boundary_vertex_mask = np.asarray(fine_payload["boundary_vertex_mask"], dtype=bool)
    boundary_edge_mask = np.asarray(fine_payload["boundary_edge_mask"], dtype=bool)
    boundary_face_mask = np.asarray(fine_payload["boundary_face_mask"], dtype=bool)
    surface_to_patch = np.asarray(transfer_payload["surface_to_patch"], dtype=np.int32)
    patch_sizes = np.asarray(transfer_payload["patch_sizes"], dtype=np.int32)
    patch_centroids = np.asarray(coarse_payload["patch_centroids"], dtype=np.float64)
    patch_adj = deserialize_sparse_matrix(patch_graph_payload, prefix="adj")

    fine_operator = deserialize_sparse_matrix(fine_payload, prefix="operator").astype(np.float64)
    fine_stiffness = deserialize_sparse_matrix(fine_payload, prefix="stiffness").astype(np.float64)
    coarse_operator = deserialize_sparse_matrix(coarse_payload, prefix="operator").astype(np.float64)
    coarse_stiffness = deserialize_sparse_matrix(coarse_payload, prefix="stiffness").astype(np.float64)
    restriction = deserialize_sparse_matrix(transfer_payload, prefix="restriction").astype(np.float64)
    normalized_restriction = deserialize_sparse_matrix(transfer_payload, prefix="normalized_restriction").astype(
        np.float64
    )
    normalized_prolongation = deserialize_sparse_matrix(transfer_payload, prefix="normalized_prolongation").astype(
        np.float64
    )

    fine_mass = np.asarray(fine_payload["mass_diagonal"], dtype=np.float64)
    coarse_mass = np.asarray(coarse_payload["mass_diagonal"], dtype=np.float64)

    frame = _build_projection_frame([vertices, patch_centroids])
    pulse = _run_pulse_smoke(
        vertices=vertices,
        fine_mass=fine_mass,
        coarse_mass=coarse_mass,
        fine_operator=fine_operator,
        coarse_operator=coarse_operator,
        restriction=restriction,
        normalized_restriction=normalized_restriction,
        normalized_prolongation=normalized_prolongation,
        geodesic_neighbor_indptr=np.asarray(fine_payload["geodesic_neighbor_indptr"], dtype=np.int32),
        geodesic_neighbor_indices=np.asarray(fine_payload["geodesic_neighbor_indices"], dtype=np.int32),
        geodesic_neighbor_distances=np.asarray(fine_payload["geodesic_neighbor_distances"], dtype=np.float64),
        boundary_vertex_mask=boundary_vertex_mask,
        surface_to_patch=surface_to_patch,
        step_count=pulse_step_count,
    )

    metrics = {
        "fine_operator_symmetry_residual_inf": _sparse_max_abs(fine_operator - fine_operator.transpose().tocsr()),
        "coarse_operator_symmetry_residual_inf": _sparse_max_abs(
            coarse_operator - coarse_operator.transpose().tocsr()
        ),
        "fine_constant_nullspace_residual_inf": float(np.max(np.abs(fine_stiffness @ np.ones(fine_mass.shape[0])))),
        "coarse_constant_nullspace_residual_inf": float(
            np.max(np.abs(coarse_stiffness @ np.ones(coarse_mass.shape[0])))
        ),
        "fine_mass_nonpositive_count": float(np.count_nonzero(fine_mass <= EPSILON)),
        "coarse_mass_nonpositive_count": float(np.count_nonzero(coarse_mass <= EPSILON)),
        "transfer_galerkin_operator_residual_inf": float(transfer_payload["quality_galerkin_operator_residual_inf"]),
        "transfer_coarse_application_residual_relative": float(
            transfer_payload["quality_coarse_application_residual_relative"]
        ),
        "pulse_fine_mass_relative_drift": float(pulse["fine"]["mass_relative_drift"]),
        "pulse_coarse_mass_relative_drift": float(pulse["coarse"]["mass_relative_drift"]),
        "pulse_fine_energy_increase_relative": float(pulse["fine"]["energy_increase_relative"]),
        "pulse_coarse_energy_increase_relative": float(pulse["coarse"]["energy_increase_relative"]),
        "pulse_final_coarse_vs_restricted_fine_residual_relative": float(
            pulse["comparison"]["coarse_vs_restricted_fine_residual_relative"]
        ),
        "pulse_final_fine_vs_prolongated_coarse_residual_relative": float(
            pulse["comparison"]["fine_vs_prolongated_coarse_residual_relative"]
        ),
    }

    checks, summary = evaluate_operator_qa_metrics(metrics=metrics, thresholds=thresholds)

    artifact_paths = _write_root_artifacts(
        root_id=root_id,
        output_dir=output_dir,
        frame=frame,
        vertices=vertices,
        edge_vertex_indices=edge_vertex_indices,
        patch_centroids=patch_centroids,
        patch_adj=patch_adj,
        surface_to_patch=surface_to_patch,
        boundary_vertex_mask=boundary_vertex_mask,
        boundary_edge_mask=boundary_edge_mask,
        pulse=pulse,
    )

    pulse_summary = _pulse_summary_payload(pulse)
    detail_payload = {
        "report_version": OPERATOR_QA_REPORT_VERSION,
        "root_id": int(root_id),
        "input_paths": {
            "processed_mesh_path": str(bundle_paths.simplified_mesh_path),
            "patch_graph_path": str(bundle_paths.patch_graph_path),
            "fine_operator_path": str(bundle_paths.fine_operator_path),
            "coarse_operator_path": str(bundle_paths.coarse_operator_path),
            "transfer_operator_path": str(bundle_paths.transfer_operator_path),
            "operator_metadata_path": str(bundle_paths.operator_metadata_path),
            "descriptor_sidecar_path": str(bundle_paths.descriptor_sidecar_path),
            "geometry_qa_path": str(bundle_paths.qa_sidecar_path),
        },
        "operator_bundle": {
            "realization_mode": str(operator_metadata.get("realization_mode", "")),
            "discretization_family": str(operator_metadata.get("discretization_family", "")),
            "mass_treatment": str(operator_metadata.get("mass_treatment", "")),
            "normalization": str(operator_metadata.get("normalization", "")),
            "boundary_condition_mode": str(operator_metadata.get("boundary_condition_mode", "")),
            "anisotropy_model": str(operator_metadata.get("anisotropy_model", "")),
            "patch_generation_method": str(
                operator_metadata.get("geodesic_neighborhood", {}).get("patch_generation_method", "")
            ),
        },
        "counts": {
            "surface_vertex_count": int(vertices.shape[0]),
            "face_count": int(faces.shape[0]),
            "patch_count": int(patch_sizes.shape[0]),
            "patch_graph_edge_count": int(patch_adj.nnz // 2),
        },
        "boundary": {
            "boundary_vertex_count": int(np.count_nonzero(boundary_vertex_mask)),
            "boundary_edge_count": int(np.count_nonzero(boundary_edge_mask)),
            "boundary_face_count": int(np.count_nonzero(boundary_face_mask)),
            "boundary_vertex_fraction": _fraction(int(np.count_nonzero(boundary_vertex_mask)), int(vertices.shape[0])),
        },
        "descriptor_summary": descriptor_payload,
        "geometry_qa_summary": geometry_qa_payload.get("summary", {}) if geometry_qa_payload else {},
        "transfer_quality_metrics": _extract_quality_metrics(transfer_payload),
        "metrics": metrics,
        "checks": checks,
        "summary": summary,
        "pulse": pulse_summary,
        "artifacts": artifact_paths,
    }

    detail_json_path = output_dir / f"{int(root_id)}_details.json"
    artifact_paths["details_json_path"] = str(detail_json_path.resolve())
    detail_payload["artifacts"] = artifact_paths
    write_json(detail_payload, detail_json_path)

    return {
        "root_id": int(root_id),
        "metrics": metrics,
        "checks": checks,
        "summary": summary,
        "pulse": pulse_summary,
        "boundary": detail_payload["boundary"],
        "counts": detail_payload["counts"],
        "descriptor_summary": descriptor_payload,
        "geometry_qa_summary": detail_payload["geometry_qa_summary"],
        "operator_bundle": detail_payload["operator_bundle"],
        "artifacts": artifact_paths,
    }


def evaluate_operator_qa_metrics(
    *,
    metrics: Mapping[str, float],
    thresholds: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    resolved_thresholds = resolve_operator_qa_thresholds(thresholds)
    checks: dict[str, dict[str, Any]] = {}
    warning_count = 0
    failure_count = 0
    blocking_failure_count = 0

    for metric_name, value in sorted(metrics.items()):
        config = dict(resolved_thresholds.get(metric_name, {}))
        warn_threshold = config.get("warn")
        fail_threshold = config.get("fail")
        blocking = bool(config.get("blocking", False))

        status = "pass"
        if fail_threshold is not None and float(value) > float(fail_threshold):
            status = "fail"
            failure_count += 1
            if blocking:
                blocking_failure_count += 1
        elif warn_threshold is not None and float(value) > float(warn_threshold):
            status = "warn"
            warning_count += 1

        checks[metric_name] = {
            "status": status,
            "value": float(value),
            "warn_threshold": None if warn_threshold is None else float(warn_threshold),
            "fail_threshold": None if fail_threshold is None else float(fail_threshold),
            "blocking": blocking,
            "description": str(config.get("description", "")),
        }

    if failure_count > 0:
        overall_status = "fail"
    elif warning_count > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    milestone10_gate = _milestone10_gate(
        blocking_failure_count=blocking_failure_count,
        failure_count=failure_count,
        warning_count=warning_count,
    )
    summary = {
        "overall_status": overall_status,
        "warning_count": warning_count,
        "failure_count": failure_count,
        "blocking_failure_count": blocking_failure_count,
        "milestone10_gate": milestone10_gate,
        "milestone10_engine_ready": bool(blocking_failure_count == 0),
    }
    return checks, summary


def _milestone10_gate(*, blocking_failure_count: int, failure_count: int, warning_count: int) -> str:
    if int(blocking_failure_count) > 0:
        return "hold"
    if int(failure_count) > 0 or int(warning_count) > 0:
        return "review"
    return "go"


def _run_pulse_smoke(
    *,
    vertices: np.ndarray,
    fine_mass: np.ndarray,
    coarse_mass: np.ndarray,
    fine_operator: sp.csr_matrix,
    coarse_operator: sp.csr_matrix,
    restriction: sp.csr_matrix,
    normalized_restriction: sp.csr_matrix,
    normalized_prolongation: sp.csr_matrix,
    geodesic_neighbor_indptr: np.ndarray,
    geodesic_neighbor_indices: np.ndarray,
    geodesic_neighbor_distances: np.ndarray,
    boundary_vertex_mask: np.ndarray,
    surface_to_patch: np.ndarray,
    step_count: int,
) -> dict[str, Any]:
    seed_vertex = _select_seed_vertex(vertices=vertices, masses=fine_mass, boundary_vertex_mask=boundary_vertex_mask)
    seed_patch = int(surface_to_patch[seed_vertex])
    fine_initial_physical, support_vertex_indices, support_sigma = _build_localized_pulse(
        seed_vertex=seed_vertex,
        fine_mass=fine_mass,
        geodesic_neighbor_indptr=geodesic_neighbor_indptr,
        geodesic_neighbor_indices=geodesic_neighbor_indices,
        geodesic_neighbor_distances=geodesic_neighbor_distances,
    )
    fine_initial_normalized = np.sqrt(fine_mass) * fine_initial_physical
    coarse_initial_normalized = normalized_restriction @ fine_initial_normalized
    coarse_initial_physical = np.divide(
        coarse_initial_normalized,
        np.sqrt(coarse_mass),
        out=np.zeros_like(coarse_initial_normalized),
        where=coarse_mass > EPSILON,
    )

    fine_smoke = _evolve_diffusion_smoke(
        operator=fine_operator,
        mass_diagonal=fine_mass,
        initial_normalized_state=fine_initial_normalized,
        step_count=step_count,
    )
    coarse_smoke = _evolve_diffusion_smoke(
        operator=coarse_operator,
        mass_diagonal=coarse_mass,
        initial_normalized_state=coarse_initial_normalized,
        step_count=step_count,
    )

    restricted_fine_final = normalized_restriction @ fine_smoke["final_normalized_state"]
    prolongated_coarse_final = normalized_prolongation @ coarse_smoke["final_normalized_state"]
    prolongated_coarse_final_physical = np.divide(
        prolongated_coarse_final,
        np.sqrt(fine_mass),
        out=np.zeros_like(prolongated_coarse_final),
        where=fine_mass > EPSILON,
    )
    comparison = {
        "coarse_vs_restricted_fine_residual_relative": _relative_residual(
            coarse_smoke["final_normalized_state"] - restricted_fine_final,
            restricted_fine_final,
        ),
        "fine_vs_prolongated_coarse_residual_relative": _relative_residual(
            fine_smoke["final_normalized_state"] - prolongated_coarse_final,
            fine_smoke["final_normalized_state"],
        ),
    }

    return {
        "seed_vertex": int(seed_vertex),
        "seed_patch": int(seed_patch),
        "step_count": int(step_count),
        "support_vertex_count": int(support_vertex_indices.size),
        "support_sigma": float(support_sigma),
        "support_vertex_indices": support_vertex_indices.tolist(),
        "fine_initial_physical_state": fine_initial_physical,
        "fine_final_physical_state": fine_smoke["final_physical_state"],
        "coarse_final_physical_state": coarse_smoke["final_physical_state"],
        "prolongated_coarse_final_physical_state": prolongated_coarse_final_physical,
        "fine": {
            **fine_smoke["summary"],
        },
        "coarse": {
            **coarse_smoke["summary"],
            "initial_physical_peak": float(np.max(np.abs(coarse_initial_physical))),
        },
        "comparison": comparison,
    }


def _evolve_diffusion_smoke(
    *,
    operator: sp.csr_matrix,
    mass_diagonal: np.ndarray,
    initial_normalized_state: np.ndarray,
    step_count: int,
) -> dict[str, Any]:
    largest_eigenvalue_estimate = _estimate_largest_eigenvalue(operator)
    dt = 1.0 if largest_eigenvalue_estimate <= EPSILON else PULSE_EIGENVALUE_SAFETY / largest_eigenvalue_estimate
    sqrt_mass = np.sqrt(np.asarray(mass_diagonal, dtype=np.float64))
    normalized_state = np.asarray(initial_normalized_state, dtype=np.float64).copy()

    mass_history: list[float] = []
    energy_history: list[float] = []
    l2_history: list[float] = []
    peak_history: list[float] = []

    for step_index in range(int(step_count) + 1):
        physical_state = np.divide(
            normalized_state,
            sqrt_mass,
            out=np.zeros_like(normalized_state),
            where=sqrt_mass > EPSILON,
        )
        mass_history.append(float(sqrt_mass @ normalized_state))
        energy_history.append(float(normalized_state @ (operator @ normalized_state)))
        l2_history.append(float(normalized_state @ normalized_state))
        peak_history.append(float(np.max(np.abs(physical_state))))
        if step_index == int(step_count):
            break
        normalized_state = normalized_state - dt * (operator @ normalized_state)

    final_physical_state = np.divide(
        normalized_state,
        sqrt_mass,
        out=np.zeros_like(normalized_state),
        where=sqrt_mass > EPSILON,
    )
    initial_mass = mass_history[0] if mass_history else 0.0
    initial_energy = energy_history[0] if energy_history else 0.0
    mass_relative_drift = max(abs(value - initial_mass) for value in mass_history) / max(abs(initial_mass), EPSILON)
    energy_increase = 0.0
    if len(energy_history) >= 2:
        energy_increase = max(
            max(energy_history[index + 1] - energy_history[index], 0.0)
            for index in range(len(energy_history) - 1)
        )
    energy_increase_relative = energy_increase / max(abs(initial_energy), EPSILON)

    return {
        "final_normalized_state": normalized_state,
        "final_physical_state": final_physical_state,
        "summary": {
            "largest_eigenvalue_estimate": float(largest_eigenvalue_estimate),
            "dt": float(dt),
            "mass_history": [float(value) for value in mass_history],
            "energy_history": [float(value) for value in energy_history],
            "l2_history": [float(value) for value in l2_history],
            "peak_history": [float(value) for value in peak_history],
            "mass_relative_drift": float(mass_relative_drift),
            "energy_increase_relative": float(energy_increase_relative),
        },
    }


def _build_localized_pulse(
    *,
    seed_vertex: int,
    fine_mass: np.ndarray,
    geodesic_neighbor_indptr: np.ndarray,
    geodesic_neighbor_indices: np.ndarray,
    geodesic_neighbor_distances: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    start = int(geodesic_neighbor_indptr[int(seed_vertex)])
    end = int(geodesic_neighbor_indptr[int(seed_vertex) + 1])
    support_indices = np.asarray(geodesic_neighbor_indices[start:end], dtype=np.int32)
    support_distances = np.asarray(geodesic_neighbor_distances[start:end], dtype=np.float64)
    if support_indices.size == 0:
        support_indices = np.asarray([int(seed_vertex)], dtype=np.int32)
        support_distances = np.asarray([0.0], dtype=np.float64)

    positive_distances = support_distances[support_distances > EPSILON]
    if positive_distances.size == 0:
        sigma = 1.0
    else:
        sigma = max(float(np.median(positive_distances)) * PULSE_RADIUS_SCALE, float(positive_distances.min()))

    pulse = np.zeros(int(fine_mass.shape[0]), dtype=np.float64)
    weights = np.exp(-0.5 * np.square(support_distances / max(sigma, EPSILON)))
    pulse[support_indices] = weights
    normalization = float(fine_mass @ pulse)
    if normalization <= EPSILON:
        pulse[:] = 0.0
        pulse[int(seed_vertex)] = 1.0 / max(float(fine_mass[int(seed_vertex)]), EPSILON)
    else:
        pulse /= normalization
    return pulse, support_indices, float(sigma)


def _select_seed_vertex(*, vertices: np.ndarray, masses: np.ndarray, boundary_vertex_mask: np.ndarray) -> int:
    candidate_indices = np.flatnonzero(~np.asarray(boundary_vertex_mask, dtype=bool))
    if candidate_indices.size == 0:
        candidate_indices = np.arange(vertices.shape[0], dtype=np.int32)
    weights = np.asarray(masses, dtype=np.float64)
    total_weight = float(weights.sum())
    if total_weight <= EPSILON:
        centroid = np.asarray(vertices, dtype=np.float64).mean(axis=0)
    else:
        centroid = np.average(np.asarray(vertices, dtype=np.float64), axis=0, weights=weights)
    distances = np.linalg.norm(np.asarray(vertices[candidate_indices], dtype=np.float64) - centroid[None, :], axis=1)
    return int(candidate_indices[int(np.argmin(distances))])


def _write_root_artifacts(
    *,
    root_id: int,
    output_dir: Path,
    frame: ProjectionFrame,
    vertices: np.ndarray,
    edge_vertex_indices: np.ndarray,
    patch_centroids: np.ndarray,
    patch_adj: sp.csr_matrix,
    surface_to_patch: np.ndarray,
    boundary_vertex_mask: np.ndarray,
    boundary_edge_mask: np.ndarray,
    pulse: Mapping[str, Any],
) -> dict[str, str]:
    artifact_paths = {
        "pulse_initial_svg_path": str((output_dir / f"{root_id}_pulse_initial.svg").resolve()),
        "boundary_mask_svg_path": str((output_dir / f"{root_id}_boundary_mask.svg").resolve()),
        "patch_decomposition_svg_path": str((output_dir / f"{root_id}_patch_decomposition.svg").resolve()),
        "fine_pulse_final_svg_path": str((output_dir / f"{root_id}_fine_pulse_final.svg").resolve()),
        "coarse_pulse_final_svg_path": str((output_dir / f"{root_id}_coarse_pulse_final.svg").resolve()),
        "coarse_reconstruction_svg_path": str((output_dir / f"{root_id}_coarse_reconstruction.svg").resolve()),
        "reconstruction_error_svg_path": str((output_dir / f"{root_id}_reconstruction_error.svg").resolve()),
    }

    Path(artifact_paths["pulse_initial_svg_path"]).write_text(
        _render_surface_scalar_svg(
            frame=frame,
            vertices=vertices,
            edge_vertex_indices=edge_vertex_indices,
            values=np.asarray(pulse["fine_initial_physical_state"], dtype=np.float64),
        ),
        encoding="utf-8",
    )
    Path(artifact_paths["boundary_mask_svg_path"]).write_text(
        _render_boundary_svg(
            frame=frame,
            vertices=vertices,
            edge_vertex_indices=edge_vertex_indices,
            boundary_vertex_mask=np.asarray(boundary_vertex_mask, dtype=bool),
            boundary_edge_mask=np.asarray(boundary_edge_mask, dtype=bool),
        ),
        encoding="utf-8",
    )
    Path(artifact_paths["patch_decomposition_svg_path"]).write_text(
        _render_patch_decomposition_svg(
            frame=frame,
            vertices=vertices,
            edge_vertex_indices=edge_vertex_indices,
            surface_to_patch=np.asarray(surface_to_patch, dtype=np.int32),
            patch_centroids=np.asarray(patch_centroids, dtype=np.float64),
        ),
        encoding="utf-8",
    )
    Path(artifact_paths["fine_pulse_final_svg_path"]).write_text(
        _render_surface_scalar_svg(
            frame=frame,
            vertices=vertices,
            edge_vertex_indices=edge_vertex_indices,
            values=np.asarray(pulse["fine_final_physical_state"], dtype=np.float64),
        ),
        encoding="utf-8",
    )
    Path(artifact_paths["coarse_pulse_final_svg_path"]).write_text(
        _render_patch_scalar_svg(
            frame=frame,
            patch_centroids=np.asarray(patch_centroids, dtype=np.float64),
            patch_adj=patch_adj,
            values=np.asarray(pulse["coarse_final_physical_state"], dtype=np.float64),
        ),
        encoding="utf-8",
    )
    Path(artifact_paths["coarse_reconstruction_svg_path"]).write_text(
        _render_surface_scalar_svg(
            frame=frame,
            vertices=vertices,
            edge_vertex_indices=edge_vertex_indices,
            values=np.asarray(pulse["prolongated_coarse_final_physical_state"], dtype=np.float64),
        ),
        encoding="utf-8",
    )
    Path(artifact_paths["reconstruction_error_svg_path"]).write_text(
        _render_surface_scalar_svg(
            frame=frame,
            vertices=vertices,
            edge_vertex_indices=edge_vertex_indices,
            values=np.abs(
                np.asarray(pulse["fine_final_physical_state"], dtype=np.float64)
                - np.asarray(pulse["prolongated_coarse_final_physical_state"], dtype=np.float64)
            ),
        ),
        encoding="utf-8",
    )
    return artifact_paths


def _render_surface_scalar_svg(
    *,
    frame: ProjectionFrame,
    vertices: np.ndarray,
    edge_vertex_indices: np.ndarray,
    values: np.ndarray,
) -> str:
    projected, depth = _project_points(vertices, frame)
    edge_elements = _svg_edge_elements(projected, edge_vertex_indices, stroke="#cbd5e1", stroke_width=1.0, opacity=0.95)
    point_elements = _svg_point_elements(
        projected=projected,
        depth=depth,
        values=np.asarray(values, dtype=np.float64),
        radius=4.2,
    )
    return _wrap_svg(edge_elements + point_elements)


def _render_boundary_svg(
    *,
    frame: ProjectionFrame,
    vertices: np.ndarray,
    edge_vertex_indices: np.ndarray,
    boundary_vertex_mask: np.ndarray,
    boundary_edge_mask: np.ndarray,
) -> str:
    projected, depth = _project_points(vertices, frame)
    all_edges = _svg_edge_elements(projected, edge_vertex_indices, stroke="#dbe4f0", stroke_width=1.0, opacity=0.9)
    boundary_edges = _svg_edge_elements(
        projected,
        edge_vertex_indices[np.asarray(boundary_edge_mask, dtype=bool)],
        stroke="#b91c1c",
        stroke_width=2.6,
        opacity=1.0,
    )
    values = np.where(np.asarray(boundary_vertex_mask, dtype=bool), 1.0, 0.0)
    points = _svg_point_elements(projected=projected, depth=depth, values=values, radius=4.4, boundary_mode=True)
    return _wrap_svg(all_edges + boundary_edges + points)


def _render_patch_decomposition_svg(
    *,
    frame: ProjectionFrame,
    vertices: np.ndarray,
    edge_vertex_indices: np.ndarray,
    surface_to_patch: np.ndarray,
    patch_centroids: np.ndarray,
) -> str:
    projected_vertices, vertex_depth = _project_points(vertices, frame)
    projected_centroids, centroid_depth = _project_points(patch_centroids, frame)
    edge_elements = _svg_edge_elements(
        projected_vertices,
        edge_vertex_indices,
        stroke="#e2e8f0",
        stroke_width=1.0,
        opacity=0.9,
    )
    point_elements = _svg_patch_point_elements(
        projected=projected_vertices,
        depth=vertex_depth,
        patch_indices=np.asarray(surface_to_patch, dtype=np.int32),
        radius=3.8,
    )
    centroid_elements = _svg_patch_point_elements(
        projected=projected_centroids,
        depth=centroid_depth,
        patch_indices=np.arange(patch_centroids.shape[0], dtype=np.int32),
        radius=7.0,
        stroke="#0f172a",
    )
    return _wrap_svg(edge_elements + point_elements + centroid_elements)


def _render_patch_scalar_svg(
    *,
    frame: ProjectionFrame,
    patch_centroids: np.ndarray,
    patch_adj: sp.csr_matrix,
    values: np.ndarray,
) -> str:
    projected, depth = _project_points(patch_centroids, frame)
    edge_indices = _csr_edges(patch_adj)
    edge_elements = _svg_edge_elements(projected, edge_indices, stroke="#cbd5e1", stroke_width=1.3, opacity=0.95)
    point_elements = _svg_point_elements(projected=projected, depth=depth, values=np.asarray(values), radius=8.0)
    return _wrap_svg(edge_elements + point_elements)


def _render_report_html(*, root_entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    root_sections = "\n".join(_render_root_html(entry) for entry in root_entries)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Offline Operator QA Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #475569;
      --line: #cbd5e1;
      --pass: #166534;
      --warn: #9a3412;
      --fail: #991b1b;
      --hold: #991b1b;
      --review: #9a3412;
      --go: #166534;
    }}
    body {{
      margin: 0;
      padding: 28px;
      background: linear-gradient(180deg, #eff6ff 0%, var(--bg) 28%, #f8fafc 100%);
      color: var(--ink);
      font: 15px/1.5 "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: 0 20px 40px rgba(15, 23, 42, 0.06);
      padding: 20px 22px;
      margin-bottom: 20px;
    }}
    h1, h2, h3 {{
      margin: 0 0 10px 0;
    }}
    p {{
      margin: 0 0 10px 0;
      color: var(--muted);
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    .summary-item {{
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 14px;
    }}
    .panels {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    figure {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
      background: #fff;
    }}
    figure img {{
      display: block;
      width: 100%;
      height: auto;
      background: #fff;
    }}
    figcaption {{
      padding: 10px 12px;
      border-top: 1px solid var(--line);
      background: #f8fafc;
      color: var(--muted);
      font-size: 13px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
      font-size: 13px;
    }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
    }}
    .status-pass {{ color: var(--pass); font-weight: 700; }}
    .status-warn {{ color: var(--warn); font-weight: 700; }}
    .status-fail {{ color: var(--fail); font-weight: 700; }}
    .gate-go {{ color: var(--go); font-weight: 700; }}
    .gate-review {{ color: var(--review); font-weight: 700; }}
    .gate-hold {{ color: var(--hold); font-weight: 700; }}
    code {{
      font-family: "SFMono-Regular", Menlo, Consolas, monospace;
      font-size: 0.95em;
    }}
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>Offline Operator QA Report</h1>
      <p>This report runs entirely on local Milestone 6 bundles. Treat <code>milestone10_gate=hold</code> as a stop for engine work, <code>review</code> as a human-inspection gate, and <code>go</code> as a clean pre-engine operator check.</p>
      <div class="summary-grid">
        <div class="summary-item"><strong>Overall status</strong><br><span class="status-{html.escape(summary['overall_status'])}">{html.escape(summary['overall_status'])}</span></div>
        <div class="summary-item"><strong>Milestone 10 gate</strong><br><span class="gate-{html.escape(summary['milestone10_gate'])}">{html.escape(summary['milestone10_gate'])}</span></div>
        <div class="summary-item"><strong>Roots</strong><br>{int(summary['root_count'])}</div>
        <div class="summary-item"><strong>Blocking failures</strong><br>{int(summary['blocking_failure_count'])}</div>
        <div class="summary-item"><strong>Warnings</strong><br>{int(summary['warning_count'])}</div>
        <div class="summary-item"><strong>Output directory</strong><br><code>{html.escape(summary['output_dir'])}</code></div>
      </div>
    </section>
    {root_sections}
  </main>
</body>
</html>
"""


def _render_root_html(entry: Mapping[str, Any]) -> str:
    summary = entry["summary"]
    pulse = entry["pulse"]
    checks_rows = "\n".join(_render_check_row(metric_name, check) for metric_name, check in entry["checks"].items())
    panel_specs = [
        ("Pulse Initialization", entry["artifacts"]["pulse_initial_svg_path"], "Localized fine-surface pulse used to initialize the smoke evolution."),
        ("Boundary Mask", entry["artifacts"]["boundary_mask_svg_path"], "Open-boundary vertices and edges highlighted on the simplified surface mesh."),
        ("Patch Decomposition", entry["artifacts"]["patch_decomposition_svg_path"], "Surface vertices colored by coarse patch membership."),
        ("Fine Pulse After Smoke Evolution", entry["artifacts"]["fine_pulse_final_svg_path"], "Fine pulse after the stability-oriented explicit diffusion smoke loop."),
        ("Coarse Pulse After Smoke Evolution", entry["artifacts"]["coarse_pulse_final_svg_path"], "Coarse pulse on the patch graph after the matching smoke loop."),
        ("Coarse Reconstruction On Fine Surface", entry["artifacts"]["coarse_reconstruction_svg_path"], "Prolongated coarse pulse reconstructed back onto the fine surface."),
        ("Reconstruction Error", entry["artifacts"]["reconstruction_error_svg_path"], "Absolute fine-versus-prolongated-coarse difference after the smoke loop."),
    ]
    panels_html = "\n".join(
        f"<figure><img src=\"{html.escape(Path(path).name)}\" alt=\"{html.escape(title)}\"><figcaption><strong>{html.escape(title)}</strong><br>{html.escape(caption)}</figcaption></figure>"
        for title, path, caption in panel_specs
    )
    return f"""
    <section class="card">
      <h2>Root {int(entry['root_id'])}</h2>
      <p>Fine family <code>{html.escape(entry['operator_bundle']['discretization_family'])}</code>, boundary mode <code>{html.escape(entry['operator_bundle']['boundary_condition_mode'])}</code>, anisotropy <code>{html.escape(entry['operator_bundle']['anisotropy_model'])}</code>.</p>
      <div class="summary-grid">
        <div class="summary-item"><strong>Overall status</strong><br><span class="status-{html.escape(summary['overall_status'])}">{html.escape(summary['overall_status'])}</span></div>
        <div class="summary-item"><strong>Milestone 10 gate</strong><br><span class="gate-{html.escape(summary['milestone10_gate'])}">{html.escape(summary['milestone10_gate'])}</span></div>
        <div class="summary-item"><strong>Boundary vertices</strong><br>{int(entry['boundary']['boundary_vertex_count'])}</div>
        <div class="summary-item"><strong>Patches</strong><br>{int(entry['counts']['patch_count'])}</div>
        <div class="summary-item"><strong>Pulse seed</strong><br>vertex {int(pulse['seed_vertex'])}, patch {int(pulse['seed_patch'])}</div>
        <div class="summary-item"><strong>Smoke steps / dt</strong><br>{int(pulse['step_count'])} steps, fine dt {float(pulse['fine']['dt']):.4g}</div>
      </div>
      <div class="panels">
        {panels_html}
      </div>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Status</th>
            <th>Warn</th>
            <th>Fail</th>
            <th>Blocking</th>
            <th>Why it matters</th>
          </tr>
        </thead>
        <tbody>
          {checks_rows}
        </tbody>
      </table>
    </section>
    """


def _render_report_markdown(*, root_entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Offline Operator QA Report",
        "",
        "Treat `milestone10_gate=hold` as a stop for Milestone 10 engine work. `review` means the bundles still need human inspection before they become the engine baseline.",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Milestone 10 gate: `{summary['milestone10_gate']}`",
        f"- Root count: `{summary['root_count']}`",
        f"- Output dir: `{summary['output_dir']}`",
        "",
    ]
    for entry in root_entries:
        lines.extend(
            [
                f"## Root {entry['root_id']}",
                "",
                f"- Overall status: `{entry['summary']['overall_status']}`",
                f"- Milestone 10 gate: `{entry['summary']['milestone10_gate']}`",
                f"- Boundary vertices: `{entry['boundary']['boundary_vertex_count']}`",
                f"- Pulse seed: `vertex {entry['pulse']['seed_vertex']}`, `patch {entry['pulse']['seed_patch']}`",
                f"- Smoke steps: `{entry['pulse']['step_count']}`",
                f"- Fine discretization: `{entry['operator_bundle']['discretization_family']}`",
                "",
                "### Key Checks",
                "",
            ]
        )
        for metric_name, check in entry["checks"].items():
            lines.append(f"- `{metric_name}`: `{check['value']:.6g}` -> `{check['status']}`")
        lines.extend(
            [
                "",
                "### Panels",
                "",
                f"![Pulse Initialization]({Path(entry['artifacts']['pulse_initial_svg_path']).name})",
                "",
                f"![Boundary Mask]({Path(entry['artifacts']['boundary_mask_svg_path']).name})",
                "",
                f"![Patch Decomposition]({Path(entry['artifacts']['patch_decomposition_svg_path']).name})",
                "",
                f"![Fine Pulse After Smoke Evolution]({Path(entry['artifacts']['fine_pulse_final_svg_path']).name})",
                "",
                f"![Coarse Pulse After Smoke Evolution]({Path(entry['artifacts']['coarse_pulse_final_svg_path']).name})",
                "",
                f"![Coarse Reconstruction]({Path(entry['artifacts']['coarse_reconstruction_svg_path']).name})",
                "",
                f"![Reconstruction Error]({Path(entry['artifacts']['reconstruction_error_svg_path']).name})",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_check_row(metric_name: str, check: Mapping[str, Any]) -> str:
    warn_threshold = check["warn_threshold"]
    fail_threshold = check["fail_threshold"]
    return (
        "<tr>"
        f"<td><code>{html.escape(metric_name)}</code></td>"
        f"<td>{float(check['value']):.6g}</td>"
        f'<td class="status-{html.escape(str(check["status"]))}">{html.escape(str(check["status"]))}</td>'
        f"<td>{'' if warn_threshold is None else f'{float(warn_threshold):.6g}'}</td>"
        f"<td>{'' if fail_threshold is None else f'{float(fail_threshold):.6g}'}</td>"
        f"<td>{'yes' if bool(check['blocking']) else 'no'}</td>"
        f"<td>{html.escape(str(check['description']))}</td>"
        "</tr>"
    )


def _pulse_summary_payload(pulse: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "seed_vertex": int(pulse["seed_vertex"]),
        "seed_patch": int(pulse["seed_patch"]),
        "step_count": int(pulse["step_count"]),
        "support_vertex_count": int(pulse["support_vertex_count"]),
        "support_sigma": float(pulse["support_sigma"]),
        "support_vertex_indices": list(pulse["support_vertex_indices"]),
        "fine": {
            key: value
            for key, value in pulse["fine"].items()
        },
        "coarse": {
            key: value
            for key, value in pulse["coarse"].items()
        },
        "comparison": {
            key: float(value)
            for key, value in pulse["comparison"].items()
        },
    }


def _build_projection_frame(point_sets: Iterable[np.ndarray]) -> ProjectionFrame:
    point_clouds = [np.asarray(points, dtype=np.float64) for points in point_sets if np.asarray(points).size > 0]
    if not point_clouds:
        raise ValueError("Projection frame requires at least one non-empty point set.")

    stacked = np.vstack(point_clouds)
    center = stacked.mean(axis=0)
    rotation = _rotation_matrix()
    rotated = (stacked - center[None, :]) @ rotation.T
    xy = rotated[:, :2]
    xy_min = xy.min(axis=0)
    xy_max = xy.max(axis=0)
    extent = np.maximum(xy_max - xy_min, 1.0)
    scale_x = max(float(SVG_WIDTH) - 2.0 * SVG_PADDING, 1.0) / float(extent[0])
    scale_y = max(float(SVG_HEIGHT) - 2.0 * SVG_PADDING, 1.0) / float(extent[1])
    scale = min(scale_x, scale_y)
    return ProjectionFrame(
        rotation=rotation,
        center=center,
        xy_min=xy_min,
        xy_max=xy_max,
        scale=float(scale),
    )


def _rotation_matrix() -> np.ndarray:
    z_radians = math.radians(ROTATION_Z_DEGREES)
    x_radians = math.radians(ROTATION_X_DEGREES)
    rotate_z = np.asarray(
        [
            [math.cos(z_radians), -math.sin(z_radians), 0.0],
            [math.sin(z_radians), math.cos(z_radians), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    rotate_x = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(x_radians), -math.sin(x_radians)],
            [0.0, math.sin(x_radians), math.cos(x_radians)],
        ],
        dtype=np.float64,
    )
    return rotate_x @ rotate_z


def _project_points(points: np.ndarray, frame: ProjectionFrame) -> tuple[np.ndarray, np.ndarray]:
    rotated = (np.asarray(points, dtype=np.float64) - frame.center[None, :]) @ frame.rotation.T
    x = SVG_PADDING + (rotated[:, 0] - frame.xy_min[0]) * frame.scale
    y = SVG_HEIGHT - SVG_PADDING - (rotated[:, 1] - frame.xy_min[1]) * frame.scale
    return np.column_stack([x, y]), rotated[:, 2]


def _svg_edge_elements(
    projected: np.ndarray,
    edge_vertex_indices: np.ndarray,
    *,
    stroke: str,
    stroke_width: float,
    opacity: float,
) -> str:
    if edge_vertex_indices.size == 0:
        return ""
    lines: list[str] = []
    for i, j in np.asarray(edge_vertex_indices, dtype=np.int32):
        start = projected[int(i)]
        end = projected[int(j)]
        lines.append(
            f'<line x1="{start[0]:.3f}" y1="{start[1]:.3f}" x2="{end[0]:.3f}" y2="{end[1]:.3f}" '
            f'stroke="{stroke}" stroke-width="{stroke_width:.2f}" opacity="{opacity:.3f}" />'
        )
    return "".join(lines)


def _svg_point_elements(
    *,
    projected: np.ndarray,
    depth: np.ndarray,
    values: np.ndarray,
    radius: float,
    boundary_mode: bool = False,
) -> str:
    if projected.shape[0] == 0:
        return ""
    order = np.argsort(np.asarray(depth, dtype=np.float64))
    values = np.asarray(values, dtype=np.float64)
    vmin = float(values.min()) if values.size else 0.0
    vmax = float(values.max()) if values.size else 1.0
    circles: list[str] = []
    for index in order:
        value = float(values[int(index)])
        color = _boundary_color(value) if boundary_mode else _sequential_color(value, vmin=vmin, vmax=vmax)
        point = projected[int(index)]
        circles.append(
            f'<circle cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="{radius:.2f}" fill="{color}" '
            'stroke="#0f172a" stroke-width="0.55" />'
        )
    return "".join(circles)


def _svg_patch_point_elements(
    *,
    projected: np.ndarray,
    depth: np.ndarray,
    patch_indices: np.ndarray,
    radius: float,
    stroke: str = "#ffffff",
) -> str:
    if projected.shape[0] == 0:
        return ""
    order = np.argsort(np.asarray(depth, dtype=np.float64))
    circles: list[str] = []
    for index in order:
        point = projected[int(index)]
        color = _patch_color(int(patch_indices[int(index)]))
        circles.append(
            f'<circle cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="{radius:.2f}" fill="{color}" '
            f'stroke="{stroke}" stroke-width="0.65" />'
        )
    return "".join(circles)


def _wrap_svg(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" '
        f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"><rect width="100%" height="100%" fill="#ffffff"/>'
        f"{body}</svg>"
    )


def _patch_color(patch_index: int) -> str:
    if patch_index < len(REPORT_PALETTE):
        return REPORT_PALETTE[patch_index]
    hue = (0.61803398875 * float(patch_index % 377)) % 1.0
    red, green, blue = _hsv_to_rgb(hue, 0.68, 0.76)
    return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"


def _boundary_color(value: float) -> str:
    return "#b91c1c" if value > 0.5 else "#94a3b8"


def _sequential_color(value: float, *, vmin: float, vmax: float) -> str:
    if not math.isfinite(value):
        return "#64748b"
    if vmax <= vmin + EPSILON:
        t = 1.0 if value > 0.0 else 0.0
    else:
        t = min(max((float(value) - float(vmin)) / (float(vmax) - float(vmin)), 0.0), 1.0)
    stops = [
        (248, 250, 252),
        (125, 211, 252),
        (14, 116, 144),
        (8, 47, 73),
    ]
    scaled = t * float(len(stops) - 1)
    lower = int(math.floor(scaled))
    upper = min(lower + 1, len(stops) - 1)
    frac = scaled - float(lower)
    red = (1.0 - frac) * stops[lower][0] + frac * stops[upper][0]
    green = (1.0 - frac) * stops[lower][1] + frac * stops[upper][1]
    blue = (1.0 - frac) * stops[lower][2] + frac * stops[upper][2]
    return f"#{int(red):02x}{int(green):02x}{int(blue):02x}"


def _hsv_to_rgb(hue: float, saturation: float, value: float) -> tuple[float, float, float]:
    hue = hue % 1.0
    sector = int(hue * 6.0)
    fraction = hue * 6.0 - sector
    p_value = value * (1.0 - saturation)
    q_value = value * (1.0 - fraction * saturation)
    t_value = value * (1.0 - (1.0 - fraction) * saturation)
    sector %= 6
    if sector == 0:
        return value, t_value, p_value
    if sector == 1:
        return q_value, value, p_value
    if sector == 2:
        return p_value, value, t_value
    if sector == 3:
        return p_value, q_value, value
    if sector == 4:
        return t_value, p_value, value
    return value, p_value, q_value


def _extract_quality_metrics(payload: Mapping[str, Any]) -> dict[str, float]:
    return {
        key[len("quality_") :]: float(value)
        for key, value in sorted(payload.items())
        if key.startswith("quality_")
    }


def _estimate_largest_eigenvalue(operator: sp.csr_matrix) -> float:
    if operator.shape[0] == 0:
        return 0.0
    if operator.shape[0] <= 16:
        return float(np.max(np.linalg.eigvalsh(operator.toarray())))
    try:
        eigenvalue = eigsh(operator, k=1, which="LA", return_eigenvectors=False, tol=1.0e-5)
        return float(max(eigenvalue[0], 0.0))
    except Exception:
        vector = np.linspace(1.0, 2.0, operator.shape[0], dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        if norm <= EPSILON:
            return 0.0
        vector /= norm
        estimate = 0.0
        for _ in range(20):
            image = operator @ vector
            image_norm = float(np.linalg.norm(image))
            if image_norm <= EPSILON:
                return 0.0
            vector = image / image_norm
            estimate = float(vector @ (operator @ vector))
        return max(estimate, 0.0)


def _load_npz_payload(path: str | Path) -> dict[str, np.ndarray]:
    npz_path = Path(path)
    with np.load(npz_path, allow_pickle=False) as payload:
        return {key: payload[key] for key in payload.files}


def _load_json_if_exists(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8"))


def _require_path(path: str | Path) -> None:
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Missing required operator QA input: {resolved}")


def _normalize_root_ids(root_ids: Iterable[int]) -> list[int]:
    normalized = sorted({int(root_id) for root_id in root_ids})
    if not normalized:
        raise ValueError("At least one root ID is required for operator QA generation.")
    return normalized


def _relative_residual(delta: np.ndarray, reference: np.ndarray) -> float:
    numerator = float(np.linalg.norm(np.asarray(delta, dtype=np.float64)))
    denominator = float(np.linalg.norm(np.asarray(reference, dtype=np.float64)))
    if denominator <= EPSILON:
        return 0.0 if numerator <= EPSILON else float("inf")
    return numerator / denominator


def _sparse_max_abs(matrix: sp.spmatrix) -> float:
    csr = matrix.tocsr()
    if csr.nnz == 0:
        return 0.0
    return float(np.max(np.abs(csr.data)))


def _csr_edges(matrix: sp.spmatrix) -> np.ndarray:
    csr = matrix.tocsr()
    rows: list[tuple[int, int]] = []
    for row_index in range(csr.shape[0]):
        start = int(csr.indptr[row_index])
        end = int(csr.indptr[row_index + 1])
        for col_index in csr.indices[start:end]:
            if row_index < int(col_index):
                rows.append((row_index, int(col_index)))
    if not rows:
        return np.empty((0, 2), dtype=np.int32)
    return np.asarray(rows, dtype=np.int32)


def _fraction(numerator: int, denominator: int) -> float:
    if int(denominator) <= 0:
        return 0.0
    return float(numerator) / float(denominator)
