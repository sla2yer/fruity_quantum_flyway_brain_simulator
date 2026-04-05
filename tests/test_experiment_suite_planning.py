from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    ACTIVE_SUBSET_DIMENSION_ID,
    BASE_CONDITION_LINEAGE_KIND,
    CONTRAST_LEVEL_DIMENSION_ID,
    MESH_RESOLUTION_DIMENSION_ID,
    MOTION_DIRECTION_DIMENSION_ID,
    MOTION_SPEED_DIMENSION_ID,
    NOISE_LEVEL_DIMENSION_ID,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SEED_REPLICATE_LINEAGE_KIND,
)
from flywire_wave.experiment_suite_planning import (
    EXPERIMENT_SUITE_CONFIG_VERSION,
    EXPERIMENT_SUITE_MANIFEST_FORMAT,
    EXPERIMENT_SUITE_PLAN_VERSION,
    resolve_experiment_suite_plan,
)
from flywire_wave.selection import build_subset_artifact_paths
from flywire_wave.simulation_planning import SIMULATION_PLAN_VERSION
try:
    from tests.test_simulation_planning import (
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )
except ModuleNotFoundError:
    from test_simulation_planning import (  # type: ignore[no-redef]
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )


class ExperimentSuitePlanningTest(unittest.TestCase):
    def test_suite_manifest_resolution_is_deterministic_and_records_stable_cell_ordering(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(tmp_dir)
            config_path = _write_simulation_fixture(
                tmp_dir,
                experiment_suite_config={
                    "version": EXPERIMENT_SUITE_CONFIG_VERSION,
                    "enabled_stage_ids": ["simulation", "analysis"],
                    "output_root": str(tmp_dir / "out" / "suite_config_default"),
                    "seed_policy": {
                        "simulation_seed_source": "manifest_seed_sweep",
                        "reuse_scope": "shared_across_suite",
                        "perturbation_seed_mode": "derived_offset",
                        "perturbation_seed_offset": 70000,
                    },
                },
            )
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
                    output_root=tmp_dir / "out" / "suite_manifest_override",
                    enabled_stage_ids=["simulation", "analysis", "validation"],
                ),
            )

            first_plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            second_plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            self.assertEqual(first_plan, second_plan)
            self.assertEqual(first_plan["plan_version"], EXPERIMENT_SUITE_PLAN_VERSION)
            self.assertEqual(
                first_plan["base_simulation_plan"]["plan_version"],
                SIMULATION_PLAN_VERSION,
            )
            self.assertEqual(
                first_plan["suite_source"]["source_kind"],
                "suite_manifest",
            )
            self.assertEqual(
                first_plan["output_roots"]["suite_root"],
                str((tmp_dir / "out" / "suite_manifest_override").resolve()),
            )
            self.assertEqual(
                [item["stage_id"] for item in first_plan["stage_targets"]],
                ["simulation", "analysis", "validation"],
            )

            active_dimensions = {
                item["dimension_id"]: item for item in first_plan["active_dimensions"]
            }
            self.assertTrue(active_dimensions[MOTION_DIRECTION_DIMENSION_ID]["is_swept"])
            self.assertEqual(
                active_dimensions[MOTION_DIRECTION_DIMENSION_ID]["expansion_mode"],
                "cross_product",
            )
            self.assertTrue(active_dimensions[MOTION_SPEED_DIMENSION_ID]["is_swept"])
            self.assertEqual(
                active_dimensions[CONTRAST_LEVEL_DIMENSION_ID]["expansion_mode"],
                "linked",
            )
            self.assertEqual(
                active_dimensions[MESH_RESOLUTION_DIMENSION_ID]["default_value"]["value_id"],
                "fine",
            )
            self.assertEqual(
                active_dimensions[ACTIVE_SUBSET_DIMENSION_ID]["default_value"]["value_id"],
                "motion_minimal",
            )

            base_cells = [
                item
                for item in first_plan["cell_catalog"]
                if item["lineage_kind"] == BASE_CONDITION_LINEAGE_KIND
            ]
            seed_cells = [
                item
                for item in first_plan["cell_catalog"]
                if item["lineage_kind"] == SEED_REPLICATE_LINEAGE_KIND
            ]
            ablation_cells = [
                item
                for item in first_plan["cell_catalog"]
                if item["lineage_kind"] == ABLATION_VARIANT_LINEAGE_KIND
            ]
            seeded_ablation_cells = [
                item
                for item in first_plan["cell_catalog"]
                if item["lineage_kind"] == SEEDED_ABLATION_VARIANT_LINEAGE_KIND
            ]

            self.assertEqual(len(base_cells), 8)
            self.assertEqual(len(seed_cells), 24)
            self.assertEqual(len(ablation_cells), 12)
            self.assertEqual(len(seeded_ablation_cells), 36)
            self.assertEqual(len(first_plan["suite_cells"]), 80)
            self.assertEqual(len(first_plan["work_items"]), 100)

            first_base = base_cells[0]["selected_dimension_values"]
            last_base = base_cells[-1]["selected_dimension_values"]
            self.assertEqual(first_base[MOTION_DIRECTION_DIMENSION_ID]["value_id"], "null")
            self.assertEqual(first_base[MOTION_SPEED_DIMENSION_ID]["value_id"], "fast")
            self.assertEqual(first_base[CONTRAST_LEVEL_DIMENSION_ID]["value_id"], "high_contrast")
            self.assertEqual(first_base[NOISE_LEVEL_DIMENSION_ID]["value_id"], "low_noise")
            self.assertEqual(last_base[MOTION_DIRECTION_DIMENSION_ID]["value_id"], "preferred")
            self.assertEqual(last_base[MOTION_SPEED_DIMENSION_ID]["value_id"], "slow")
            self.assertEqual(last_base[CONTRAST_LEVEL_DIMENSION_ID]["value_id"], "low_contrast")
            self.assertEqual(last_base[NOISE_LEVEL_DIMENSION_ID]["value_id"], "high_noise")

            shuffle_seeded = next(
                item
                for item in seeded_ablation_cells
                if any(
                    reference["ablation_family_id"] == "shuffle_morphology"
                    for reference in item["ablation_references"]
                )
            )
            self.assertIsNotNone(
                shuffle_seeded["ablation_references"][0]["perturbation_seed"]
            )
            self.assertNotEqual(
                shuffle_seeded["ablation_references"][0]["perturbation_seed"],
                shuffle_seeded["simulation_seed"],
            )
            self.assertTrue(
                shuffle_seeded["suite_cell_id"].startswith(
                    shuffle_seeded["parent_cell_id"]
                )
            )

            self.assertEqual(
                first_plan["comparison_pairings"]["experiment_arm_pair_catalog"],
                first_plan["base_readout_analysis_plan"]["arm_pair_catalog"],
            )
            suite_pairings = first_plan["comparison_pairings"]["suite_cell_pairings"]
            self.assertEqual(
                len([item for item in suite_pairings if item["pairing_kind"] == "seed_rollup"]),
                8,
            )
            self.assertEqual(
                len(
                    [item for item in suite_pairings if item["pairing_kind"] == "ablation_vs_base"]
                ),
                12,
            )
            self.assertEqual(
                len(
                    [
                        item
                        for item in suite_pairings
                        if item["pairing_kind"] == "seed_matched_ablation_vs_base"
                    ]
                ),
                36,
            )

            seed_target = next(
                item
                for item in seed_cells[0]["stage_targets"]
                if item["stage_id"] == "simulation"
            )
            self.assertTrue(
                seed_target["metadata_path"].startswith(
                    str((tmp_dir / "out" / "suite_manifest_override").resolve())
                )
            )
            analysis_target = next(
                item
                for item in base_cells[0]["stage_targets"]
                if item["stage_id"] == "analysis"
            )
            self.assertTrue(analysis_target["metadata_path"].endswith("experiment_analysis_bundle.json"))
            self.assertFalse(
                any(item["stage_id"] == "dashboard" for item in base_cells[0]["stage_targets"])
            )

    def test_embedded_suite_extension_uses_config_defaults_when_suite_overrides_are_absent(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_output_root = tmp_dir / "out" / "embedded_suite_root"
            config_path = _write_simulation_fixture(
                tmp_dir,
                experiment_suite_config={
                    "version": EXPERIMENT_SUITE_CONFIG_VERSION,
                    "enabled_stage_ids": ["simulation", "analysis", "dashboard"],
                    "output_root": str(config_output_root),
                    "seed_policy": {
                        "reuse_scope": "shared_within_base_condition",
                        "lineage_seed_stride": 500,
                    },
                },
            )
            base_manifest_path = _write_manifest_fixture(tmp_dir)
            _record_fixture_stimulus_bundle(
                manifest_path=base_manifest_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            manifest_path = _write_embedded_suite_manifest_fixture(
                tmp_dir=tmp_dir,
                suite_block=_suite_block_without_seed_policy(
                    _base_suite_block(
                        output_root=None,
                        enabled_stage_ids=None,
                    )
                ),
            )

            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            self.assertEqual(plan["suite_source"]["source_kind"], "experiment_manifest")
            self.assertEqual(
                plan["output_roots"]["suite_root"],
                str(config_output_root.resolve()),
            )
            self.assertEqual(
                [item["stage_id"] for item in plan["stage_targets"]],
                ["simulation", "analysis", "dashboard"],
            )
            self.assertEqual(
                plan["seed_policy"]["reuse_scope"],
                "shared_within_base_condition",
            )
            self.assertEqual(
                plan["seed_policy"]["lineage_seed_stride"],
                500,
            )
            self.assertEqual(
                len(
                    [
                        item
                        for item in plan["upstream_references"]
                        if item["artifact_role_id"] == "suite_manifest_input"
                    ]
                ),
                1,
            )
            self.assertEqual(
                [
                    item["path"]
                    for item in plan["upstream_references"]
                    if item["artifact_role_id"] == "suite_manifest_input"
                ][0],
                str(manifest_path.resolve()),
            )

    def test_active_subset_prerequisite_uses_selection_contract_for_mixed_case_subset_names(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            subset_name = "Motion Minimal! Beta"
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"subset_name": subset_name},
            )
            config_path = _write_simulation_fixture(
                tmp_dir,
                subset_name=subset_name,
                experiment_suite_config={
                    "version": EXPERIMENT_SUITE_CONFIG_VERSION,
                    "enabled_stage_ids": ["simulation"],
                    "output_root": str(tmp_dir / "out" / "suite_root"),
                },
            )
            _record_fixture_stimulus_bundle(
                manifest_path=manifest_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            suite_block = _base_suite_block(output_root=tmp_dir / "out" / "suite_root")
            suite_block["dimensions"]["fixed"] = [
                item
                for item in suite_block["dimensions"]["fixed"]
                if item["dimension_id"] != ACTIVE_SUBSET_DIMENSION_ID
            ]
            suite_block["dimensions"]["fixed"].append(
                {
                    "dimension_id": ACTIVE_SUBSET_DIMENSION_ID,
                    "value_id": subset_name,
                    "value_label": "Mixed Case Subset",
                    "manifest_overrides": {"subset_name": subset_name},
                    "parameter_snapshot": {"subset_name": subset_name},
                }
            )
            suite_manifest_path = _write_suite_manifest_fixture(
                tmp_dir=tmp_dir,
                manifest_path=manifest_path,
                suite_block=suite_block,
            )

            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            expected_subset_paths = build_subset_artifact_paths(
                tmp_dir / "out" / "subsets",
                subset_name,
            )
            self.assertEqual(
                plan["base_simulation_plan"]["arm_plans"][0]["selection"][
                    "subset_manifest_reference"
                ]["subset_manifest_path"],
                str(expected_subset_paths.manifest_json.resolve()),
            )

    def test_suite_planner_fails_clearly_for_unsupported_suite_requests(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with self.subTest("unknown_dimension_id"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(tmp_dir)
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                suite_block = _base_suite_block()
                suite_block["dimensions"]["fixed"].append(
                    {
                        "dimension_id": "unsupported_dimension",
                        "value_id": "bad",
                        "value_label": "Bad",
                    }
                )
                suite_manifest_path = _write_suite_manifest_fixture(
                    tmp_dir=tmp_dir,
                    manifest_path=manifest_path,
                    suite_block=suite_block,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_experiment_suite_plan(
                        config_path=config_path,
                        suite_manifest_path=suite_manifest_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn("unknown dimension id", str(ctx.exception))

        with self.subTest("linked_axis_length_mismatch"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(tmp_dir)
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                suite_block = _base_suite_block()
                suite_block["dimensions"]["sweep_axes"][1]["dimensions"][1]["values"] = [
                    suite_block["dimensions"]["sweep_axes"][1]["dimensions"][1]["values"][0]
                ]
                suite_manifest_path = _write_suite_manifest_fixture(
                    tmp_dir=tmp_dir,
                    manifest_path=manifest_path,
                    suite_block=suite_block,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_experiment_suite_plan(
                        config_path=config_path,
                        suite_manifest_path=suite_manifest_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn("uses linked expansion but dimension value counts differ", str(ctx.exception))

        with self.subTest("unsupported_ablation_variant"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(tmp_dir)
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                suite_block = _base_suite_block()
                suite_block["ablations"][0]["variant_id"] = "unsupported_variant"
                suite_manifest_path = _write_suite_manifest_fixture(
                    tmp_dir=tmp_dir,
                    manifest_path=manifest_path,
                    suite_block=suite_block,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_experiment_suite_plan(
                        config_path=config_path,
                        suite_manifest_path=suite_manifest_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn("is not supported for ablation_family_id", str(ctx.exception))

        with self.subTest("contradictory_perturbation_seed_policy"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(tmp_dir)
                config_path = _write_simulation_fixture(
                    tmp_dir,
                    experiment_suite_config={
                        "version": EXPERIMENT_SUITE_CONFIG_VERSION,
                        "seed_policy": {
                            "perturbation_seed_mode": "none",
                        },
                    },
                )
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                suite_manifest_path = _write_suite_manifest_fixture(
                    tmp_dir=tmp_dir,
                    manifest_path=manifest_path,
                    suite_block=_suite_block_without_seed_policy(_base_suite_block()),
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_experiment_suite_plan(
                        config_path=config_path,
                        suite_manifest_path=suite_manifest_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn("requires separate perturbation seeds", str(ctx.exception))

        with self.subTest("missing_subset_prerequisite"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(tmp_dir)
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                suite_block = _base_suite_block()
                suite_block["dimensions"]["fixed"] = [
                    item
                    for item in suite_block["dimensions"]["fixed"]
                    if item["dimension_id"] != ACTIVE_SUBSET_DIMENSION_ID
                ]
                suite_block["dimensions"]["fixed"].append(
                    {
                        "dimension_id": ACTIVE_SUBSET_DIMENSION_ID,
                        "value_id": "missing_subset",
                        "value_label": "Missing Subset",
                        "manifest_overrides": {"subset_name": "missing_subset"},
                        "parameter_snapshot": {"subset_name": "missing_subset"},
                    }
                )
                suite_manifest_path = _write_suite_manifest_fixture(
                    tmp_dir=tmp_dir,
                    manifest_path=manifest_path,
                    suite_block=suite_block,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_experiment_suite_plan(
                        config_path=config_path,
                        suite_manifest_path=suite_manifest_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn("requires a local subset manifest", str(ctx.exception))


def _write_suite_manifest_fixture(
    *,
    tmp_dir: Path,
    manifest_path: Path,
    suite_block: dict[str, object],
) -> Path:
    suite_manifest_payload = {
        "format": EXPERIMENT_SUITE_MANIFEST_FORMAT,
        "experiment_manifest": {
            "path": str(manifest_path),
        },
        **copy.deepcopy(suite_block),
    }
    suite_manifest_path = tmp_dir / "suite_manifest.yaml"
    suite_manifest_path.write_text(
        yaml.safe_dump(suite_manifest_payload, sort_keys=False),
        encoding="utf-8",
    )
    return suite_manifest_path


def _write_embedded_suite_manifest_fixture(
    *,
    tmp_dir: Path,
    suite_block: dict[str, object],
) -> Path:
    manifest_path = _write_manifest_fixture(
        tmp_dir,
        manifest_overrides={"suite": copy.deepcopy(suite_block)},
    )
    embedded_manifest_path = tmp_dir / "embedded_suite_manifest.yaml"
    embedded_manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return embedded_manifest_path


def _suite_block_without_seed_policy(block: dict[str, object]) -> dict[str, object]:
    cloned = copy.deepcopy(block)
    cloned.pop("seed_policy", None)
    return cloned


def _base_suite_block(
    *,
    output_root: Path | None = None,
    enabled_stage_ids: list[str] | None = None,
) -> dict[str, object]:
    block: dict[str, object] = {
        "suite_id": "m15_motion_suite",
        "suite_label": "Milestone 15 Motion Suite",
        "description": "Representative fixture suite for Milestone 15 planning coverage.",
        "dimensions": {
            "fixed": [
                {
                    "dimension_id": "scene_type",
                    "value_id": "moving_edge",
                    "value_label": "Moving Edge",
                    "parameter_snapshot": {
                        "stimulus_family": "moving_edge",
                        "stimulus_name": "simple_moving_edge",
                    },
                },
                {
                    "dimension_id": "active_subset",
                    "value_id": "motion_minimal",
                    "value_label": "Motion Minimal",
                    "manifest_overrides": {"subset_name": "motion_minimal"},
                    "parameter_snapshot": {"subset_name": "motion_minimal"},
                },
                {
                    "dimension_id": "wave_kernel",
                    "value_id": "motion_patch_reference",
                    "value_label": "Motion Patch Reference",
                    "config_overrides": {
                        "simulation": {
                            "surface_wave": {
                                "parameter_preset": "motion_patch_reference"
                            }
                        }
                    },
                    "parameter_snapshot": {"parameter_preset": "motion_patch_reference"},
                },
                {
                    "dimension_id": "coupling_mode",
                    "value_id": "distributed_patch_cloud",
                    "value_label": "Distributed Patch Cloud",
                    "config_overrides": {
                        "meshing": {
                            "coupling_assembly": {
                                "topology_family": "distributed_patch_cloud"
                            }
                        }
                    },
                    "parameter_snapshot": {"topology_family": "distributed_patch_cloud"},
                },
                {
                    "dimension_id": "mesh_resolution",
                    "value_id": "fine",
                    "value_label": "Fine",
                    "parameter_snapshot": {"resolution": "fine"},
                },
                {
                    "dimension_id": "solver_settings",
                    "value_id": "dt_10_ms",
                    "value_label": "dt 10 ms",
                    "config_overrides": {
                        "simulation": {
                            "timebase": {
                                "dt_ms": 10.0,
                                "duration_ms": 500.0,
                            }
                        }
                    },
                    "parameter_snapshot": {
                        "dt_ms": 10.0,
                        "duration_ms": 500.0,
                    },
                },
                {
                    "dimension_id": "fidelity_class",
                    "value_id": "surface_only",
                    "value_label": "Surface Only",
                    "parameter_snapshot": {"fidelity_class": "surface_only"},
                },
            ],
            "sweep_axes": [
                {
                    "axis_id": "motion_axes",
                    "expansion_mode": "cross_product",
                    "dimensions": [
                        {
                            "dimension_id": "motion_direction",
                            "default_value_id": "preferred",
                            "values": [
                                {
                                    "value_id": "preferred",
                                    "value_label": "Preferred",
                                    "manifest_overrides": {
                                        "stimulus": {
                                            "stimulus_overrides": {"direction_deg": 0.0}
                                        }
                                    },
                                    "parameter_snapshot": {"direction_deg": 0.0},
                                },
                                {
                                    "value_id": "null",
                                    "value_label": "Null",
                                    "manifest_overrides": {
                                        "stimulus": {
                                            "stimulus_overrides": {"direction_deg": 180.0}
                                        }
                                    },
                                    "parameter_snapshot": {"direction_deg": 180.0},
                                },
                            ],
                        },
                        {
                            "dimension_id": "motion_speed",
                            "default_value_id": "fast",
                            "values": [
                                {
                                    "value_id": "fast",
                                    "value_label": "Fast",
                                    "manifest_overrides": {
                                        "stimulus": {
                                            "stimulus_overrides": {"velocity_deg_per_s": 45.0}
                                        }
                                    },
                                    "parameter_snapshot": {"velocity_deg_per_s": 45.0},
                                },
                                {
                                    "value_id": "slow",
                                    "value_label": "Slow",
                                    "manifest_overrides": {
                                        "stimulus": {
                                            "stimulus_overrides": {"velocity_deg_per_s": 20.0}
                                        }
                                    },
                                    "parameter_snapshot": {"velocity_deg_per_s": 20.0},
                                },
                            ],
                        },
                    ],
                },
                {
                    "axis_id": "signal_linked",
                    "expansion_mode": "linked",
                    "dimensions": [
                        {
                            "dimension_id": "contrast_level",
                            "default_value_id": "high_contrast",
                            "values": [
                                {
                                    "value_id": "high_contrast",
                                    "value_label": "High Contrast",
                                    "manifest_overrides": {
                                        "stimulus": {
                                            "stimulus_overrides": {"contrast": 0.8}
                                        }
                                    },
                                    "parameter_snapshot": {"contrast": 0.8},
                                },
                                {
                                    "value_id": "low_contrast",
                                    "value_label": "Low Contrast",
                                    "manifest_overrides": {
                                        "stimulus": {
                                            "stimulus_overrides": {"contrast": 0.4}
                                        }
                                    },
                                    "parameter_snapshot": {"contrast": 0.4},
                                },
                            ],
                        },
                        {
                            "dimension_id": "noise_level",
                            "default_value_id": "low_noise",
                            "values": [
                                {
                                    "value_id": "low_noise",
                                    "value_label": "Low Noise",
                                    "parameter_snapshot": {"noise_level": 0.0},
                                },
                                {
                                    "value_id": "high_noise",
                                    "value_label": "High Noise",
                                    "parameter_snapshot": {"noise_level": 0.15},
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        "seed_policy": {
            "simulation_seed_source": "manifest_seed_sweep",
            "reuse_scope": "shared_within_base_condition",
            "lineage_seed_stride": 1000,
            "perturbation_seed_mode": "derived_offset",
            "perturbation_seed_offset": 90000,
        },
        "ablations": [
            {
                "ablation_family_id": "no_waves",
                "variant_id": "disabled",
                "display_name": "No Waves",
                "parameter_snapshot": {"mode": "disable_surface_wave"},
            },
            {
                "ablation_family_id": "shuffle_morphology",
                "variant_id": "shuffled",
                "display_name": "Shuffle Morphology",
                "dimension_filters": {"motion_direction": ["preferred"]},
                "parameter_snapshot": {"shuffle_kind": "root_correspondence"},
            },
        ],
    }
    if output_root is not None:
        block["output_root"] = str(output_root)
    if enabled_stage_ids is not None:
        block["enabled_stage_ids"] = list(enabled_stage_ids)
    return block
