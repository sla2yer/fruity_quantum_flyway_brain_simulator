from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.coupling_contract import (
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    POINT_NEURON_LUMPED_MODE,
    POINT_TO_POINT_TOPOLOGY,
    SURFACE_PATCH_CLOUD_MODE,
)
from flywire_wave.hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
    build_hybrid_morphology_plan_metadata,
)
from flywire_wave.hybrid_morphology_runtime import (
    MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
    MorphologyRuntimeDescriptor,
    resolve_morphology_runtime_from_arm_plan,
    run_morphology_runtime_shared_schedule,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.skeleton_runtime_assets import (
    SKELETON_RUNTIME_ASSET_CONTRACT_VERSION,
    build_skeleton_runtime_asset_record,
    load_skeleton_runtime_asset_metadata,
    materialize_skeleton_runtime_asset,
)
from flywire_wave.surface_operators import serialize_sparse_matrix
from flywire_wave.surface_wave_contract import build_surface_wave_model_metadata
from flywire_wave.simulator_runtime import (
    SimulationDeterminismContext,
    SimulationReadoutDefinition,
    SimulationStateSummaryRow,
    SimulationTimebase,
)


@dataclass(frozen=True)
class _StubRuntimeResult:
    descriptor: MorphologyRuntimeDescriptor
    root_ids: tuple[int, ...]
    timebase: dict[str, Any]
    determinism: dict[str, Any]
    runtime_metadata_by_root: tuple[dict[str, Any], ...]
    initial_state_exports_by_root: dict[int, dict[str, Any]]
    final_state_exports_by_root: dict[int, dict[str, Any]]
    coupling_projection_history_by_root: dict[int, np.ndarray]
    shared_readout_history: tuple[dict[str, Any], ...]
    coupling_application_history: tuple[dict[str, Any], ...]
    substep_count: int
    shared_step_count: int

    def export_state_summaries(
        self,
        *,
        state_stage: str,
    ) -> tuple[SimulationStateSummaryRow, ...]:
        if state_stage == "initial":
            state_mapping = self.initial_state_exports_by_root[303]
        elif state_stage == "final":
            state_mapping = self.final_state_exports_by_root[303]
        else:
            raise ValueError(f"Unsupported state_stage {state_stage!r}.")
        return (
            SimulationStateSummaryRow(
                state_id="root_303_stub_state",
                scope="root_state",
                summary_stat="mean",
                value=float(state_mapping["activation"][0]),
                units="activation_au",
            ),
        )

    def export_readout_values(
        self,
        *,
        summary: dict[str, Any],
        readout_catalog: tuple[SimulationReadoutDefinition, ...],
    ) -> np.ndarray:
        return np.asarray(
            [float(summary["shared_output_mean"]) for _ in readout_catalog],
            dtype=np.float64,
        )

    def export_readout_trace_values(
        self,
        *,
        readout_catalog: tuple[SimulationReadoutDefinition, ...],
        sample_count: int,
    ) -> np.ndarray:
        values = np.empty((int(sample_count), len(readout_catalog)), dtype=np.float64)
        for sample_index in range(int(sample_count)):
            values[sample_index, :] = self.export_readout_values(
                summary=self.shared_readout_history[sample_index],
                readout_catalog=readout_catalog,
            )
        return values

    def export_dynamic_state_vector(
        self,
        *,
        summary: dict[str, Any],
    ) -> np.ndarray:
        return np.asarray([float(summary["shared_output_mean"])], dtype=np.float64)

    def export_projection_trace_payload(self) -> dict[str, np.ndarray]:
        history = np.asarray(self.coupling_projection_history_by_root[303], dtype=np.float64)
        return {
            "substep_time_ms": np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
            "root_ids": np.asarray([303], dtype=np.int64),
            "root_303_projection": history,
        }


class _StubMorphologyRuntime:
    def __init__(self) -> None:
        self.execution_version = "stub_morphology_runtime.v1"
        self.model_mode = "surface_wave"
        self.root_ids = (303,)
        self.timebase = SimulationTimebase.from_mapping(
            {
                "time_origin_ms": 0.0,
                "dt_ms": 1.0,
                "duration_ms": 3.0,
                "sample_count": 3,
            }
        )
        self.determinism = SimulationDeterminismContext.from_mapping(
            {
                "seed": 17,
                "rng_family": "numpy_pcg64",
                "seed_scope": "all_stochastic_simulator_components",
            }
        )
        hybrid_morphology = build_hybrid_morphology_plan_metadata(
            root_records=[
                {
                    "root_id": 303,
                    "project_role": "point_simulated",
                    "cell_type": "Mi1",
                }
            ]
        )
        self.descriptor = MorphologyRuntimeDescriptor(
            interface_version=MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
            model_mode="surface_wave",
            runtime_family="stub_point_runtime.v1",
            hybrid_morphology=hybrid_morphology,
            source_injection={
                "injection_strategy": "per_root_scalar_stub_drive",
            },
            state_export={
                "state_field_layout": "scalar_state_by_root",
            },
            readout_export={
                "history_field": "shared_readout_history",
                "shared_readout_value_semantics": "shared_downstream_activation",
            },
            coupling_projection={
                "projection_field": "coupling_projection_history_by_root",
                "projection_surface": "root_state_scalar",
            },
        )
        self._initialized = False
        self._pending_input = 0.0
        self._current_value = 0.0
        self._projection_history: list[np.ndarray] = []
        self._shared_history: list[dict[str, Any]] = []
        self._initial_state: dict[int, dict[str, Any]] | None = None

    def initialize_zero(self) -> dict[str, Any]:
        self._initialized = True
        self._pending_input = 0.0
        self._current_value = 0.0
        self._projection_history = []
        self._shared_history = [self._summary(lifecycle_stage="initialized", step_index=0)]
        self._initial_state = {
            303: {
                "resolution": "point",
                "activation": [0.0],
                "velocity": [0.0],
            }
        }
        return copy.deepcopy(self._shared_history[0])

    def initialize_states(
        self,
        states_by_root: dict[int, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("The stub runtime only uses initialize_zero in tests.")

    def inject_sources(
        self,
        source_values_by_root: dict[int, float] | None = None,
    ) -> None:
        if not self._initialized:
            raise ValueError("Stub runtime is not initialized.")
        self._pending_input = 0.0 if source_values_by_root is None else float(
            source_values_by_root.get(303, 0.0)
        )

    def step_shared(self) -> dict[str, Any]:
        if not self._initialized:
            raise ValueError("Stub runtime is not initialized.")
        self._current_value += self._pending_input
        self._projection_history.append(
            np.asarray([self._current_value], dtype=np.float64)
        )
        summary = self._summary(
            lifecycle_stage="step_completed",
            step_index=len(self._projection_history),
        )
        self._shared_history.append(summary)
        self._pending_input = 0.0
        return copy.deepcopy(summary)

    def finalize(self) -> _StubRuntimeResult:
        if not self._initialized or self._initial_state is None:
            raise ValueError("Stub runtime is not initialized.")
        final_summary = self._summary(
            lifecycle_stage="finalized",
            step_index=len(self._projection_history),
        )
        self._shared_history.append(final_summary)
        return _StubRuntimeResult(
            descriptor=self.descriptor,
            root_ids=self.root_ids,
            timebase=self.timebase.as_mapping(),
            determinism=self.determinism.as_mapping(),
            runtime_metadata_by_root=(
                {
                    "root_id": 303,
                    "morphology_class": POINT_NEURON_CLASS,
                    "state_layout": "scalar_state",
                },
            ),
            initial_state_exports_by_root=copy.deepcopy(self._initial_state),
            final_state_exports_by_root={
                303: {
                    "resolution": "point",
                    "activation": [float(self._current_value)],
                    "velocity": [0.0],
                }
            },
            coupling_projection_history_by_root={
                303: np.asarray(self._projection_history, dtype=np.float64),
            },
            shared_readout_history=tuple(copy.deepcopy(self._shared_history)),
            coupling_application_history=(),
            substep_count=len(self._projection_history),
            shared_step_count=len(self._projection_history),
        )

    def _summary(self, *, lifecycle_stage: str, step_index: int) -> dict[str, Any]:
        return {
            "lifecycle_stage": lifecycle_stage,
            "shared_step_index": int(step_index),
            "substep_index": int(step_index),
            "time_ms": float(step_index),
            "shared_output_mean": float(self._current_value),
            "per_root_mean_activation": {"303": float(self._current_value)},
            "per_root_mean_velocity": {"303": 0.0},
            "per_root_patch_activation": {"303": [float(self._current_value)]},
        }


class HybridMorphologyRuntimeTest(unittest.TestCase):
    def test_runtime_interface_hosts_lightweight_stub_class(self) -> None:
        runtime = _StubMorphologyRuntime()
        readout_catalog = (
            SimulationReadoutDefinition(
                readout_id="shared_output_mean",
                scope="circuit_output",
                aggregation="identity",
                units="activation_au",
                value_semantics="shared_downstream_activation",
            ),
        )

        last_drive_vector, result = run_morphology_runtime_shared_schedule(
            runtime,
            drive_values=np.asarray([[1.0], [0.5], [2.5]], dtype=np.float64),
        )

        np.testing.assert_allclose(last_drive_vector, np.asarray([2.5], dtype=np.float64))
        self.assertEqual(result.descriptor.runtime_family, "stub_point_runtime.v1")
        self.assertEqual(
            result.descriptor.hybrid_morphology["discovered_morphology_classes"],
            [POINT_NEURON_CLASS],
        )
        self.assertEqual(
            result.descriptor.readout_export["shared_readout_value_semantics"],
            "shared_downstream_activation",
        )

        trace_values = result.export_readout_trace_values(
            readout_catalog=readout_catalog,
            sample_count=3,
        )
        np.testing.assert_allclose(
            trace_values[:, 0],
            np.asarray([0.0, 1.0, 1.5], dtype=np.float64),
        )
        np.testing.assert_allclose(
            result.export_dynamic_state_vector(summary=result.shared_readout_history[-1]),
            np.asarray([4.0], dtype=np.float64),
        )
        self.assertEqual(
            [row.as_record() for row in result.export_state_summaries(state_stage="final")],
            [
                {
                    "scope": "root_state",
                    "state_id": "root_303_stub_state",
                    "summary_stat": "mean",
                    "units": "activation_au",
                    "value": 4.0,
                }
            ],
        )

        projection_payload = result.export_projection_trace_payload()
        self.assertIn("root_303_projection", projection_payload)
        np.testing.assert_allclose(
            projection_payload["root_303_projection"].ravel(),
            np.asarray([1.0, 1.5, 4.0], dtype=np.float64),
        )

    def test_skeleton_runtime_asset_materialization_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            raw_skeleton_path = tmp_dir / "raw" / "202.swc"
            _write_skeleton_fixture(raw_skeleton_path)

            first = materialize_skeleton_runtime_asset(
                root_id=202,
                raw_skeleton_path=raw_skeleton_path,
                processed_graph_dir=tmp_dir / "processed",
            )
            second = materialize_skeleton_runtime_asset(
                root_id=202,
                raw_skeleton_path=raw_skeleton_path,
                processed_graph_dir=tmp_dir / "processed",
            )

            self.assertEqual(first, second)
            self.assertEqual(
                first["contract_version"],
                SKELETON_RUNTIME_ASSET_CONTRACT_VERSION,
            )
            self.assertEqual(first["counts"]["node_count"], 3)
            self.assertEqual(first["counts"]["edge_count"], 2)
            self.assertGreater(first["operator"]["spectral_radius"], 0.0)
            self.assertEqual(
                Path(first["metadata_path"]).read_bytes(),
                Path(second["metadata_path"]).read_bytes(),
            )
            self.assertEqual(
                Path(first["asset_data_path"]).read_bytes(),
                Path(second["asset_data_path"]).read_bytes(),
            )

    def test_surface_skeleton_runtime_adapter_runs_supported_mixed_fixture_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(tmp_dir)

            first_runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            first_last_drive, first_result = run_morphology_runtime_shared_schedule(
                first_runtime,
                drive_values=np.asarray(
                    [
                        [0.0, 1.0],
                        [0.0, 0.5],
                        [0.0, 0.0],
                    ],
                    dtype=np.float64,
                ),
            )
            second_runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            second_last_drive, second_result = run_morphology_runtime_shared_schedule(
                second_runtime,
                drive_values=np.asarray(
                    [
                        [0.0, 1.0],
                        [0.0, 0.5],
                        [0.0, 0.0],
                    ],
                    dtype=np.float64,
                ),
            )

            np.testing.assert_allclose(
                first_last_drive,
                np.asarray([0.0, 0.0], dtype=np.float64),
            )
            np.testing.assert_allclose(first_last_drive, second_last_drive)
            self.assertEqual(
                first_runtime.descriptor.hybrid_morphology["discovered_morphology_classes"],
                [SKELETON_NEURON_CLASS, SURFACE_NEURON_CLASS],
            )
            self.assertEqual(
                first_runtime.descriptor.runtime_family,
                "surface_wave_surface_skeleton_runtime_adapter.v1",
            )

            skeleton_projection = first_result.coupling_projection_history_by_root[202]
            np.testing.assert_allclose(
                skeleton_projection,
                np.asarray(
                    [
                        [0.0, 0.0, 0.0],
                        [1.0, 1.0, 1.0],
                        [2.35, 2.35, 2.35],
                        [3.4475, 3.4475, 3.4475],
                    ],
                    dtype=np.float64,
                ),
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                first_result.coupling_projection_history_by_root[101],
                np.zeros((4, 2), dtype=np.float64),
            )
            np.testing.assert_allclose(
                np.asarray(
                    first_result.final_state_exports_by_root[202]["activation"],
                    dtype=np.float64,
                ),
                np.asarray([3.4475, 3.4475, 3.4475], dtype=np.float64),
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                np.asarray(
                    first_result.final_state_exports_by_root[202]["velocity"],
                    dtype=np.float64,
                ),
                np.asarray([1.0975, 1.0975, 1.0975], dtype=np.float64),
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                first_result.export_readout_trace_values(
                    readout_catalog=(
                        SimulationReadoutDefinition(
                            readout_id="shared_output_mean",
                            scope="circuit_output",
                            aggregation="identity",
                            units="activation_au",
                            value_semantics="shared_downstream_activation",
                        ),
                    ),
                    sample_count=3,
                )[:, 0],
                np.asarray([0.0, 0.5, 1.175], dtype=np.float64),
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                first_result.export_dynamic_state_vector(
                    summary=first_result.shared_readout_history[-1]
                ),
                np.asarray([0.0, 3.4475], dtype=np.float64),
                atol=1.0e-9,
            )
            projection_payload = first_result.export_projection_trace_payload()
            self.assertIn("root_101_patch_activation", projection_payload)
            self.assertIn("root_202_skeleton_activation", projection_payload)
            np.testing.assert_allclose(
                projection_payload["root_202_skeleton_activation"],
                skeleton_projection,
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                first_result.coupling_projection_history_by_root[202],
                second_result.coupling_projection_history_by_root[202],
                atol=1.0e-9,
            )
            self.assertEqual(
                list(first_result.shared_readout_history),
                list(second_result.shared_readout_history),
            )

    def test_mixed_runtime_adapter_supports_point_placeholder_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(
                tmp_dir,
                include_point_root=True,
            )

            first_runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            first_last_drive, first_result = run_morphology_runtime_shared_schedule(
                first_runtime,
                drive_values=np.asarray(
                    [
                        [0.0, 0.0, 2.0],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ],
                    dtype=np.float64,
                ),
            )
            second_runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
            second_last_drive, second_result = run_morphology_runtime_shared_schedule(
                second_runtime,
                drive_values=np.asarray(
                    [
                        [0.0, 0.0, 2.0],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ],
                    dtype=np.float64,
                ),
            )

            np.testing.assert_allclose(
                first_last_drive,
                np.asarray([0.0, 0.0, 0.0], dtype=np.float64),
            )
            np.testing.assert_allclose(first_last_drive, second_last_drive)
            self.assertEqual(
                first_runtime.descriptor.hybrid_morphology["discovered_morphology_classes"],
                [POINT_NEURON_CLASS, SKELETON_NEURON_CLASS, SURFACE_NEURON_CLASS],
            )
            self.assertEqual(
                first_runtime.descriptor.runtime_family,
                "surface_wave_mixed_morphology_runtime_adapter.v1",
            )
            np.testing.assert_allclose(
                first_result.coupling_projection_history_by_root[303],
                np.asarray(
                    [[0.0], [1.0], [0.5], [0.25]],
                    dtype=np.float64,
                ),
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                np.asarray(
                    first_result.final_state_exports_by_root[303]["activation"],
                    dtype=np.float64,
                ),
                np.asarray([0.25], dtype=np.float64),
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                np.asarray(
                    first_result.final_state_exports_by_root[303]["velocity"],
                    dtype=np.float64,
                ),
                np.asarray([-0.25], dtype=np.float64),
                atol=1.0e-9,
            )
            final_state_ids = {
                row.state_id
                for row in first_result.export_state_summaries(state_stage="final")
            }
            self.assertIn("root_303_point_activation_state", final_state_ids)
            self.assertIn("root_303_point_projection_state", final_state_ids)

            projection_payload = first_result.export_projection_trace_payload()
            self.assertIn("root_303_point_activation", projection_payload)
            np.testing.assert_allclose(
                projection_payload["root_303_point_activation"],
                first_result.coupling_projection_history_by_root[303],
                atol=1.0e-9,
            )
            np.testing.assert_allclose(
                first_result.coupling_projection_history_by_root[303],
                second_result.coupling_projection_history_by_root[303],
                atol=1.0e-9,
            )
            self.assertEqual(
                list(first_result.shared_readout_history),
                list(second_result.shared_readout_history),
            )

    def test_missing_selected_edge_bundle_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            arm_plan = _build_surface_skeleton_arm_plan(
                tmp_dir,
                selected_edge_bundle_paths=[
                    {
                        "pre_root_id": 202,
                        "post_root_id": 101,
                        "path": str((tmp_dir / "edges" / "202__to__101.npz").resolve()),
                    }
                ],
            )
            with self.assertRaises(ValueError) as ctx:
                resolve_morphology_runtime_from_arm_plan(arm_plan)
            self.assertIn("selected edge bundle is missing", str(ctx.exception))

    def test_invalid_skeleton_runtime_asset_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            invalid_path = tmp_dir / "raw" / "404.swc"
            invalid_path.parent.mkdir(parents=True, exist_ok=True)
            invalid_path.write_text(
                "1 1 0.0 0.0 0.0 1.0 -1\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                materialize_skeleton_runtime_asset(
                    root_id=404,
                    raw_skeleton_path=invalid_path,
                    processed_graph_dir=tmp_dir / "processed",
                )
            self.assertIn("scientifically unsupported", str(ctx.exception))


def _build_surface_skeleton_arm_plan(
    tmp_dir: Path,
    *,
    selected_edge_bundle_paths: list[dict[str, object]] | None = None,
    include_point_root: bool = False,
) -> dict[str, Any]:
    surface_wave_model = build_surface_wave_model_metadata(
        parameter_bundle={
            "propagation": {
                "wave_speed_sq_scale": 0.1,
                "restoring_strength_per_ms2": 0.05,
            },
            "damping": {
                "gamma_per_ms": 0.1,
            },
            "recovery": {
                "mode": "disabled",
            },
            "nonlinearity": {
                "mode": "none",
            },
            "anisotropy": {
                "mode": "isotropic",
            },
            "branching": {
                "mode": "disabled",
            },
        }
    )
    root_records = [
        {
            "root_id": 101,
            "morphology_class": "surface_neuron",
        },
        {
            "root_id": 202,
            "morphology_class": "skeleton_neuron",
        },
    ]
    if include_point_root:
        root_records.append(
            {
                "root_id": 303,
                "morphology_class": "point_neuron",
            }
        )
    hybrid_morphology = build_hybrid_morphology_plan_metadata(
        root_records=root_records,
        model_mode="surface_wave",
    )
    surface_operator_asset = _write_identity_surface_operator_assets(
        tmp_dir / "surface_assets",
        root_id=101,
    )
    surface_coupling_asset = _write_surface_coupling_asset(
        tmp_dir / "surface_coupling",
        root_id=101,
    )
    raw_skeleton_path = tmp_dir / "skeletons_raw" / "202.swc"
    _write_skeleton_fixture(raw_skeleton_path)
    skeleton_asset = build_skeleton_runtime_asset_record(
        root_id=202,
        raw_skeleton_path=raw_skeleton_path,
        processed_graph_dir=tmp_dir / "processed_graphs",
    )
    metadata = load_skeleton_runtime_asset_metadata(skeleton_asset["metadata_path"])
    mixed_fidelity = {
        "point_neuron_model_spec": {
            "family": "P0",
            "model_family": "passive_linear_single_compartment",
            "state_layout": "scalar_state_per_selected_root",
            "integration_scheme": "forward_euler",
            "readout_state": "membrane_state",
            "initial_state": "all_zero",
            "parameters": {
                "membrane_time_constant_ms": 2.0,
                "resting_potential": 0.0,
                "input_gain": 1.0,
                "recurrent_gain": 0.0,
            },
        },
        "per_root_assignments": [],
    }
    if include_point_root:
        mixed_fidelity["per_root_assignments"].append(
            {
                "root_id": 303,
                "realized_morphology_class": "point_neuron",
                "coupling_asset": _write_point_coupling_asset(
                    tmp_dir / "point_coupling",
                    root_id=303,
                ),
            }
        )
    return {
        "arm_reference": {
            "arm_id": "surface_skeleton_fixture",
            "model_mode": "surface_wave",
            "baseline_family": None,
        },
        "model_configuration": {
            "surface_wave_model": surface_wave_model,
            "surface_wave_reference": {
                "parameter_hash": surface_wave_model["parameter_hash"],
            },
            "surface_wave_execution_plan": {
                "topology_condition": "intact",
                "resolution": {
                    "state_space": "per_root_morphology_class",
                    "coupling_anchor_resolution": "per_root_morphology_class",
                },
                "solver": {
                    "integration_timestep_ms": 1.0,
                    "shared_output_timestep_ms": 1.0,
                    "internal_substep_count": 1,
                },
                "hybrid_morphology": hybrid_morphology,
                "mixed_fidelity": mixed_fidelity,
                "selected_root_operator_assets": [surface_operator_asset],
                "selected_root_coupling_assets": [surface_coupling_asset],
                "selected_root_skeleton_assets": [
                    {
                        **copy.deepcopy(skeleton_asset),
                        "selected_edge_bundle_paths": copy.deepcopy(
                            selected_edge_bundle_paths or []
                        ),
                        "loaded_metadata_contract_version": metadata["contract_version"],
                    }
                ],
            },
        },
        "runtime": {
            "timebase": {
                "time_origin_ms": 0.0,
                "dt_ms": 1.0,
                "duration_ms": 3.0,
                "sample_count": 3,
            },
        },
        "determinism": {
            "seed": 17,
            "rng_family": "numpy_pcg64",
            "seed_scope": "all_stochastic_simulator_components",
        },
    }


def _write_identity_surface_operator_assets(
    base_dir: Path,
    *,
    root_id: int,
) -> dict[str, object]:
    fine_operator_path = base_dir / f"{root_id}_fine_operator.npz"
    coarse_operator_path = base_dir / f"{root_id}_coarse_operator.npz"
    transfer_operator_path = base_dir / f"{root_id}_transfer_operators.npz"
    operator_metadata_path = base_dir / f"{root_id}_operator_metadata.json"
    base_dir.mkdir(parents=True, exist_ok=True)

    zero_operator = sp.csr_matrix((2, 2), dtype=np.float64)
    identity = sp.identity(2, dtype=np.float64, format="csr")
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
                for key, value in serialize_sparse_matrix(identity).items()
            },
            **{
                f"prolongation_{key}": value
                for key, value in serialize_sparse_matrix(identity).items()
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


def _write_surface_coupling_asset(
    base_dir: Path,
    *,
    root_id: int,
) -> dict[str, object]:
    registry_path = base_dir / "synapse_registry.csv"
    incoming_anchor_map_path = base_dir / f"{root_id}_incoming_anchor_map.npz"
    outgoing_anchor_map_path = base_dir / f"{root_id}_outgoing_anchor_map.npz"
    coupling_index_path = base_dir / f"{root_id}_coupling_index.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("synapse_row_id,pre_root_id,post_root_id\n", encoding="utf-8")
    incoming_anchor_map_path.write_bytes(b"fixture")
    outgoing_anchor_map_path.write_bytes(b"fixture")
    write_json({"root_id": root_id, "edge_count": 0}, coupling_index_path)
    return {
        "root_id": root_id,
        "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        "fallback_hierarchy": [SURFACE_PATCH_CLOUD_MODE],
        "local_synapse_registry_path": str(registry_path.resolve()),
        "incoming_anchor_map_path": str(incoming_anchor_map_path.resolve()),
        "outgoing_anchor_map_path": str(outgoing_anchor_map_path.resolve()),
        "coupling_index_path": str(coupling_index_path.resolve()),
        "selected_edge_bundle_paths": [],
    }


def _write_point_coupling_asset(
    base_dir: Path,
    *,
    root_id: int,
) -> dict[str, object]:
    registry_path = base_dir / "synapse_registry.csv"
    incoming_anchor_map_path = base_dir / f"{root_id}_incoming_anchor_map.npz"
    outgoing_anchor_map_path = base_dir / f"{root_id}_outgoing_anchor_map.npz"
    coupling_index_path = base_dir / f"{root_id}_coupling_index.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("synapse_row_id,pre_root_id,post_root_id\n", encoding="utf-8")
    incoming_anchor_map_path.write_bytes(b"fixture")
    outgoing_anchor_map_path.write_bytes(b"fixture")
    write_json({"root_id": root_id, "edge_count": 0}, coupling_index_path)
    return {
        "root_id": root_id,
        "topology_family": POINT_TO_POINT_TOPOLOGY,
        "fallback_hierarchy": [POINT_NEURON_LUMPED_MODE],
        "local_synapse_registry_path": str(registry_path.resolve()),
        "incoming_anchor_map_path": str(incoming_anchor_map_path.resolve()),
        "outgoing_anchor_map_path": str(outgoing_anchor_map_path.resolve()),
        "coupling_index_path": str(coupling_index_path.resolve()),
        "selected_edge_bundle_paths": [],
    }


def _write_skeleton_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "1 1 0.0 0.0 0.0 1.0 -1",
                "2 3 1.0 0.0 0.0 0.5 1",
                "3 3 2.0 0.0 0.0 0.5 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
