from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import (
    CLAMPED_BOUNDARY_CONDITION_MODE,
    DEFAULT_BOUNDARY_CONDITION_MODE,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.surface_operators import serialize_sparse_matrix
from flywire_wave.surface_wave_contract import build_surface_wave_model_metadata
from flywire_wave.surface_wave_solver import (
    EXPLICIT_STATE_INITIALIZATION,
    FINALIZED_STAGE,
    LOCALIZED_PULSE_INITIALIZATION,
    PATCH_STATE_RESOLUTION,
    SURFACE_STATE_RESOLUTION,
    STEP_COMPLETED_STAGE,
    SingleNeuronSurfaceWaveSolver,
    SurfaceWaveOperatorBundle,
    SurfaceWaveSparseKernels,
    SurfaceWaveState,
)


class SurfaceWaveSolverTest(unittest.TestCase):
    def test_fixture_solver_pulse_smoke_case_is_deterministic_and_damped(self) -> None:
        model = _build_linear_fixture_model()
        bundle = _build_fixture_operator_bundle()

        first_solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=model,
            integration_timestep_ms=0.4,
            shared_output_timestep_ms=0.8,
        )
        first_initial = first_solver.initialize_localized_pulse(
            seed_vertex=2,
            amplitude=1.0,
        )
        first_snapshots = [first_solver.step() for _ in range(8)]
        first_result = first_solver.finalize()

        second_solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=model,
            integration_timestep_ms=0.4,
            shared_output_timestep_ms=0.8,
        )
        second_solver.initialize_localized_pulse(seed_vertex=2, amplitude=1.0)
        second_snapshots = [second_solver.step() for _ in range(8)]
        second_result = second_solver.finalize()

        self.assertEqual(first_initial.lifecycle_stage, "initialized")
        self.assertEqual(first_result.initialization.mode, LOCALIZED_PULSE_INITIALIZATION)
        self.assertEqual(first_result.runtime_metadata.integration_timestep_ms, 0.4)
        self.assertEqual(first_result.runtime_metadata.shared_output_timestep_ms, 0.8)
        self.assertEqual(first_result.runtime_metadata.internal_substep_count, 2)
        self.assertEqual(first_result.runtime_metadata.patch_count, 3)
        self.assertEqual(
            first_result.runtime_metadata.boundary_condition_mode,
            DEFAULT_BOUNDARY_CONDITION_MODE,
        )
        self.assertEqual(
            first_result.runtime_metadata.step_order,
            (
                "apply_boundary_policy_pre_step",
                "assemble_surface_drive",
                "apply_surface_operator",
                "apply_restoring_sink",
                "apply_recovery_sink",
                "apply_branching_damping",
                "semi_implicit_velocity_damping",
                "update_surface_activation",
                "apply_activation_nonlinearity",
                "update_recovery_state",
                "apply_boundary_policy_post_step",
            ),
        )
        np.testing.assert_allclose(first_initial.state.activation, [0.0, 0.0, 1.0, 0.0, 0.0])
        np.testing.assert_allclose(
            first_snapshots[0].state.activation,
            [0.0, 0.1492537313432836, 0.691044776119403, 0.1492537313432836, 0.0],
        )
        np.testing.assert_allclose(
            first_snapshots[-1].state.activation,
            [
                0.4013928359127062,
                -0.17642994820313634,
                0.24641377275465212,
                -0.17642994820313634,
                0.4013928359127062,
            ],
        )
        np.testing.assert_allclose(
            first_snapshots[-1].state.velocity,
            [
                -0.1978509101772038,
                -0.006682706098361142,
                0.26130330652274586,
                -0.006682706098361142,
                -0.1978509101772038,
            ],
        )
        self.assertEqual(first_snapshots[-1].lifecycle_stage, STEP_COMPLETED_STAGE)
        self.assertEqual(first_result.final_snapshot.lifecycle_stage, FINALIZED_STAGE)
        self.assertLess(
            first_result.final_snapshot.diagnostics.energy,
            first_initial.diagnostics.energy,
        )
        np.testing.assert_allclose(
            first_solver.current_patch_state().activation,
            [0.4013928359127062, 0.03499191227575789, 0.11248144385478494],
            atol=1.0e-12,
        )
        self.assertEqual(len(first_result.diagnostics_history), 9)
        np.testing.assert_allclose(
            [item.diagnostics.energy for item in first_snapshots],
            [item.diagnostics.energy for item in second_snapshots],
        )
        np.testing.assert_allclose(
            first_result.final_snapshot.state.activation,
            second_result.final_snapshot.state.activation,
        )
        self.assertEqual(
            first_result.initialization.as_mapping(),
            second_result.initialization.as_mapping(),
        )
        self.assertEqual(
            first_result.runtime_metadata.source_reference,
            second_result.runtime_metadata.source_reference,
        )
        np.testing.assert_allclose(
            [item.activation_l2 for item in first_result.diagnostics_history],
            [item.activation_l2 for item in second_result.diagnostics_history],
        )
        np.testing.assert_allclose(
            [item.velocity_l2 for item in first_result.diagnostics_history],
            [item.velocity_l2 for item in second_result.diagnostics_history],
        )
        self.assertIs(first_result, first_solver.finalize())

        with self.assertRaises(ValueError):
            first_solver.step()

    def test_sparse_kernels_apply_surface_and_patch_state_deterministically(self) -> None:
        bundle = _build_fixture_operator_bundle()
        kernels = SurfaceWaveSparseKernels(bundle)
        surface_state = SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=np.asarray([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64),
            velocity=np.asarray([-1.0, 0.0, 1.0, 2.0, 3.0], dtype=np.float64),
        )

        surface_operator_state = kernels.apply_operator_to_state(surface_state)
        patch_state = kernels.project_state_to_patch(surface_state)
        projected_surface_state = kernels.project_state_to_surface(patch_state)

        self.assertEqual(patch_state.resolution, PATCH_STATE_RESOLUTION)
        np.testing.assert_allclose(
            surface_operator_state.activation,
            [-1.0, 0.0, 0.0, 0.0, 1.0],
        )
        np.testing.assert_allclose(
            patch_state.activation,
            [1.0, 2.5, 4.5],
        )
        np.testing.assert_allclose(
            patch_state.velocity,
            [-1.0, 0.5, 2.5],
        )
        np.testing.assert_allclose(
            kernels.apply_field(patch_state.activation, resolution=PATCH_STATE_RESOLUTION),
            [-1.5, -0.5, 2.0],
        )
        np.testing.assert_allclose(
            projected_surface_state.activation,
            [1.0, 2.5, 2.5, 4.5, 4.5],
        )

    def test_clamped_boundary_policy_zeros_boundary_state_and_drive(self) -> None:
        model = build_surface_wave_model_metadata(
            parameter_bundle={
                "parameter_preset": "clamped_fixture",
                "propagation": {
                    "wave_speed_sq_scale": 1.0,
                    "restoring_strength_per_ms2": 0.05,
                },
                "damping": {
                    "gamma_per_ms": 0.1,
                },
            }
        )
        bundle = _build_clamped_fixture_operator_bundle()
        solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=model,
            integration_timestep_ms=0.4,
        )

        initial_snapshot = solver.initialize_state(
            SurfaceWaveState(
                resolution=SURFACE_STATE_RESOLUTION,
                activation=np.asarray([3.0, 0.0, 0.0, 4.0], dtype=np.float64),
                velocity=np.zeros(4, dtype=np.float64),
            ),
            initialization_mode=EXPLICIT_STATE_INITIALIZATION,
        )
        stepped_snapshot = solver.step(surface_drive=np.ones(4, dtype=np.float64))

        self.assertEqual(initial_snapshot.state.activation.tolist(), [0.0, 0.0, 0.0, 0.0])
        np.testing.assert_allclose(
            stepped_snapshot.state.activation,
            [0.0, 0.15384615384615385, 0.15384615384615385, 0.0],
        )
        np.testing.assert_allclose(
            stepped_snapshot.state.velocity,
            [0.0, 0.3846153846153846, 0.3846153846153846, 0.0],
        )
        self.assertEqual(
            solver.runtime_metadata.boundary_condition_mode,
            CLAMPED_BOUNDARY_CONDITION_MODE,
        )

    def test_operator_bundle_loads_archive_paths_and_unstable_timestep_fails(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            archive_paths = _write_fixture_operator_archives(tmp_dir)
            bundle = SurfaceWaveOperatorBundle.from_operator_paths(
                root_id=303,
                fine_operator_path=archive_paths["fine_operator_path"],
                coarse_operator_path=archive_paths["coarse_operator_path"],
                transfer_operator_path=archive_paths["transfer_operator_path"],
                operator_metadata_path=archive_paths["operator_metadata_path"],
            )

            self.assertEqual(bundle.root_id, 303)
            self.assertEqual(bundle.surface_vertex_count, 5)
            self.assertEqual(bundle.patch_count, 3)
            self.assertEqual(bundle.boundary_condition_mode, DEFAULT_BOUNDARY_CONDITION_MODE)
            self.assertEqual(
                bundle.source_reference["fine_operator_path"],
                str(archive_paths["fine_operator_path"]),
            )

            with self.assertRaises(ValueError):
                SingleNeuronSurfaceWaveSolver(
                    operator_bundle=bundle,
                    surface_wave_model=_build_linear_fixture_model(),
                    integration_timestep_ms=0.7,
                )

    def test_recovery_mode_builds_recovery_state_and_damps_activation(self) -> None:
        model = build_surface_wave_model_metadata(
            parameter_bundle={
                "parameter_preset": "recovery_fixture",
                "propagation": {
                    "wave_speed_sq_scale": 1.0,
                    "restoring_strength_per_ms2": 0.0,
                },
                "damping": {
                    "gamma_per_ms": 0.0,
                },
                "recovery": {
                    "mode": "activity_driven_first_order",
                    "time_constant_ms": 4.0,
                    "drive_gain": 0.6,
                    "coupling_strength_per_ms2": 0.4,
                    "baseline": 0.1,
                },
            }
        )
        bundle = _build_zero_operator_bundle(size=1)
        solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=model,
            integration_timestep_ms=0.5,
        )

        initial = solver.initialize_state(
            SurfaceWaveState(
                resolution=SURFACE_STATE_RESOLUTION,
                activation=np.asarray([1.0], dtype=np.float64),
                velocity=np.asarray([0.0], dtype=np.float64),
            ),
            initialization_mode=EXPLICIT_STATE_INITIALIZATION,
        )
        first = solver.step()
        final = solver.finalize()

        self.assertIsNotNone(initial.state.recovery)
        self.assertAlmostEqual(float(initial.state.recovery[0]), 0.1)
        self.assertGreater(float(first.state.recovery[0]), 0.1)
        self.assertLess(float(final.final_snapshot.state.activation[0]), 1.0)
        self.assertEqual(final.runtime_metadata.recovery_mode, "activity_driven_first_order")
        self.assertTrue(final.runtime_metadata.recovery_summary["active"])
        self.assertGreater(first.diagnostics.recovery_drive_l2, 0.0)
        self.assertGreater(first.diagnostics.recovery_sink_l2, 0.0)

    def test_tanh_soft_clip_bounds_activation_and_reports_adjustment(self) -> None:
        model = build_surface_wave_model_metadata(
            parameter_bundle={
                "parameter_preset": "nonlinearity_fixture",
                "propagation": {
                    "wave_speed_sq_scale": 1.0,
                    "restoring_strength_per_ms2": 0.0,
                },
                "damping": {
                    "gamma_per_ms": 0.0,
                },
                "nonlinearity": {
                    "mode": "tanh_soft_clip",
                    "activation_scale": 1.0,
                },
            }
        )
        bundle = _build_zero_operator_bundle(size=1)
        solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=model,
            integration_timestep_ms=1.0,
        )

        solver.initialize_state(
            SurfaceWaveState(
                resolution=SURFACE_STATE_RESOLUTION,
                activation=np.asarray([0.0], dtype=np.float64),
                velocity=np.asarray([20.0], dtype=np.float64),
            ),
            initialization_mode=EXPLICIT_STATE_INITIALIZATION,
        )
        first = solver.step()

        self.assertLessEqual(abs(float(first.state.activation[0])), 1.0 + 1.0e-12)
        self.assertLessEqual(first.diagnostics.activation_peak_abs, 1.0 + 1.0e-12)
        self.assertGreater(first.diagnostics.nonlinear_adjustment_l2, 10.0)
        self.assertTrue(solver.runtime_metadata.nonlinearity_summary["active"])

    def test_operator_embedded_identity_anisotropy_matches_isotropic_solver(self) -> None:
        bundle = _build_identity_anisotropy_bundle()
        isotropic_model = _build_linear_fixture_model(parameter_preset="anisotropy_isotropic")
        anisotropic_model = build_surface_wave_model_metadata(
            parameter_bundle={
                "parameter_preset": "anisotropy_identity",
                "propagation": {
                    "wave_speed_sq_scale": 1.0,
                    "restoring_strength_per_ms2": 0.07,
                },
                "damping": {
                    "gamma_per_ms": 0.18,
                },
                "anisotropy": {
                    "mode": "operator_embedded",
                    "strength_scale": 1.0,
                },
            }
        )
        initial_state = SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=np.asarray([0.0, 1.0, 0.25, 0.0], dtype=np.float64),
            velocity=np.asarray([0.0, 0.0, 0.0, 0.0], dtype=np.float64),
        )

        isotropic_solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=isotropic_model,
            integration_timestep_ms=0.2,
        )
        anisotropic_solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=anisotropic_model,
            integration_timestep_ms=0.2,
        )
        isotropic_solver.initialize_state(initial_state, initialization_mode=EXPLICIT_STATE_INITIALIZATION)
        anisotropic_solver.initialize_state(initial_state, initialization_mode=EXPLICIT_STATE_INITIALIZATION)
        isotropic_final = [isotropic_solver.step() for _ in range(5)][-1]
        anisotropic_final = [anisotropic_solver.step() for _ in range(5)][-1]

        np.testing.assert_allclose(
            isotropic_final.state.activation,
            anisotropic_final.state.activation,
            atol=1.0e-10,
        )
        np.testing.assert_allclose(
            isotropic_final.state.velocity,
            anisotropic_final.state.velocity,
            atol=1.0e-10,
        )
        self.assertEqual(anisotropic_solver.runtime_metadata.anisotropy_mode, "operator_embedded")
        self.assertTrue(anisotropic_solver.runtime_metadata.anisotropy_summary["identity_equivalent"])
        self.assertAlmostEqual(anisotropic_final.diagnostics.anisotropy_delta_l2, 0.0, places=12)

    def test_branching_descriptor_scaled_damping_changes_energy_on_branch_sensitive_fixture(self) -> None:
        bundle = _build_branch_sensitive_bundle(branch_point_count=3)
        disabled_solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=_build_linear_fixture_model(parameter_preset="branching_disabled"),
            integration_timestep_ms=0.2,
        )
        branching_solver = SingleNeuronSurfaceWaveSolver(
            operator_bundle=bundle,
            surface_wave_model=build_surface_wave_model_metadata(
                parameter_bundle={
                    "parameter_preset": "branching_enabled",
                    "propagation": {
                        "wave_speed_sq_scale": 1.0,
                        "restoring_strength_per_ms2": 0.07,
                    },
                    "damping": {
                        "gamma_per_ms": 0.18,
                    },
                    "branching": {
                        "mode": "descriptor_scaled_damping",
                        "gain": 0.5,
                    },
                }
            ),
            integration_timestep_ms=0.2,
        )
        initial_state = SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=np.asarray([0.0, 1.0, 0.25, 0.0], dtype=np.float64),
            velocity=np.zeros(4, dtype=np.float64),
        )
        disabled_solver.initialize_state(initial_state, initialization_mode=EXPLICIT_STATE_INITIALIZATION)
        branching_solver.initialize_state(initial_state, initialization_mode=EXPLICIT_STATE_INITIALIZATION)
        disabled_final = [disabled_solver.step() for _ in range(6)][-1]
        branching_final = [branching_solver.step() for _ in range(6)][-1]

        self.assertLess(branching_final.diagnostics.energy, disabled_final.diagnostics.energy)
        self.assertGreater(branching_final.diagnostics.branching_sink_l2, 0.0)
        self.assertEqual(branching_solver.runtime_metadata.branching_mode, "descriptor_scaled_damping")
        self.assertEqual(branching_solver.runtime_metadata.branching_summary["branch_point_count"], 3)
        self.assertGreater(branching_solver.runtime_metadata.branching_summary["local_damping_max"], 0.0)

    def test_missing_anisotropy_or_branching_assets_fail_clearly(self) -> None:
        with self.assertRaises(ValueError) as anisotropy_ctx:
            SingleNeuronSurfaceWaveSolver(
                operator_bundle=_build_fixture_operator_bundle(),
                surface_wave_model=build_surface_wave_model_metadata(
                    parameter_bundle={
                        "parameter_preset": "missing_anisotropy_assets",
                        "anisotropy": {
                            "mode": "operator_embedded",
                            "strength_scale": 1.0,
                        },
                    }
                ),
                integration_timestep_ms=0.2,
            )
        self.assertIn("serialized edge weights plus anisotropy multipliers", str(anisotropy_ctx.exception))

        with self.assertRaises(ValueError) as branching_ctx:
            SingleNeuronSurfaceWaveSolver(
                operator_bundle=_build_fixture_operator_bundle(),
                surface_wave_model=build_surface_wave_model_metadata(
                    parameter_bundle={
                        "parameter_preset": "missing_branch_assets",
                        "branching": {
                            "mode": "descriptor_scaled_damping",
                            "gain": 0.25,
                        },
                    }
                ),
                integration_timestep_ms=0.2,
            )
        self.assertIn("requires loaded geometry descriptors", str(branching_ctx.exception))


def _build_linear_fixture_model(*, parameter_preset: str = "m10_linear_fixture") -> dict[str, object]:
    return build_surface_wave_model_metadata(
        parameter_bundle={
            "parameter_preset": parameter_preset,
            "propagation": {
                "wave_speed_sq_scale": 1.0,
                "restoring_strength_per_ms2": 0.07,
            },
            "damping": {
                "gamma_per_ms": 0.18,
            },
        }
    )


def _build_fixture_operator_bundle() -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=101,
        surface_operator=_fixture_surface_operator(),
        coarse_operator=_fixture_coarse_operator(),
        restriction=_fixture_restriction(),
        prolongation=_fixture_prolongation(),
        mass_diagonal=np.ones(5, dtype=np.float64),
        patch_mass_diagonal=np.ones(3, dtype=np.float64),
        surface_to_patch=np.asarray([0, 1, 1, 2, 2], dtype=np.int32),
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _build_clamped_fixture_operator_bundle() -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=202,
        surface_operator=sp.csr_matrix(
            [
                [1.0, -1.0, 0.0, 0.0],
                [-1.0, 2.0, -1.0, 0.0],
                [0.0, -1.0, 2.0, -1.0],
                [0.0, 0.0, -1.0, 1.0],
            ],
            dtype=np.float64,
        ),
        boundary_vertex_mask=np.asarray([True, False, False, True], dtype=bool),
        boundary_condition_mode=CLAMPED_BOUNDARY_CONDITION_MODE,
    )


def _build_zero_operator_bundle(*, size: int) -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=404,
        surface_operator=sp.csr_matrix((size, size), dtype=np.float64),
        mass_diagonal=np.ones(size, dtype=np.float64),
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _build_identity_anisotropy_bundle() -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=505,
        surface_operator=_path_surface_operator([1.0, 1.0, 1.0]),
        mass_diagonal=np.ones(4, dtype=np.float64),
        surface_to_patch=np.asarray([0, 1, 1, 2], dtype=np.int32),
        edge_vertex_indices=np.asarray([[0, 1], [1, 2], [2, 3]], dtype=np.int32),
        cotangent_weights=np.asarray([1.0, 1.0, 1.0], dtype=np.float64),
        anisotropy_edge_multiplier=np.asarray([1.0, 1.0, 1.0], dtype=np.float64),
        operator_metadata={
            "anisotropy_model": "local_tangent_diagonal",
        },
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _build_branch_sensitive_bundle(*, branch_point_count: int) -> SurfaceWaveOperatorBundle:
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=606,
        surface_operator=_path_surface_operator([1.0, 1.0, 1.0]),
        mass_diagonal=np.ones(4, dtype=np.float64),
        surface_to_patch=np.asarray([0, 0, 1, 2], dtype=np.int32),
        geometry_descriptors={
            "descriptor_version": "geometry_descriptor.v1",
            "representations": {
                "skeleton": {
                    "available": True,
                    "branch_point_count": int(branch_point_count),
                    "leaf_count": 4,
                    "root_count": 1,
                    "total_cable_length": 10.0,
                }
            },
        },
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
    )


def _fixture_surface_operator() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, -1.0, 0.0, 0.0, 0.0],
            [-1.0, 2.0, -1.0, 0.0, 0.0],
            [0.0, -1.0, 2.0, -1.0, 0.0],
            [0.0, 0.0, -1.0, 2.0, -1.0],
            [0.0, 0.0, 0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )


def _fixture_coarse_operator() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, -1.0, 0.0],
            [-1.0, 2.0, -1.0],
            [0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )


def _fixture_restriction() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.5, 0.5, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.5, 0.5],
        ],
        dtype=np.float64,
    )


def _fixture_prolongation() -> sp.csr_matrix:
    return sp.csr_matrix(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _path_surface_operator(weights: list[float]) -> sp.csr_matrix:
    diagonal = np.zeros(len(weights) + 1, dtype=np.float64)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for edge_index, weight in enumerate(weights):
        i = edge_index
        j = edge_index + 1
        diagonal[i] += float(weight)
        diagonal[j] += float(weight)
        rows.extend([i, j])
        cols.extend([j, i])
        data.extend([-float(weight), -float(weight)])
    for vertex_index, value in enumerate(diagonal):
        rows.append(vertex_index)
        cols.append(vertex_index)
        data.append(float(value))
    return sp.csr_matrix(
        (
            np.asarray(data, dtype=np.float64),
            (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32)),
        ),
        shape=(len(weights) + 1, len(weights) + 1),
        dtype=np.float64,
    )


def _write_fixture_operator_archives(tmp_dir: Path) -> dict[str, Path]:
    fine_operator_path = tmp_dir / "303_fine_operator.npz"
    coarse_operator_path = tmp_dir / "303_coarse_operator.npz"
    transfer_operator_path = tmp_dir / "303_transfer_operators.npz"
    operator_metadata_path = tmp_dir / "303_operator_metadata.json"

    write_deterministic_npz(
        {
            "root_id": np.asarray([303], dtype=np.int64),
            "mass_diagonal": np.ones(5, dtype=np.float64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(_fixture_surface_operator()).items()
            },
        },
        fine_operator_path,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([303], dtype=np.int64),
            "mass_diagonal": np.ones(3, dtype=np.float64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(_fixture_coarse_operator()).items()
            },
        },
        coarse_operator_path,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([303], dtype=np.int64),
            "surface_to_patch": np.asarray([0, 1, 1, 2, 2], dtype=np.int32),
            **{
                f"restriction_{key}": value
                for key, value in serialize_sparse_matrix(_fixture_restriction()).items()
            },
            **{
                f"prolongation_{key}": value
                for key, value in serialize_sparse_matrix(_fixture_prolongation()).items()
            },
        },
        transfer_operator_path,
    )
    write_json(
        {
            "boundary_condition_mode": DEFAULT_BOUNDARY_CONDITION_MODE,
            "realization_mode": "fixture_mass_normalized_surface_operator",
        },
        operator_metadata_path,
    )
    return {
        "fine_operator_path": fine_operator_path.resolve(),
        "coarse_operator_path": coarse_operator_path.resolve(),
        "transfer_operator_path": transfer_operator_path.resolve(),
        "operator_metadata_path": operator_metadata_path.resolve(),
    }


if __name__ == "__main__":
    unittest.main()
