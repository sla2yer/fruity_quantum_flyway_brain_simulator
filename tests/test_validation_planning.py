from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.experiment_analysis_contract import (
    build_experiment_analysis_bundle_metadata,
    write_experiment_analysis_bundle_metadata,
)
from flywire_wave.experiment_comparison_analysis import discover_experiment_bundle_set
from flywire_wave.simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from flywire_wave.simulator_result_contract import (
    build_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from flywire_wave.stimulus_contract import (
    build_stimulus_bundle_metadata,
    load_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from flywire_wave.validation_contract import (
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
)
from flywire_wave.validation_planning import (
    GEOMETRY_VARIANTS_SUITE_ID,
    NOISE_ROBUSTNESS_SUITE_ID,
    SIGN_DELAY_PERTURBATIONS_SUITE_ID,
    TIMESTEP_SWEEPS_SUITE_ID,
    normalize_validation_config,
    resolve_manifest_validation_plan,
    resolve_validation_plan,
)

try:
    from simulation_planning_test_support import (
        _record_fixture_stimulus_bundle,
        _write_simulation_fixture,
    )
except ModuleNotFoundError:
    from tests.simulation_planning_test_support import (
        _record_fixture_stimulus_bundle,
        _write_simulation_fixture,
    )


class ValidationPlanningTest(unittest.TestCase):
    def test_validation_config_normalization_is_deterministic(self) -> None:
        raw_a = {
            "active_layer_ids": [
                "task_sanity",
                "numerical_sanity",
                "circuit_sanity",
            ],
            "criteria_profiles": {
                "validator_overrides": {
                    "surface_wave_stability_envelope": "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1",
                    "task_decoder_robustness": "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1",
                },
                "validator_family_overrides": {
                    "circuit_response": "validation_criteria.circuit_response.default_local_review.v1",
                },
            },
            "perturbation_suites": {
                "noise_robustness": {
                    "seed_values": [23, 11, 17],
                    "noise_levels": [0.1, 0.0],
                },
                "geometry_variants": {
                    "variant_ids": ["shuffled", "intact"],
                },
                "timestep_sweeps": {
                    "sweep_spec_paths": ["config/surface_wave_sweep.verification.yaml"],
                    "use_manifest_seed_sweep": True,
                },
            },
        }
        raw_b = {
            "active_layer_ids": [
                "circuit_sanity",
                "task_sanity",
                "numerical_sanity",
            ],
            "criteria_profiles": {
                "validator_family_overrides": {
                    "Circuit Response": "validation_criteria.circuit_response.default_local_review.v1",
                },
                "validator_overrides": {
                    "Task Decoder Robustness": "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1",
                    "Surface Wave Stability Envelope": "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1",
                },
            },
            "perturbation_suites": {
                "timestep_sweeps": {
                    "use_manifest_seed_sweep": True,
                    "sweep_spec_paths": [
                        str(ROOT / "config" / "surface_wave_sweep.verification.yaml")
                    ],
                },
                "geometry_variants": {
                    "variant_ids": ["intact", "shuffled"],
                },
                "noise_robustness": {
                    "noise_levels": [0.0, 0.1],
                    "seed_values": [17, 11, 23],
                },
            },
        }

        normalized_a = normalize_validation_config(raw_a, project_root=ROOT)
        normalized_b = normalize_validation_config(raw_b, project_root=ROOT)

        self.assertEqual(normalized_a, normalized_b)
        self.assertEqual(
            normalized_a["active_layer_ids"],
            ["circuit_sanity", "numerical_sanity", "task_sanity"],
        )
        self.assertEqual(
            normalized_a["perturbation_suites"][GEOMETRY_VARIANTS_SUITE_ID][
                "variant_ids"
            ],
            ["intact", "shuffled"],
        )
        self.assertEqual(
            normalized_a["perturbation_suites"][NOISE_ROBUSTNESS_SUITE_ID][
                "seed_values"
            ],
            [11, 17, 23],
        )
        self.assertEqual(
            normalized_a["perturbation_suites"][TIMESTEP_SWEEPS_SUITE_ID][
                "sweep_spec_paths"
            ],
            [str((ROOT / "config" / "surface_wave_sweep.verification.yaml").resolve())],
        )

    def test_manifest_validation_plan_resolution_is_deterministic_and_reuses_upstream_inputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_validation_fixture(
                tmp_dir,
                validation_config={
                    "active_layer_ids": [
                        "task_sanity",
                        "circuit_sanity",
                        "morphology_sanity",
                        "numerical_sanity",
                    ],
                    "criteria_profiles": {
                        "layer_overrides": {
                            "task_sanity": "validation_criteria.task_effect_reproducibility.default_local_review.v1",
                        },
                        "validator_family_overrides": {
                            "circuit_response": "validation_criteria.circuit_response.default_local_review.v1",
                        },
                        "validator_overrides": {
                            "surface_wave_stability_envelope": "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1",
                        },
                    },
                    "perturbation_suites": {
                        "timestep_sweeps": {
                            "enabled": True,
                            "sweep_spec_paths": [
                                "config/surface_wave_sweep.verification.yaml",
                            ],
                            "use_manifest_seed_sweep": True,
                        },
                        "geometry_variants": {
                            "enabled": True,
                            "variant_ids": ["shuffled", "intact"],
                        },
                        "sign_delay_perturbations": {
                            "enabled": True,
                            "variant_ids": ["sign_inversion_probe", "zero_delay_probe"],
                        },
                        "noise_robustness": {
                            "enabled": True,
                            "seed_values": [23, 11, 17],
                            "noise_levels": [0.1, 0.0],
                        },
                    },
                },
                write_analysis_bundle=True,
            )

            first_plan = resolve_manifest_validation_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            second_plan = resolve_validation_plan(
                config_path=fixture["config_path"],
                simulation_plan=fixture["simulation_plan"],
                analysis_plan=fixture["analysis_plan"],
                bundle_set=fixture["bundle_set"],
                analysis_bundle_metadata_path=fixture["analysis_bundle_path"],
            )

            self.assertEqual(first_plan, second_plan)
            self.assertEqual(
                first_plan["active_layer_ids"],
                [
                    "numerical_sanity",
                    "morphology_sanity",
                    "circuit_sanity",
                    "task_sanity",
                ],
            )
            self.assertEqual(
                [suite["suite_id"] for suite in first_plan["perturbation_suites"]],
                [
                    TIMESTEP_SWEEPS_SUITE_ID,
                    GEOMETRY_VARIANTS_SUITE_ID,
                    SIGN_DELAY_PERTURBATIONS_SUITE_ID,
                    NOISE_ROBUSTNESS_SUITE_ID,
                ],
            )
            assignments = {
                item["validator_id"]: item for item in first_plan["criteria_profile_assignments"]
            }
            self.assertEqual(
                assignments[SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID][
                    "criteria_profile_source"
                ],
                "validator_override",
            )
            self.assertEqual(
                assignments[MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID][
                    "criteria_profile_source"
                ],
                "validator_family_override",
            )
            self.assertEqual(
                assignments[TASK_DECODER_ROBUSTNESS_VALIDATOR_ID][
                    "criteria_profile_source"
                ],
                "layer_override",
            )
            self.assertEqual(
                assignments[GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID][
                    "criteria_profile_source"
                ],
                "validator_contract_default",
            )
            geometry_suite = next(
                suite
                for suite in first_plan["perturbation_suites"]
                if suite["suite_id"] == GEOMETRY_VARIANTS_SUITE_ID
            )
            self.assertEqual(
                [variant["variant_id"] for variant in geometry_suite["variants"]],
                ["intact", "shuffled"],
            )
            timestep_suite = next(
                suite
                for suite in first_plan["perturbation_suites"]
                if suite["suite_id"] == TIMESTEP_SWEEPS_SUITE_ID
            )
            self.assertEqual(
                [variant["resolved_seed_values"] for variant in timestep_suite["variants"]],
                [[11, 17, 23], [11, 17, 23]],
            )
            self.assertTrue(
                first_plan["output_locations"]["bundle_directory"].endswith(
                    first_plan["validation_bundle"]["validation_spec_hash"]
                )
            )
            self.assertEqual(
                Path(
                    first_plan["target_artifact_references"]["experiment_analysis_bundle"][
                        "metadata_path"
                    ]
                ).resolve(),
                fixture["analysis_bundle_path"].resolve(),
            )
            self.assertEqual(
                first_plan["target_artifact_references"]["simulator_result_bundles"][0][
                    "arm_id"
                ],
                "baseline_p0_intact",
            )

    def test_missing_analysis_bundle_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_validation_fixture(
                tmp_dir,
                validation_config=None,
                write_analysis_bundle=False,
            )
            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_validation_plan(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )
            self.assertIn(
                "requires a local experiment_analysis_bundle",
                str(ctx.exception),
            )

    def test_unsupported_geometry_variant_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_validation_fixture(
                tmp_dir,
                validation_config={
                    "perturbation_suites": {
                        "geometry_variants": {
                            "variant_ids": ["unsupported_geometry_variant"],
                        },
                    },
                },
                write_analysis_bundle=True,
            )
            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_validation_plan(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )
            self.assertIn("unsupported geometry variants", str(ctx.exception))

    def test_incomplete_seed_coverage_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_validation_fixture(
                tmp_dir,
                validation_config=None,
                write_analysis_bundle=False,
                skip_bundle_keys={("surface_wave_intact", 23)},
                discover_bundle_set=False,
            )
            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_validation_plan(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )
            self.assertIn("missing required condition coverage", str(ctx.exception))

    def test_unknown_criteria_profile_identifier_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_validation_fixture(
                tmp_dir,
                validation_config={
                    "active_validator_ids": ["operator_bundle_gate_alignment"],
                    "criteria_profiles": {
                        "validator_overrides": {
                            "operator_bundle_gate_alignment": "validation_criteria.unknown_profile.v1",
                        },
                    },
                },
                write_simulator_bundles=False,
                write_analysis_bundle=False,
            )
            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_validation_plan(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )
            self.assertIn("unknown criteria_profile identifiers", str(ctx.exception))


def _prepare_validation_fixture(
    tmp_dir: Path,
    *,
    validation_config: dict[str, object] | None,
    write_simulator_bundles: bool = True,
    write_analysis_bundle: bool,
    skip_bundle_keys: set[tuple[str, int]] | None = None,
    discover_bundle_set: bool = True,
) -> dict[str, object]:
    manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
    schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
    design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
    config_path = _write_simulation_fixture(tmp_dir)
    _write_validation_config(config_path, validation_config)
    _record_fixture_stimulus_bundle(
        manifest_path=manifest_path,
        processed_stimulus_dir=tmp_dir / "out" / "stimuli",
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    analysis_plan = resolve_manifest_readout_analysis_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    if write_simulator_bundles:
        _write_simulator_bundle_metadata(
            simulation_plan,
            analysis_plan=analysis_plan,
            skip_bundle_keys=skip_bundle_keys or set(),
        )
    bundle_set = None
    analysis_bundle_path = None
    if write_simulator_bundles and discover_bundle_set:
        bundle_set = discover_experiment_bundle_set(
            simulation_plan=simulation_plan,
            analysis_plan=analysis_plan,
        )
        if write_analysis_bundle:
            metadata = build_experiment_analysis_bundle_metadata(
                analysis_plan=analysis_plan,
                bundle_set=bundle_set,
            )
            analysis_bundle_path = write_experiment_analysis_bundle_metadata(metadata)
    return {
        "manifest_path": manifest_path,
        "config_path": config_path,
        "schema_path": schema_path,
        "design_lock_path": design_lock_path,
        "simulation_plan": simulation_plan,
        "analysis_plan": analysis_plan,
        "bundle_set": bundle_set,
        "analysis_bundle_path": analysis_bundle_path,
    }


def _write_validation_config(
    config_path: Path,
    validation_config: dict[str, object] | None,
) -> None:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if validation_config is not None:
        payload["validation"] = validation_config
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _write_simulator_bundle_metadata(
    simulation_plan: dict[str, object],
    *,
    analysis_plan: dict[str, object],
    skip_bundle_keys: set[tuple[str, int]],
) -> None:
    condition_variants = _condition_variants(analysis_plan)
    for run_plan in discover_simulation_run_plans(
        simulation_plan,
        use_manifest_seed_sweep=True,
    ):
        arm_id = str(run_plan["arm_reference"]["arm_id"])
        seed = int(run_plan["determinism"]["seed"])
        if (arm_id, seed) in skip_bundle_keys:
            continue
        selected_assets = list(run_plan["selected_assets"])
        input_asset = next(
            asset for asset in selected_assets if str(asset["asset_role"]) == "input_bundle"
        )
        base_stimulus_metadata = load_stimulus_bundle_metadata(input_asset["path"])
        for condition_variant in condition_variants:
            stimulus_metadata = build_stimulus_bundle_metadata(
                stimulus_family=base_stimulus_metadata["stimulus_family"],
                stimulus_name=base_stimulus_metadata["stimulus_name"],
                processed_stimulus_dir=Path(
                    base_stimulus_metadata["assets"]["metadata_json"]["path"]
                ).resolve().parents[4],
                representation_family=base_stimulus_metadata["representation_family"],
                parameter_snapshot={
                    **base_stimulus_metadata["parameter_snapshot"],
                    **condition_variant["parameter_overrides"],
                },
                seed=base_stimulus_metadata["determinism"]["seed"],
                rng_family=base_stimulus_metadata["determinism"]["rng_family"],
                temporal_sampling=base_stimulus_metadata["temporal_sampling"],
                spatial_frame=base_stimulus_metadata["spatial_frame"],
                luminance_convention=base_stimulus_metadata["luminance_convention"],
            )
            stimulus_metadata_path = write_stimulus_bundle_metadata(
                stimulus_metadata,
                write_aliases=False,
            )
            mutated_assets = []
            for asset in selected_assets:
                record = dict(asset)
                if str(record["asset_role"]) == "input_bundle":
                    record["bundle_id"] = str(stimulus_metadata["bundle_id"])
                    record["path"] = str(stimulus_metadata_path.resolve())
                mutated_assets.append(record)
            bundle_metadata = build_simulator_result_bundle_metadata(
                manifest_reference=run_plan["manifest_reference"],
                arm_reference=run_plan["arm_reference"],
                determinism=run_plan["determinism"],
                timebase=run_plan["runtime"]["timebase"],
                selected_assets=mutated_assets,
                readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
                processed_simulator_results_dir=run_plan["runtime"][
                    "processed_simulator_results_dir"
                ],
            )
            write_simulator_result_bundle_metadata(bundle_metadata)


def _condition_variants(analysis_plan: dict[str, object]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in analysis_plan["condition_catalog"]:
        grouped.setdefault(str(item["parameter_name"]), []).append(dict(item))
    if not grouped:
        return [{"condition_ids": [], "parameter_overrides": {}}]
    variants: list[dict[str, object]] = [
        {"condition_ids": [], "parameter_overrides": {}}
    ]
    for parameter_name in sorted(grouped):
        next_variants: list[dict[str, object]] = []
        for partial in variants:
            for item in grouped[parameter_name]:
                next_variants.append(
                    {
                        "condition_ids": sorted(
                            [*partial["condition_ids"], str(item["condition_id"])]
                        ),
                        "parameter_overrides": {
                            **partial["parameter_overrides"],
                            parameter_name: item["value"],
                        },
                    }
                )
        variants = next_variants
    variants.sort(key=lambda item: tuple(item["condition_ids"]))
    return variants


if __name__ == "__main__":
    unittest.main()
