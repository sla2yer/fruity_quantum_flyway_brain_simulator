from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

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
    SURFACE_PATCH_CLOUD_MODE,
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
)
from flywire_wave.hybrid_morphology_runtime import (
    build_surface_wave_morphology_runtime,
    run_morphology_runtime_shared_schedule,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.surface_operators import serialize_sparse_matrix
from flywire_wave.surface_wave_contract import build_surface_wave_model_metadata
from flywire_wave.surface_wave_execution import (
    POSTSYNAPTIC_PATCH_PERMUTATION_SHUFFLE,
    SHUFFLED_TOPOLOGY_CONDITION,
    resolve_surface_wave_execution_plan,
)
from flywire_wave.surface_wave_solver import SurfaceWaveState
from flywire_wave.synapse_mapping import (
    EDGE_BUNDLE_COLUMN_TYPES,
    _write_edge_coupling_bundle_npz,
)


class SurfaceWaveExecutionTest(unittest.TestCase):
    def test_delayed_signed_patch_cloud_coupling_runs_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_fixture(Path(tmp_dir_str), topology_condition="intact")
            plan = resolve_surface_wave_execution_plan(
                surface_wave_model=fixture["surface_wave_model"],
                surface_wave_execution_plan=fixture["surface_wave_execution_plan"],
                root_ids=fixture["root_ids"],
                timebase=fixture["timebase"],
                determinism=fixture["determinism"],
            )
            initial_states = {
                101: SurfaceWaveState(
                    resolution="surface",
                    activation=np.asarray([1.0, 0.0], dtype=np.float64),
                    velocity=np.zeros(2, dtype=np.float64),
                )
            }

            first = plan.run_to_completion(
                shared_step_count=3,
                initial_states_by_root=initial_states,
            )
            second = plan.run_to_completion(
                shared_step_count=3,
                initial_states_by_root=initial_states,
            )

            np.testing.assert_allclose(
                first.patch_readout_history_by_root[101],
                np.asarray(
                    [
                        [1.0, 0.0],
                        [1.0, 0.0],
                        [1.0, 0.0],
                        [1.0, 0.0],
                    ],
                    dtype=np.float64,
                ),
            )
            np.testing.assert_allclose(
                first.patch_readout_history_by_root[202],
                np.asarray(
                    [
                        [0.0, 0.0],
                        [0.0, 0.0],
                        [0.0, -0.5],
                        [1.0, -1.5],
                    ],
                    dtype=np.float64,
                ),
            )
            self.assertEqual(len(first.coupling_application_history), 3)
            self.assertEqual(
                first.coupling_application_history[0]["component_id"],
                "101__to__202__inh_delay_1",
            )
            self.assertAlmostEqual(
                first.coupling_application_history[0]["signed_source_value"],
                -0.5,
                places=9,
            )
            self.assertEqual(plan.coupling_plan.component_count, 2)
            self.assertEqual(plan.coupling_plan.max_delay_steps, 2)
            self.assertEqual(
                first.final_states_by_root[202]["activation"],
                [1.0, -1.5],
            )
            self.assertEqual(
                first.as_mapping()["coupling_application_history"],
                second.as_mapping()["coupling_application_history"],
            )
            np.testing.assert_allclose(
                first.patch_readout_history_by_root[202],
                second.patch_readout_history_by_root[202],
            )

    def test_shuffled_topology_uses_deterministic_postsynaptic_patch_permutation(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_fixture(
                Path(tmp_dir_str),
                topology_condition=SHUFFLED_TOPOLOGY_CONDITION,
            )
            plan = resolve_surface_wave_execution_plan(
                surface_wave_model=fixture["surface_wave_model"],
                surface_wave_execution_plan=fixture["surface_wave_execution_plan"],
                root_ids=fixture["root_ids"],
                timebase=fixture["timebase"],
                determinism=fixture["determinism"],
            )
            initial_states = {
                101: SurfaceWaveState(
                    resolution="surface",
                    activation=np.asarray([1.0, 0.0], dtype=np.float64),
                    velocity=np.zeros(2, dtype=np.float64),
                )
            }

            result = plan.run_to_completion(
                shared_step_count=3,
                initial_states_by_root=initial_states,
            )
            repeated = plan.run_to_completion(
                shared_step_count=3,
                initial_states_by_root=initial_states,
            )

            self.assertEqual(plan.coupling_plan.shuffle_scope, POSTSYNAPTIC_PATCH_PERMUTATION_SHUFFLE)
            self.assertEqual(plan.coupling_plan.target_patch_permutations[202], (1, 0))
            self.assertEqual(
                result.final_states_by_root[202]["activation"],
                [-1.5, 1.0],
            )
            np.testing.assert_allclose(
                result.patch_readout_history_by_root[202],
                repeated.patch_readout_history_by_root[202],
            )

    def test_morphology_runtime_adapter_preserves_surface_fixture_behavior(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_fixture(Path(tmp_dir_str), topology_condition="intact")
            plan = resolve_surface_wave_execution_plan(
                surface_wave_model=fixture["surface_wave_model"],
                surface_wave_execution_plan=fixture["surface_wave_execution_plan"],
                root_ids=fixture["root_ids"],
                timebase=fixture["timebase"],
                determinism=fixture["determinism"],
            )
            initial_states = {
                101: SurfaceWaveState(
                    resolution="surface",
                    activation=np.asarray([1.0, 0.0], dtype=np.float64),
                    velocity=np.zeros(2, dtype=np.float64),
                )
            }

            legacy = plan.run_to_completion(
                shared_step_count=3,
                initial_states_by_root=initial_states,
            )
            runtime = build_surface_wave_morphology_runtime(plan)
            last_drive_vector, adapted = run_morphology_runtime_shared_schedule(
                runtime,
                drive_values=np.zeros((3, len(plan.root_ids)), dtype=np.float64),
                initial_states_by_root=initial_states,
            )

            np.testing.assert_allclose(last_drive_vector, np.zeros(len(plan.root_ids), dtype=np.float64))
            self.assertEqual(
                runtime.descriptor.hybrid_morphology["discovered_morphology_classes"],
                ["surface_neuron"],
            )
            self.assertEqual(
                adapted.initial_state_exports_by_root,
                legacy.initial_states_by_root,
            )
            self.assertEqual(
                adapted.final_state_exports_by_root,
                legacy.final_states_by_root,
            )
            self.assertEqual(
                list(adapted.shared_readout_history),
                list(legacy.shared_readout_history),
            )
            self.assertEqual(
                list(adapted.coupling_application_history),
                list(legacy.coupling_application_history),
            )
            np.testing.assert_allclose(
                adapted.coupling_projection_history_by_root[101],
                legacy.patch_readout_history_by_root[101],
            )
            np.testing.assert_allclose(
                adapted.coupling_projection_history_by_root[202],
                legacy.patch_readout_history_by_root[202],
            )

            projection_payload = adapted.export_projection_trace_payload()
            self.assertIn("root_101_patch_activation", projection_payload)
            self.assertIn("root_202_patch_activation", projection_payload)
            np.testing.assert_allclose(
                projection_payload["root_202_patch_activation"],
                legacy.patch_readout_history_by_root[202],
            )

    def test_unusable_delay_and_incompatible_anchor_resolution_fail_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            delay_fixture = _materialize_fixture(
                tmp_dir / "bad_delay",
                topology_condition="intact",
                inhibitory_delay_ms=0.5,
            )
            with self.assertRaises(ValueError) as delay_ctx:
                resolve_surface_wave_execution_plan(
                    surface_wave_model=delay_fixture["surface_wave_model"],
                    surface_wave_execution_plan=delay_fixture["surface_wave_execution_plan"],
                    root_ids=delay_fixture["root_ids"],
                    timebase=delay_fixture["timebase"],
                    determinism=delay_fixture["determinism"],
                )
            self.assertIn("cannot be represented", str(delay_ctx.exception))

            anchor_fixture = _materialize_fixture(
                tmp_dir / "bad_anchor",
                topology_condition="intact",
                target_anchor_resolution="skeleton_node",
            )
            with self.assertRaises(ValueError) as anchor_ctx:
                resolve_surface_wave_execution_plan(
                    surface_wave_model=anchor_fixture["surface_wave_model"],
                    surface_wave_execution_plan=anchor_fixture["surface_wave_execution_plan"],
                    root_ids=anchor_fixture["root_ids"],
                    timebase=anchor_fixture["timebase"],
                    determinism=anchor_fixture["determinism"],
                )
            self.assertIn("anchor_resolution 'coarse_patch'", str(anchor_ctx.exception))


def _materialize_fixture(
    base_dir: Path,
    *,
    topology_condition: str,
    inhibitory_delay_ms: float = 1.0,
    target_anchor_resolution: str = "coarse_patch",
) -> dict[str, object]:
    operator_assets = [
        _write_identity_operator_assets(base_dir / "operators" / "101", root_id=101),
        _write_identity_operator_assets(base_dir / "operators" / "202", root_id=202),
    ]

    coupling_dir = base_dir / "coupling"
    local_synapse_registry_path = coupling_dir / "synapse_registry.csv"
    local_synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
    local_synapse_registry_path.write_text("synapse_id\n", encoding="utf-8")
    edge_bundle_path = coupling_dir / "edges" / "101__to__202_coupling.npz"
    _write_fixture_edge_bundle(
        edge_bundle_path=edge_bundle_path,
        inhibitory_delay_ms=inhibitory_delay_ms,
        target_anchor_resolution=target_anchor_resolution,
    )

    selected_root_coupling_assets = []
    for root_id in (101, 202):
        incoming_anchor_map_path = coupling_dir / "roots" / f"{root_id}_incoming_anchor_map.npz"
        outgoing_anchor_map_path = coupling_dir / "roots" / f"{root_id}_outgoing_anchor_map.npz"
        coupling_index_path = coupling_dir / "roots" / f"{root_id}_coupling_index.json"
        incoming_anchor_map_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(incoming_anchor_map_path, placeholder=np.asarray([], dtype=np.int64))
        np.savez_compressed(outgoing_anchor_map_path, placeholder=np.asarray([], dtype=np.int64))
        write_json({}, coupling_index_path)
        selected_root_coupling_assets.append(
            {
                "root_id": root_id,
                "local_synapse_registry_path": str(local_synapse_registry_path.resolve()),
                "incoming_anchor_map_path": str(incoming_anchor_map_path.resolve()),
                "outgoing_anchor_map_path": str(outgoing_anchor_map_path.resolve()),
                "coupling_index_path": str(coupling_index_path.resolve()),
                "selected_edge_bundle_paths": [
                    {
                        "pre_root_id": 101,
                        "post_root_id": 202,
                        "path": str(edge_bundle_path.resolve()),
                    }
                ],
            }
        )

    return {
        "root_ids": [101, 202],
        "timebase": {
            "time_origin_ms": 0.0,
            "dt_ms": 1.0,
            "duration_ms": 3.0,
            "sample_count": 3,
        },
        "determinism": {
            "seed": 17,
            "rng_family": "numpy_pcg64",
            "seed_scope": "all_stochastic_simulator_components",
        },
        "surface_wave_model": build_surface_wave_model_metadata(
            parameter_bundle={
                "parameter_preset": "coupled_patch_cloud_fixture",
                "propagation": {
                    "wave_speed_sq_scale": 1.0,
                    "restoring_strength_per_ms2": 0.0,
                },
                "damping": {
                    "gamma_per_ms": 0.0,
                },
            }
        ),
        "surface_wave_execution_plan": {
            "topology_condition": topology_condition,
            "solver": {
                "integration_timestep_ms": 1.0,
                "shared_output_timestep_ms": 1.0,
                "internal_substep_count": 1,
            },
            "selected_root_operator_assets": operator_assets,
            "selected_root_coupling_assets": selected_root_coupling_assets,
        },
    }


def _write_identity_operator_assets(base_dir: Path, *, root_id: int) -> dict[str, object]:
    fine_operator_path = base_dir / f"{root_id}_fine_operator.npz"
    coarse_operator_path = base_dir / f"{root_id}_coarse_operator.npz"
    transfer_operator_path = base_dir / f"{root_id}_transfer_operators.npz"
    operator_metadata_path = base_dir / f"{root_id}_operator_metadata.json"
    base_dir.mkdir(parents=True, exist_ok=True)

    zero_operator = sp.csr_matrix((2, 2), dtype=np.float64)
    identity_transfer = sp.identity(2, dtype=np.float64, format="csr")
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            "mass_diagonal": np.ones(2, dtype=np.float64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(zero_operator).items()
            },
        },
        fine_operator_path,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            "mass_diagonal": np.ones(2, dtype=np.float64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(zero_operator).items()
            },
        },
        coarse_operator_path,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            "surface_to_patch": np.asarray([0, 1], dtype=np.int32),
            **{
                f"restriction_{key}": value
                for key, value in serialize_sparse_matrix(identity_transfer).items()
            },
            **{
                f"prolongation_{key}": value
                for key, value in serialize_sparse_matrix(identity_transfer).items()
            },
        },
        transfer_operator_path,
    )
    write_json(
        {
            "boundary_condition_mode": "closed_surface_zero_flux",
            "realization_mode": "fixture_identity_patch_operator",
        },
        operator_metadata_path,
    )
    return {
        "root_id": root_id,
        "fine_operator_path": str(fine_operator_path.resolve()),
        "coarse_operator_path": str(coarse_operator_path.resolve()),
        "transfer_operator_path": str(transfer_operator_path.resolve()),
        "operator_metadata_path": str(operator_metadata_path.resolve()),
    }


def _write_fixture_edge_bundle(
    *,
    edge_bundle_path: Path,
    inhibitory_delay_ms: float,
    target_anchor_resolution: str,
) -> None:
    source_anchor_table = pd.DataFrame.from_records(
        [
            {
                "anchor_table_index": 0,
                "root_id": 101,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": "coarse_patch",
                "anchor_index": 0,
                "anchor_x": 0.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            }
        ],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    target_anchor_table = pd.DataFrame.from_records(
        [
            {
                "anchor_table_index": 0,
                "root_id": 202,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": target_anchor_resolution,
                "anchor_index": 0,
                "anchor_x": 0.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            },
            {
                "anchor_table_index": 1,
                "root_id": 202,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": target_anchor_resolution,
                "anchor_index": 1,
                "anchor_x": 1.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            },
        ],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    component_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "component_id": "101__to__202__inh_delay_1",
                "pre_root_id": 101,
                "post_root_id": 202,
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "pre_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "post_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "sign_label": "inhibitory",
                "sign_polarity": -1,
                "sign_representation": DEFAULT_SIGN_REPRESENTATION,
                "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                "delay_model": "fixture_delay_model",
                "delay_ms": inhibitory_delay_ms,
                "delay_bin_index": 1,
                "delay_bin_label": "delay_1",
                "delay_bin_start_ms": inhibitory_delay_ms,
                "delay_bin_end_ms": inhibitory_delay_ms,
                "aggregation_rule": DEFAULT_AGGREGATION_RULE,
                "source_anchor_count": 1,
                "target_anchor_count": 1,
                "synapse_count": 1,
                "signed_weight_total": -0.5,
                "absolute_weight_total": 0.5,
                "confidence_sum": 1.0,
                "confidence_mean": 1.0,
                "source_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "target_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "source_normalization_total": 1.0,
                "target_normalization_total": 1.0,
            },
            {
                "component_index": 1,
                "component_id": "101__to__202__exc_delay_2",
                "pre_root_id": 101,
                "post_root_id": 202,
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "pre_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "post_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "sign_label": "excitatory",
                "sign_polarity": 1,
                "sign_representation": DEFAULT_SIGN_REPRESENTATION,
                "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                "delay_model": "fixture_delay_model",
                "delay_ms": 2.0,
                "delay_bin_index": 2,
                "delay_bin_label": "delay_2",
                "delay_bin_start_ms": 2.0,
                "delay_bin_end_ms": 2.0,
                "aggregation_rule": DEFAULT_AGGREGATION_RULE,
                "source_anchor_count": 1,
                "target_anchor_count": 1,
                "synapse_count": 1,
                "signed_weight_total": 1.0,
                "absolute_weight_total": 1.0,
                "confidence_sum": 1.0,
                "confidence_mean": 1.0,
                "source_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "target_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "source_normalization_total": 1.0,
                "target_normalization_total": 1.0,
            },
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
            },
            {
                "component_index": 1,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            },
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    target_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 1,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            },
            {
                "component_index": 1,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            },
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    component_synapse_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "synapse_row_id": "fixture#inh",
                "source_row_number": 1,
                "synapse_id": "fixture-inh",
                "sign_label": "inhibitory",
                "signed_weight": -0.5,
                "absolute_weight": 0.5,
                "delay_ms": inhibitory_delay_ms,
                "delay_bin_index": 1,
                "delay_bin_label": "delay_1",
            },
            {
                "component_index": 1,
                "synapse_row_id": "fixture#exc",
                "source_row_number": 2,
                "synapse_id": "fixture-exc",
                "sign_label": "excitatory",
                "signed_weight": 1.0,
                "absolute_weight": 1.0,
                "delay_ms": 2.0,
                "delay_bin_index": 2,
                "delay_bin_label": "delay_2",
            },
        ],
        columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES),
    )
    empty_synapse_table = pd.DataFrame(columns=list(EDGE_BUNDLE_COLUMN_TYPES))
    bundle = EdgeCouplingBundle(
        pre_root_id=101,
        post_root_id=202,
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


if __name__ == "__main__":
    unittest.main()
