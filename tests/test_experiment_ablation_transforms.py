from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.experiment_ablation_transforms import (
    ALTERED_DELAY_SCALE_TRANSFORM_MODE,
    ALTERED_DELAY_ZERO_TRANSFORM_MODE,
    ALTERED_SIGN_TRANSFORM_MODE,
    COARSEN_GEOMETRY_TRANSFORM_MODE,
    EXPERIMENT_SUITE_ABLATION_CONFIG_KEY,
    NO_LATERAL_COUPLING_TRANSFORM_MODE,
    NO_WAVES_TRANSFORM_MODE,
    SHUFFLE_MORPHOLOGY_TRANSFORM_MODE,
    SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE,
    WAVES_ONLY_SELECTED_CELL_CLASSES_TRANSFORM_MODE,
    apply_experiment_ablation_coupling_perturbation,
    apply_experiment_ablation_to_arm_payload,
    apply_experiment_ablation_to_arm_plan,
    build_experiment_ablation_realization,
    materialize_experiment_ablation_realization_for_seed,
    resolve_experiment_ablation_patch_permutations,
)
from flywire_wave.experiment_suite_contract import (
    ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
    ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
    COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
    NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
    NO_WAVES_ABLATION_FAMILY_ID,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
    SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
    WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
)
from flywire_wave.experiment_suite_execution import (
    _build_materialized_config_payload,
    build_experiment_suite_execution_schedule,
)
from flywire_wave.experiment_suite_planning import resolve_experiment_suite_plan
from flywire_wave.hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from flywire_wave.io_utils import write_json
from flywire_wave.simulation_planning import resolve_manifest_simulation_plan
from flywire_wave.stimulus_contract import ASSET_STATUS_READY

try:
    from tests.test_experiment_suite_planning import (  # type: ignore[no-redef]
        _base_suite_block,
        _write_suite_manifest_fixture,
    )
except ModuleNotFoundError:
    from test_experiment_suite_planning import (  # type: ignore[no-redef]
        _base_suite_block,
        _write_suite_manifest_fixture,
    )

try:
    from tests.simulation_planning_test_support import (  # type: ignore[no-redef]
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
        _write_skeleton_fixture,
    )
except ModuleNotFoundError:
    from simulation_planning_test_support import (  # type: ignore[no-redef]
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
        _write_skeleton_fixture,
    )


class ExperimentAblationTransformsTest(unittest.TestCase):
    def test_required_ablation_families_realize_deterministically_from_fixture_plan(
        self,
    ) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            root_specs = [
                {
                    "root_id": 101,
                    "cell_type": "class_a",
                    "project_role": "surface_simulated",
                    "asset_profile": "surface",
                },
                {
                    "root_id": 202,
                    "cell_type": "class_b",
                    "project_role": "surface_simulated",
                    "asset_profile": "surface",
                },
            ]
            _, config_path, base_plan = self._resolve_fixture_simulation_plan(
                tmp_dir=tmp_dir,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                root_specs=root_specs,
                manifest_overrides={"seed_sweep": [11, 17], "random_seed": 11},
            )
            base_cell = self._base_suite_cell()
            surface_wave_arm = self._surface_wave_arm_plan(base_plan)
            surface_wave_payload = self._surface_wave_arm_payload()

            no_waves = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=NO_WAVES_ABLATION_FAMILY_ID,
                    variant_id="disabled",
                    display_name="No Waves",
                ),
                base_simulation_plan=base_plan,
            )
            self._assert_common_provenance(
                no_waves,
                family_id=NO_WAVES_ABLATION_FAMILY_ID,
                variant_id="disabled",
            )
            self.assertEqual(
                no_waves["realization_policy"]["mode"],
                NO_WAVES_TRANSFORM_MODE,
            )
            self.assertEqual(
                no_waves["target_root_cell_types"],
                {101: "class_a", 202: "class_b"},
            )
            self.assertEqual(
                apply_experiment_ablation_to_arm_payload(
                    arm_payload=surface_wave_payload,
                    realization=no_waves,
                )["fidelity_assignment"],
                {
                    "default_morphology_class": POINT_NEURON_CLASS,
                    "root_overrides": [],
                },
            )

            waves_only = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
                    variant_id="selected_subset_only",
                    display_name="Waves Only Selected Cell Classes",
                    parameter_snapshot={"target_cell_classes": ["class_a"]},
                ),
                base_simulation_plan=base_plan,
            )
            self._assert_common_provenance(
                waves_only,
                family_id=WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
                variant_id="selected_subset_only",
            )
            self.assertEqual(
                waves_only["realization_policy"]["mode"],
                WAVES_ONLY_SELECTED_CELL_CLASSES_TRANSFORM_MODE,
            )
            self.assertEqual(
                waves_only["realization_policy"]["target_cell_classes"],
                ["class_a"],
            )
            self.assertEqual(
                waves_only["realization_policy"]["preserved_root_morphology_classes"],
                {"101": SURFACE_NEURON_CLASS},
            )
            self.assertEqual(
                apply_experiment_ablation_to_arm_payload(
                    arm_payload=surface_wave_payload,
                    realization=waves_only,
                )["fidelity_assignment"],
                {
                    "default_morphology_class": POINT_NEURON_CLASS,
                    "root_overrides": [
                        {
                            "root_id": 101,
                            "morphology_class": SURFACE_NEURON_CLASS,
                        }
                    ],
                },
            )

            no_lateral_coupling = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
                    variant_id="disabled",
                    display_name="No Lateral Coupling",
                ),
                base_simulation_plan=base_plan,
            )
            self._assert_common_provenance(
                no_lateral_coupling,
                family_id=NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
                variant_id="disabled",
            )
            self.assertEqual(
                no_lateral_coupling["realization_policy"]["mode"],
                NO_LATERAL_COUPLING_TRANSFORM_MODE,
            )
            self.assertGreater(
                no_lateral_coupling["realization_policy"]["removed_inter_root_edge_count"],
                0,
            )
            no_lateral_plan = apply_experiment_ablation_to_arm_plan(
                arm_plan=surface_wave_arm,
                realization=no_lateral_coupling,
            )
            no_lateral_execution = no_lateral_plan["model_configuration"][
                "surface_wave_execution_plan"
            ]
            self.assertTrue(
                all(
                    not asset["selected_edge_bundle_paths"]
                    for asset in no_lateral_execution["selected_root_coupling_assets"]
                )
            )
            self.assertTrue(
                all(
                    not assignment["coupling_asset"]["selected_edge_bundle_paths"]
                    for assignment in no_lateral_execution["mixed_fidelity"][
                        "per_root_assignments"
                    ]
                )
            )
            self.assertEqual(
                no_lateral_execution["ablation_transform"]["transform_id"],
                "no_lateral_coupling__disabled",
            )

            shuffle_synapse_locations = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
                    variant_id="shuffled",
                    display_name="Shuffle Synapse Locations",
                ),
                base_simulation_plan=base_plan,
                perturbation_seed_by_simulation_seed={11: 701, 17: 703},
            )
            self._assert_common_provenance(
                shuffle_synapse_locations,
                family_id=SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
                variant_id="shuffled",
            )
            self.assertEqual(
                shuffle_synapse_locations["realization_policy"]["mode"],
                SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE,
            )
            self.assertEqual(
                shuffle_synapse_locations["perturbation_seed_by_simulation_seed"],
                {11: 701, 17: 703},
            )
            materialized_shuffle_synapse = (
                materialize_experiment_ablation_realization_for_seed(
                    shuffle_synapse_locations,
                    simulation_seed=11,
                )
            )
            self.assertEqual(
                materialized_shuffle_synapse["perturbation_seed"],
                701,
            )
            self.assertEqual(
                materialized_shuffle_synapse,
                materialize_experiment_ablation_realization_for_seed(
                    shuffle_synapse_locations,
                    simulation_seed=11,
                ),
            )
            patch_permutations = resolve_experiment_ablation_patch_permutations(
                materialized_shuffle_synapse
            )
            self.assertEqual(sorted(patch_permutations), [101, 202])
            self.assertEqual(
                patch_permutations,
                {
                    root_id: tuple(reversed(sorted(values)))
                    for root_id, values in patch_permutations.items()
                },
            )
            shuffled_payload = apply_experiment_ablation_to_arm_payload(
                arm_payload=surface_wave_payload,
                realization=materialized_shuffle_synapse,
            )
            self.assertEqual(shuffled_payload["topology_condition"], "shuffled")
            self.assertEqual(
                shuffled_payload["morphology_condition"],
                "shuffled_synapse_landing_geometry",
            )

            shuffle_morphology = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
                    variant_id="shuffled",
                    display_name="Shuffle Morphology",
                ),
                base_simulation_plan=base_plan,
                perturbation_seed_by_simulation_seed={11: 811, 17: 813},
            )
            self._assert_common_provenance(
                shuffle_morphology,
                family_id=SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
                variant_id="shuffled",
            )
            self.assertEqual(
                shuffle_morphology["realization_policy"]["mode"],
                SHUFFLE_MORPHOLOGY_TRANSFORM_MODE,
            )
            materialized_shuffle_morphology = (
                materialize_experiment_ablation_realization_for_seed(
                    shuffle_morphology,
                    simulation_seed=11,
                )
            )
            self.assertEqual(
                materialized_shuffle_morphology["perturbation_seed"],
                811,
            )
            self.assertEqual(
                materialized_shuffle_morphology["realization_policy"][
                    "operator_asset_donor_root_by_target_root"
                ],
                {"101": 202, "202": 101},
            )
            original_operator_assets = {
                int(asset["root_id"]): asset
                for asset in surface_wave_arm["model_configuration"][
                    "surface_wave_execution_plan"
                ]["selected_root_operator_assets"]
            }
            original_required_assets = {
                int(item["root_id"]): item["required_local_assets"]
                for item in surface_wave_arm["model_configuration"][
                    "surface_wave_execution_plan"
                ]["mixed_fidelity"]["per_root_assignments"]
            }
            shuffled_morphology_plan = apply_experiment_ablation_to_arm_plan(
                arm_plan=surface_wave_arm,
                realization=materialized_shuffle_morphology,
            )
            shuffled_execution = shuffled_morphology_plan["model_configuration"][
                "surface_wave_execution_plan"
            ]
            mutated_operator_assets = {
                int(asset["root_id"]): asset
                for asset in shuffled_execution["selected_root_operator_assets"]
            }
            mutated_required_assets = {
                int(item["root_id"]): item["required_local_assets"]
                for item in shuffled_execution["mixed_fidelity"]["per_root_assignments"]
            }
            self.assertEqual(
                mutated_operator_assets[101]["coarse_operator_path"],
                original_operator_assets[202]["coarse_operator_path"],
            )
            self.assertEqual(
                mutated_required_assets[101]["processed_surface_mesh"]["path"],
                original_required_assets[202]["processed_surface_mesh"]["path"],
            )
            self.assertEqual(
                shuffled_execution["ablation_transform"]["perturbation_seed"],
                811,
            )

            self._mark_surface_skeletons_ready(
                tmp_dir=tmp_dir,
                root_ids=[101, 202],
            )
            coarsened_plan = resolve_manifest_simulation_plan(
                manifest_path=tmp_dir / "fixture_manifest.yaml",
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            coarsen_geometry = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
                    variant_id="coarse",
                    display_name="Coarsen Geometry",
                ),
                base_simulation_plan=coarsened_plan,
            )
            self._assert_common_provenance(
                coarsen_geometry,
                family_id=COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
                variant_id="coarse",
            )
            self.assertEqual(
                coarsen_geometry["realization_policy"]["mode"],
                COARSEN_GEOMETRY_TRANSFORM_MODE,
            )
            self.assertEqual(
                coarsen_geometry["realization_policy"]["coarsened_root_ids"],
                [101, 202],
            )
            self.assertEqual(
                apply_experiment_ablation_to_arm_payload(
                    arm_payload=surface_wave_payload,
                    realization=coarsen_geometry,
                )["fidelity_assignment"],
                {
                    "root_overrides": [
                        {
                            "root_id": 101,
                            "morphology_class": SKELETON_NEURON_CLASS,
                        },
                        {
                            "root_id": 202,
                            "morphology_class": SKELETON_NEURON_CLASS,
                        },
                    ]
                },
            )

            altered_sign = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
                    variant_id="sign_inversion_probe",
                    display_name="Altered Sign Assumptions",
                    parameter_snapshot={"sign_mode": "sign_inversion_probe"},
                ),
                base_simulation_plan=base_plan,
            )
            self._assert_common_provenance(
                altered_sign,
                family_id=ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
                variant_id="sign_inversion_probe",
            )
            self.assertEqual(
                altered_sign["realization_policy"]["mode"],
                ALTERED_SIGN_TRANSFORM_MODE,
            )
            self.assertEqual(
                apply_experiment_ablation_coupling_perturbation(
                    altered_sign,
                    sign_label="excitatory",
                    signed_weight_total=1.5,
                    delay_ms=3.0,
                ),
                ("inhibitory", -1.5, 3.0),
            )

            zero_delay = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
                    variant_id="zero_delay_probe",
                    display_name="Zero Delay Probe",
                    parameter_snapshot={"delay_mode": "zero_delay_probe"},
                ),
                base_simulation_plan=base_plan,
            )
            self._assert_common_provenance(
                zero_delay,
                family_id=ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
                variant_id="zero_delay_probe",
            )
            self.assertEqual(
                zero_delay["realization_policy"]["mode"],
                ALTERED_DELAY_ZERO_TRANSFORM_MODE,
            )
            self.assertEqual(
                apply_experiment_ablation_coupling_perturbation(
                    zero_delay,
                    sign_label="inhibitory",
                    signed_weight_total=-2.0,
                    delay_ms=4.0,
                ),
                ("inhibitory", -2.0, 0.0),
            )

            half_delay = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=self._declaration(
                    ablation_family_id=ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
                    variant_id="delay_scale_half_probe",
                    display_name="Half Delay Probe",
                    parameter_snapshot={
                        "delay_mode": "delay_scale_half_probe",
                        "delay_scale_factor": 0.5,
                    },
                ),
                base_simulation_plan=base_plan,
            )
            self._assert_common_provenance(
                half_delay,
                family_id=ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
                variant_id="delay_scale_half_probe",
            )
            self.assertEqual(
                half_delay["realization_policy"]["mode"],
                ALTERED_DELAY_SCALE_TRANSFORM_MODE,
            )
            self.assertEqual(
                apply_experiment_ablation_coupling_perturbation(
                    half_delay,
                    sign_label="inhibitory",
                    signed_weight_total=-2.0,
                    delay_ms=4.0,
                ),
                ("inhibitory", -2.0, 2.0),
            )

    def test_ablation_transform_failures_are_explicit_for_missing_prerequisites_and_unsupported_requests(
        self,
    ) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with self.subTest("missing_cell_class_assignments"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                _, _, plan = self._resolve_fixture_simulation_plan(
                    tmp_dir=tmp_dir,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                    root_specs=[
                        {
                            "root_id": 101,
                            "cell_type": "",
                            "project_role": "surface_simulated",
                            "asset_profile": "surface",
                        },
                        {
                            "root_id": 202,
                            "cell_type": "class_b",
                            "project_role": "surface_simulated",
                            "asset_profile": "surface",
                        },
                    ],
                )
                with self.assertRaises(ValueError) as ctx:
                    build_experiment_ablation_realization(
                        base_cell=self._base_suite_cell(),
                        declaration=self._declaration(
                            ablation_family_id=WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
                            variant_id="selected_subset_only",
                            display_name="Waves Only Selected Cell Classes",
                            parameter_snapshot={"target_cell_classes": ["class_a"]},
                        ),
                        base_simulation_plan=plan,
                    )
                self.assertIn(
                    "requires cell-type assignments",
                    str(ctx.exception),
                )

        with self.subTest("missing_coupling_bundles"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                _, _, plan = self._resolve_fixture_simulation_plan(
                    tmp_dir=tmp_dir,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                couplingless_plan = copy.deepcopy(plan)
                for arm in couplingless_plan["arm_plans"]:
                    if arm["arm_reference"]["model_mode"] != "surface_wave":
                        continue
                    execution = arm["model_configuration"]["surface_wave_execution_plan"]
                    for asset in execution["selected_root_coupling_assets"]:
                        asset["selected_edge_bundle_paths"] = []
                    for assignment in execution["mixed_fidelity"]["per_root_assignments"]:
                        assignment["coupling_asset"]["selected_edge_bundle_paths"] = []
                with self.assertRaises(ValueError) as ctx:
                    build_experiment_ablation_realization(
                        base_cell=self._base_suite_cell(),
                        declaration=self._declaration(
                            ablation_family_id=NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
                            variant_id="disabled",
                            display_name="No Lateral Coupling",
                        ),
                        base_simulation_plan=couplingless_plan,
                    )
                self.assertIn(
                    "does not expose any inter-root coupling edges",
                    str(ctx.exception),
                )

        with self.subTest("missing_skeleton_variants"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                _, _, plan = self._resolve_fixture_simulation_plan(
                    tmp_dir=tmp_dir,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    build_experiment_ablation_realization(
                        base_cell=self._base_suite_cell(),
                        declaration=self._declaration(
                            ablation_family_id=COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
                            variant_id="coarse",
                            display_name="Coarsen Geometry",
                        ),
                        base_simulation_plan=plan,
                    )
                self.assertIn(
                    "raw skeleton variants",
                    str(ctx.exception),
                )

        with self.subTest("unsupported_sign_mode"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                _, _, plan = self._resolve_fixture_simulation_plan(
                    tmp_dir=tmp_dir,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    build_experiment_ablation_realization(
                        base_cell=self._base_suite_cell(),
                        declaration=self._declaration(
                            ablation_family_id=ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
                            variant_id="sign_inversion_probe",
                            display_name="Altered Sign Assumptions",
                            parameter_snapshot={"sign_mode": "unsupported_mode"},
                        ),
                        base_simulation_plan=plan,
                    )
                self.assertIn(
                    "currently supports only sign_mode='sign_inversion_probe'",
                    str(ctx.exception),
                )

        with self.subTest("unsupported_delay_scale_request"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                _, _, plan = self._resolve_fixture_simulation_plan(
                    tmp_dir=tmp_dir,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    build_experiment_ablation_realization(
                        base_cell=self._base_suite_cell(),
                        declaration=self._declaration(
                            ablation_family_id=ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
                            variant_id="delay_scale_half_probe",
                            display_name="Half Delay Probe",
                            parameter_snapshot={"delay_scale_factor": 0.25},
                        ),
                        base_simulation_plan=plan,
                    )
                self.assertIn(
                    "delay_scale_factor=0.5",
                    str(ctx.exception),
                )

    def test_seeded_suite_cells_carry_ablation_realization_and_materialized_config(
        self,
    ) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"seed_sweep": [11, 17], "random_seed": 11},
            )
            config_path = _write_simulation_fixture(tmp_dir)
            _record_fixture_stimulus_bundle(
                manifest_path=manifest_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            suite_manifest_path = _write_suite_manifest_fixture(
                tmp_dir=tmp_dir,
                manifest_path=manifest_path,
                suite_block=_base_suite_block(
                    output_root=tmp_dir / "out" / "suite_ablation_fixture",
                ),
            )
            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            seeded_shuffle_cell = next(
                item
                for item in plan["cell_catalog"]
                if item["lineage_kind"] == SEEDED_ABLATION_VARIANT_LINEAGE_KIND
                and any(
                    reference["ablation_family_id"] == SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID
                    for reference in item["ablation_references"]
                )
            )
            realization = seeded_shuffle_cell["ablation_realization"]
            self.assertIsNotNone(realization)
            self.assertEqual(
                realization["transform_id"],
                "shuffle_morphology__shuffled",
            )
            self.assertNotEqual(
                realization["perturbation_seed"],
                seeded_shuffle_cell["simulation_seed"],
            )
            schedule = build_experiment_suite_execution_schedule(plan)
            schedule_entry = next(
                item
                for item in schedule["schedule"]
                if item["suite_cell_id"] == seeded_shuffle_cell["suite_cell_id"]
                and item["stage_id"] == "simulation"
            )
            materialized_config = _build_materialized_config_payload(
                plan=plan,
                schedule_entry=schedule_entry,
            )
            self.assertEqual(
                materialized_config[EXPERIMENT_SUITE_ABLATION_CONFIG_KEY],
                realization,
            )

    def _resolve_fixture_simulation_plan(
        self,
        *,
        tmp_dir: Path,
        schema_path: Path,
        design_lock_path: Path,
        root_specs: list[dict[str, object]] | None = None,
        manifest_overrides: dict[str, object] | None = None,
    ) -> tuple[Path, Path, dict[str, object]]:
        manifest_path = _write_manifest_fixture(
            tmp_dir,
            manifest_overrides=manifest_overrides,
        )
        config_path = _write_simulation_fixture(
            tmp_dir,
            root_specs=root_specs,
        )
        _record_fixture_stimulus_bundle(
            manifest_path=manifest_path,
            processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
        return (
            manifest_path,
            config_path,
            resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            ),
        )

    def _mark_surface_skeletons_ready(
        self,
        *,
        tmp_dir: Path,
        root_ids: list[int],
    ) -> None:
        asset_manifest_path = (tmp_dir / "out" / "asset_manifest.json").resolve()
        manifest_payload = json.loads(asset_manifest_path.read_text(encoding="utf-8"))
        for root_id in root_ids:
            record = manifest_payload[str(int(root_id))]
            record["assets"]["raw_skeleton"]["status"] = ASSET_STATUS_READY
            _write_skeleton_fixture(Path(record["raw_skeleton_path"]))
        write_json(manifest_payload, asset_manifest_path)

    def _assert_common_provenance(
        self,
        realization: dict[str, object],
        *,
        family_id: str,
        variant_id: str,
    ) -> None:
        self.assertEqual(realization["source_suite_cell_id"], "base_fixture")
        self.assertEqual(realization["ablation_family_id"], family_id)
        self.assertEqual(realization["variant_id"], variant_id)
        self.assertEqual(realization["transform_id"], f"{family_id}__{variant_id}")
        self.assertTrue(realization["perturbed_inputs"])
        self.assertTrue(realization["validated_prerequisites"])

    def _surface_wave_arm_plan(self, plan: dict[str, object]) -> dict[str, object]:
        return next(
            item
            for item in plan["arm_plans"]
            if item["arm_reference"]["arm_id"] == "surface_wave_intact"
        )

    def _surface_wave_arm_payload(self) -> dict[str, object]:
        return {
            "arm_id": "surface_wave_intact",
            "model_mode": "surface_wave",
            "topology_condition": "intact",
            "morphology_condition": "intact",
            "fidelity_assignment": {
                "default_morphology_class": SURFACE_NEURON_CLASS,
                "root_overrides": [],
            },
        }

    def _base_suite_cell(self) -> dict[str, str]:
        return {
            "suite_cell_id": "base_fixture",
            "lineage_kind": "base_condition",
        }

    def _declaration(
        self,
        *,
        ablation_family_id: str,
        variant_id: str,
        display_name: str,
        parameter_snapshot: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "ablation_family_id": ablation_family_id,
            "variant_id": variant_id,
            "display_name": display_name,
            "parameter_snapshot": (
                {} if parameter_snapshot is None else copy.deepcopy(parameter_snapshot)
            ),
        }


if __name__ == "__main__":
    unittest.main()
