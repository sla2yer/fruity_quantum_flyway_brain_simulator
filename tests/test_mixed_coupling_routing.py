from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.coupling_assembly import (
    ANCHOR_COLUMN_TYPES,
    CLOUD_COLUMN_TYPES,
    COMPONENT_COLUMN_TYPES,
    COMPONENT_SYNAPSE_COLUMN_TYPES,
    EdgeCouplingBundle,
)
from flywire_wave.coupling_contract import (
    DEFAULT_AGGREGATION_RULE,
    DEFAULT_DELAY_REPRESENTATION,
    DEFAULT_SIGN_REPRESENTATION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
)
from flywire_wave.hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from flywire_wave.hybrid_morphology_runtime import (
    PointNeuronState,
    SkeletonGraphState,
    resolve_morphology_runtime_from_arm_plan,
    run_morphology_runtime_shared_schedule,
)
from flywire_wave.surface_wave_solver import SurfaceWaveState
from flywire_wave.synapse_mapping import _write_edge_coupling_bundle_npz
try:
    from tests.test_hybrid_morphology_runtime import _build_surface_skeleton_arm_plan
except ModuleNotFoundError:
    from test_hybrid_morphology_runtime import _build_surface_skeleton_arm_plan


class MixedCouplingRoutingTest(unittest.TestCase):
    def test_surface_to_skeleton_route_preserves_delay_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(tmp_dir)
            _set_sample_count(arm_plan, sample_count=2)
            edge_path = tmp_dir / "edges" / "101__to__202_surface_to_skeleton.npz"
            _write_route_edge_bundle(
                edge_bundle_path=edge_path,
                pre_root_id=101,
                post_root_id=202,
                source_anchor=_surface_anchor(root_id=101, anchor_index=0, x=0.0),
                target_anchor=_skeleton_anchor(root_id=202, node_id=2, x=1.0),
                signed_weight_total=1.5,
                delay_ms=1.0,
                sign_label="excitatory",
            )
            arm_plan["model_configuration"]["surface_wave_execution_plan"][
                "selected_root_coupling_assets"
            ][0]["selected_edge_bundle_paths"] = [
                {
                    "pre_root_id": 101,
                    "post_root_id": 202,
                    "path": str(edge_path.resolve()),
                }
            ]

            runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            _, result = run_morphology_runtime_shared_schedule(
                runtime,
                drive_values=np.zeros((2, 2), dtype=np.float64),
                initial_states_by_root={
                    101: SurfaceWaveState(
                        resolution="surface",
                        activation=np.asarray([2.0, 0.0], dtype=np.float64),
                        velocity=np.zeros(2, dtype=np.float64),
                    ),
                    202: SkeletonGraphState.zeros(3),
                },
            )

            family = _family_by_route(
                result.descriptor.coupling_metadata["component_families"],
                "surface_patch_projection_to_skeleton_node_injection",
            )
            self.assertEqual(family["source_morphology_class"], SURFACE_NEURON_CLASS)
            self.assertEqual(family["target_morphology_class"], SKELETON_NEURON_CLASS)
            self.assertEqual(family["blocked_reasons"], [])

            event = _event_by_route(
                result.coupling_application_history,
                "surface_patch_projection_to_skeleton_node_injection",
            )
            self.assertEqual(event["delay_steps"], 1)
            self.assertEqual(event["target_shared_step_index"], 1)
            self.assertEqual(event["source_step_index"], 0)
            self.assertEqual(event["source_local_indices"], [0])
            self.assertEqual(event["target_local_indices"], [1])
            self.assertEqual(event["source_projection_values"], [2.0])
            self.assertAlmostEqual(event["source_value"], 2.0)
            self.assertAlmostEqual(event["signed_source_value"], 3.0)
            self.assertEqual(event["target_projection_drive"], [3.0])

    def test_skeleton_to_point_route_updates_point_state_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(tmp_dir, include_point_root=True)
            _set_sample_count(arm_plan, sample_count=1)
            edge_path = tmp_dir / "edges" / "202__to__303_skeleton_to_point.npz"
            _write_route_edge_bundle(
                edge_bundle_path=edge_path,
                pre_root_id=202,
                post_root_id=303,
                source_anchor=_skeleton_anchor(root_id=202, node_id=2, x=1.0),
                target_anchor=_point_anchor(root_id=303, x=0.0),
                signed_weight_total=1.0,
                delay_ms=0.0,
                sign_label="excitatory",
            )
            arm_plan["model_configuration"]["surface_wave_execution_plan"][
                "selected_root_skeleton_assets"
            ][0]["selected_edge_bundle_paths"] = [
                {
                    "pre_root_id": 202,
                    "post_root_id": 303,
                    "path": str(edge_path.resolve()),
                }
            ]

            runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            _, result = run_morphology_runtime_shared_schedule(
                runtime,
                drive_values=np.zeros((1, 3), dtype=np.float64),
                initial_states_by_root={
                    202: SkeletonGraphState(
                        resolution="skeleton_graph",
                        activation=np.asarray([0.0, 3.0, 0.0], dtype=np.float64),
                        velocity=np.zeros(3, dtype=np.float64),
                    ),
                    303: PointNeuronState.zeros(),
                },
            )

            event = _event_by_route(
                result.coupling_application_history,
                "skeleton_node_projection_to_point_state_injection",
            )
            self.assertEqual(event["delay_steps"], 0)
            self.assertEqual(event["source_local_indices"], [1])
            self.assertEqual(event["target_local_indices"], [0])
            self.assertAlmostEqual(event["source_value"], 3.0)
            self.assertAlmostEqual(event["signed_source_value"], 3.0)
            self.assertEqual(event["target_projection_drive"], [3.0])
            self.assertAlmostEqual(
                result.coupling_projection_history_by_root[303][1, 0],
                1.5,
                places=9,
            )

    def test_point_to_surface_route_records_inhibitory_patch_injection(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(tmp_dir, include_point_root=True)
            _set_sample_count(arm_plan, sample_count=1)
            edge_path = tmp_dir / "edges" / "303__to__101_point_to_surface.npz"
            _write_route_edge_bundle(
                edge_bundle_path=edge_path,
                pre_root_id=303,
                post_root_id=101,
                source_anchor=_point_anchor(root_id=303, x=0.0),
                target_anchor=_surface_anchor(root_id=101, anchor_index=1, x=1.0),
                signed_weight_total=-0.5,
                delay_ms=0.0,
                sign_label="inhibitory",
            )
            arm_plan["model_configuration"]["surface_wave_execution_plan"]["mixed_fidelity"][
                "per_root_assignments"
            ][0]["coupling_asset"]["selected_edge_bundle_paths"] = [
                {
                    "pre_root_id": 303,
                    "post_root_id": 101,
                    "path": str(edge_path.resolve()),
                }
            ]

            runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            _, result = run_morphology_runtime_shared_schedule(
                runtime,
                drive_values=np.zeros((1, 3), dtype=np.float64),
                initial_states_by_root={
                    101: SurfaceWaveState(
                        resolution="surface",
                        activation=np.zeros(2, dtype=np.float64),
                        velocity=np.zeros(2, dtype=np.float64),
                    ),
                    303: PointNeuronState(
                        resolution="point_state",
                        activation=np.asarray([4.0], dtype=np.float64),
                        velocity=np.zeros(1, dtype=np.float64),
                    ),
                },
            )

            family = _family_by_route(
                result.descriptor.coupling_metadata["component_families"],
                "point_state_projection_to_surface_patch_injection",
            )
            self.assertEqual(family["source_morphology_class"], POINT_NEURON_CLASS)
            self.assertEqual(family["target_morphology_class"], SURFACE_NEURON_CLASS)

            event = _event_by_route(
                result.coupling_application_history,
                "point_state_projection_to_surface_patch_injection",
            )
            self.assertEqual(event["sign_label"], "inhibitory")
            self.assertEqual(event["source_local_indices"], [0])
            self.assertEqual(event["target_local_indices"], [1])
            self.assertAlmostEqual(event["source_value"], 4.0)
            self.assertAlmostEqual(event["signed_source_value"], -2.0)
            self.assertEqual(event["target_projection_drive"], [-2.0])

    def test_unsupported_anchor_mode_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(tmp_dir)
            edge_path = tmp_dir / "edges" / "202__to__101_invalid_anchor.npz"
            _write_route_edge_bundle(
                edge_bundle_path=edge_path,
                pre_root_id=202,
                post_root_id=101,
                source_anchor=_point_anchor(root_id=202, x=0.0),
                target_anchor=_surface_anchor(root_id=101, anchor_index=0, x=0.0),
                signed_weight_total=1.0,
                delay_ms=0.0,
                sign_label="excitatory",
            )
            arm_plan["model_configuration"]["surface_wave_execution_plan"][
                "selected_root_skeleton_assets"
            ][0]["selected_edge_bundle_paths"] = [
                {
                    "pre_root_id": 202,
                    "post_root_id": 101,
                    "path": str(edge_path.resolve()),
                }
            ]

            with self.assertRaises(ValueError) as ctx:
                resolve_morphology_runtime_from_arm_plan(arm_plan)
            self.assertIn("requires presynaptic anchor_mode", str(ctx.exception))


def _set_sample_count(arm_plan: dict[str, object], *, sample_count: int) -> None:
    timebase = arm_plan["runtime"]["timebase"]
    timebase["sample_count"] = int(sample_count)
    timebase["duration_ms"] = float(sample_count)


def _surface_anchor(*, root_id: int, anchor_index: int, x: float) -> dict[str, object]:
    return {
        "anchor_table_index": 0,
        "root_id": int(root_id),
        "anchor_mode": "surface_patch_cloud",
        "anchor_type": "surface_patch",
        "anchor_resolution": "coarse_patch",
        "anchor_index": int(anchor_index),
        "anchor_x": float(x),
        "anchor_y": 0.0,
        "anchor_z": 0.0,
    }


def _skeleton_anchor(*, root_id: int, node_id: int, x: float) -> dict[str, object]:
    return {
        "anchor_table_index": 0,
        "root_id": int(root_id),
        "anchor_mode": "skeleton_segment_cloud",
        "anchor_type": "skeleton_node",
        "anchor_resolution": "skeleton_node",
        "anchor_index": int(node_id),
        "anchor_x": float(x),
        "anchor_y": 0.0,
        "anchor_z": 0.0,
    }


def _point_anchor(*, root_id: int, x: float) -> dict[str, object]:
    return {
        "anchor_table_index": 0,
        "root_id": int(root_id),
        "anchor_mode": "point_neuron_lumped",
        "anchor_type": "point_state",
        "anchor_resolution": "lumped_root_state",
        "anchor_index": 0,
        "anchor_x": float(x),
        "anchor_y": 0.0,
        "anchor_z": 0.0,
    }


def _write_route_edge_bundle(
    *,
    edge_bundle_path: Path,
    pre_root_id: int,
    post_root_id: int,
    source_anchor: dict[str, object],
    target_anchor: dict[str, object],
    signed_weight_total: float,
    delay_ms: float,
    sign_label: str,
) -> None:
    source_anchor_table = pd.DataFrame.from_records(
        [copy.deepcopy(source_anchor)],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    target_anchor_table = pd.DataFrame.from_records(
        [copy.deepcopy(target_anchor)],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    component_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "component_id": f"{int(pre_root_id)}__to__{int(post_root_id)}__component_0000",
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "pre_anchor_mode": str(source_anchor["anchor_mode"]),
                "post_anchor_mode": str(target_anchor["anchor_mode"]),
                "sign_label": str(sign_label),
                "sign_polarity": 1 if signed_weight_total > 0.0 else -1 if signed_weight_total < 0.0 else 0,
                "sign_representation": DEFAULT_SIGN_REPRESENTATION,
                "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                "delay_model": "fixture_delay_model",
                "delay_ms": float(delay_ms),
                "delay_bin_index": int(delay_ms),
                "delay_bin_label": f"delay_{delay_ms:.1f}",
                "delay_bin_start_ms": float(delay_ms),
                "delay_bin_end_ms": float(delay_ms),
                "aggregation_rule": DEFAULT_AGGREGATION_RULE,
                "source_anchor_count": 1,
                "target_anchor_count": 1,
                "synapse_count": 1,
                "signed_weight_total": float(signed_weight_total),
                "absolute_weight_total": float(abs(signed_weight_total)),
                "confidence_sum": 1.0,
                "confidence_mean": 1.0,
                "source_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "target_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "source_normalization_total": 1.0,
                "target_normalization_total": 1.0,
            }
        ],
        columns=list(COMPONENT_COLUMN_TYPES),
    )
    source_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    target_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    component_synapse_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "synapse_row_id": "fixture#0",
                "source_row_number": 1,
                "synapse_id": "fixture-0",
                "sign_label": str(sign_label),
                "signed_weight": float(signed_weight_total),
                "absolute_weight": float(abs(signed_weight_total)),
                "delay_ms": float(delay_ms),
                "delay_bin_index": int(delay_ms),
                "delay_bin_label": f"delay_{delay_ms:.1f}",
            }
        ],
        columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES),
    )
    empty_synapse_table = pd.DataFrame()
    bundle = EdgeCouplingBundle(
        pre_root_id=int(pre_root_id),
        post_root_id=int(post_root_id),
        status="ready",
        topology_family=DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        kernel_family=SEPARABLE_RANK_ONE_CLOUD_KERNEL,
        sign_representation=DEFAULT_SIGN_REPRESENTATION,
        delay_representation=DEFAULT_DELAY_REPRESENTATION,
        delay_model="fixture_delay_model",
        delay_model_parameters={
            "base_delay_ms": 0.0,
            "velocity_distance_units_per_ms": 1.0,
            "delay_bin_size_ms": 1.0,
        },
        aggregation_rule=DEFAULT_AGGREGATION_RULE,
        missing_geometry_policy="fail_fixture",
        source_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        target_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        synapse_table=empty_synapse_table.copy(),
        component_table=component_table,
        blocked_synapse_table=empty_synapse_table.copy(),
        source_anchor_table=source_anchor_table,
        target_anchor_table=target_anchor_table,
        source_cloud_table=source_cloud_table,
        target_cloud_table=target_cloud_table,
        component_synapse_table=component_synapse_table,
    )
    _write_edge_coupling_bundle_npz(
        path=edge_bundle_path,
        bundle=bundle,
    )


def _family_by_route(
    families: list[dict[str, object]],
    projection_route: str,
) -> dict[str, object]:
    for family in families:
        if family["projection_route"] == projection_route:
            return family
    raise AssertionError(f"Missing component family for route {projection_route!r}.")


def _event_by_route(
    events: tuple[dict[str, object], ...],
    projection_route: str,
) -> dict[str, object]:
    for event in events:
        if event["projection_route"] == projection_route:
            return event
    raise AssertionError(f"Missing coupling event for route {projection_route!r}.")


if __name__ == "__main__":
    unittest.main()
