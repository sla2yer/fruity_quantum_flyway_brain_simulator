from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.dashboard_session_contract import DASHBOARD_SESSION_CONTRACT_VERSION
from flywire_wave.experiment_analysis_contract import (
    EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
)
from flywire_wave.experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    ACTIVE_SUBSET_DIMENSION_ID,
    COMPARISON_PLOT_ROLE_ID,
    COMPARISON_PLOT_SOURCE_KIND,
    CONTRAST_LEVEL_DIMENSION_ID,
    DASHBOARD_SESSION_ROLE_ID,
    DASHBOARD_SESSION_SOURCE_KIND,
    EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
    EXPERIMENT_ANALYSIS_SOURCE_KIND,
    EXPERIMENT_MANIFEST_INPUT_ROLE_ID,
    EXPERIMENT_MANIFEST_SOURCE_KIND,
    EXPERIMENT_SUITE_CONTRACT_VERSION,
    EXPERIMENT_SUITE_DESIGN_NOTE,
    FIDELITY_CLASS_DIMENSION_ID,
    MOTION_DIRECTION_DIMENSION_ID,
    MOTION_SPEED_DIMENSION_ID,
    MESH_RESOLUTION_DIMENSION_ID,
    NOISE_LEVEL_DIMENSION_ID,
    NO_WAVES_ABLATION_FAMILY_ID,
    REVIEW_ARTIFACT_ROLE_ID,
    REVIEW_ARTIFACT_SOURCE_KIND,
    SCENE_TYPE_DIMENSION_ID,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
    SIMULATION_PLAN_ROLE_ID,
    SIMULATION_PLAN_SOURCE_KIND,
    SIMULATOR_RESULT_BUNDLE_ROLE_ID,
    SIMULATOR_RESULT_SOURCE_KIND,
    SOLVER_SETTINGS_DIMENSION_ID,
    SUMMARY_TABLE_ROLE_ID,
    SUMMARY_TABLE_SOURCE_KIND,
    SUPPORTED_ABLATION_FAMILY_IDS,
    SUPPORTED_DIMENSION_IDS,
    SUITE_MANIFEST_INPUT_ROLE_ID,
    SUITE_MANIFEST_SOURCE_KIND,
    UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
    VALIDATION_BUNDLE_ROLE_ID,
    VALIDATION_BUNDLE_SOURCE_KIND,
    WAVE_KERNEL_DIMENSION_ID,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_SUCCEEDED,
    build_experiment_suite_ablation_reference,
    build_experiment_suite_artifact_reference,
    build_experiment_suite_cell_metadata,
    build_experiment_suite_contract_metadata,
    build_experiment_suite_dimension_assignment,
    build_experiment_suite_metadata,
    build_experiment_suite_work_item,
    discover_experiment_suite_ablation_families,
    discover_experiment_suite_artifact_references,
    discover_experiment_suite_artifact_roles,
    discover_experiment_suite_cells,
    discover_experiment_suite_dimensions,
    discover_experiment_suite_work_items,
    get_experiment_suite_ablation_family_definition,
    get_experiment_suite_dimension_definition,
    load_experiment_suite_contract_metadata,
    load_experiment_suite_metadata,
    write_experiment_suite_contract_metadata,
    write_experiment_suite_metadata,
)
from flywire_wave.simulation_planning import SIMULATION_PLAN_VERSION
from flywire_wave.simulator_result_contract import (
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
)
from flywire_wave.validation_contract import VALIDATION_LADDER_CONTRACT_VERSION


def _humanize_identifier(identifier: str) -> str:
    return identifier.replace("_", " ").title()


def _mutate_contract_fixture(
    metadata: dict[str, object],
    *,
    reverse: bool,
) -> dict[str, list[dict[str, object]]]:
    dimension_definitions: list[dict[str, object]] = []
    for entry in metadata["dimension_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["dimension_id"] = _humanize_identifier(str(mutated["dimension_id"]))
        mutated["dimension_group"] = _humanize_identifier(str(mutated["dimension_group"]))
        dimension_definitions.append(mutated)

    ablation_family_definitions: list[dict[str, object]] = []
    for entry in metadata["ablation_family_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["ablation_family_id"] = _humanize_identifier(
            str(mutated["ablation_family_id"])
        )
        ablation_family_definitions.append(mutated)

    lineage_definitions: list[dict[str, object]] = []
    for entry in metadata["lineage_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["lineage_kind"] = _humanize_identifier(str(mutated["lineage_kind"]))
        lineage_definitions.append(mutated)

    work_item_status_definitions: list[dict[str, object]] = []
    for entry in metadata["work_item_status_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["status_id"] = _humanize_identifier(str(mutated["status_id"]))
        work_item_status_definitions.append(mutated)

    artifact_role_definitions: list[dict[str, object]] = []
    for entry in metadata["artifact_role_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["artifact_role_id"] = _humanize_identifier(
            str(mutated["artifact_role_id"])
        )
        mutated["source_kind"] = _humanize_identifier(str(mutated["source_kind"]))
        mutated["artifact_scope"] = _humanize_identifier(str(mutated["artifact_scope"]))
        artifact_role_definitions.append(mutated)

    reproducibility_hook_definitions: list[dict[str, object]] = []
    for entry in metadata["reproducibility_hook_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["hook_id"] = _humanize_identifier(str(mutated["hook_id"]))
        reproducibility_hook_definitions.append(mutated)

    if reverse:
        dimension_definitions.reverse()
        ablation_family_definitions.reverse()
        lineage_definitions.reverse()
        work_item_status_definitions.reverse()
        artifact_role_definitions.reverse()
        reproducibility_hook_definitions.reverse()

    return {
        "dimension_definitions": dimension_definitions,
        "ablation_family_definitions": ablation_family_definitions,
        "lineage_definitions": lineage_definitions,
        "work_item_status_definitions": work_item_status_definitions,
        "artifact_role_definitions": artifact_role_definitions,
        "reproducibility_hook_definitions": reproducibility_hook_definitions,
    }


def _mutate_suite_fixture(
    suite_cells: list[dict[str, object]],
    work_items: list[dict[str, object]],
    upstream_references: list[dict[str, object]],
    artifact_references: list[dict[str, object]],
    *,
    reverse: bool,
) -> dict[str, list[dict[str, object]]]:
    mutated_cells: list[dict[str, object]] = []
    for entry in suite_cells:
        mutated = copy.deepcopy(entry)
        mutated["suite_cell_id"] = _humanize_identifier(str(mutated["suite_cell_id"]))
        mutated["lineage_kind"] = _humanize_identifier(str(mutated["lineage_kind"]))
        if mutated["parent_cell_id"] is not None:
            mutated["parent_cell_id"] = _humanize_identifier(
                str(mutated["parent_cell_id"])
            )
        if mutated["root_cell_id"] is not None:
            mutated["root_cell_id"] = _humanize_identifier(str(mutated["root_cell_id"]))
        for assignment in mutated["dimension_assignments"]:
            assignment["dimension_id"] = _humanize_identifier(
                str(assignment["dimension_id"])
            )
            assignment["value_id"] = _humanize_identifier(str(assignment["value_id"]))
        for ablation in mutated["ablation_references"]:
            ablation["ablation_family_id"] = _humanize_identifier(
                str(ablation["ablation_family_id"])
            )
            ablation["variant_id"] = _humanize_identifier(str(ablation["variant_id"]))
        mutated_cells.append(mutated)

    mutated_work_items: list[dict[str, object]] = []
    for entry in work_items:
        mutated = copy.deepcopy(entry)
        mutated["work_item_id"] = _humanize_identifier(str(mutated["work_item_id"]))
        mutated["suite_cell_id"] = _humanize_identifier(str(mutated["suite_cell_id"]))
        mutated["stage_id"] = _humanize_identifier(str(mutated["stage_id"]))
        mutated["status"] = _humanize_identifier(str(mutated["status"]))
        mutated["artifact_role_ids"] = [
            _humanize_identifier(str(item)) for item in mutated["artifact_role_ids"]
        ]
        mutated_work_items.append(mutated)

    mutated_upstream_references: list[dict[str, object]] = []
    for entry in upstream_references:
        mutated = copy.deepcopy(entry)
        mutated["artifact_role_id"] = _humanize_identifier(
            str(mutated["artifact_role_id"])
        )
        mutated["source_kind"] = _humanize_identifier(str(mutated["source_kind"]))
        if mutated["artifact_id"] is not None:
            mutated["artifact_id"] = _humanize_identifier(str(mutated["artifact_id"]))
        if mutated["artifact_scope"] is not None:
            mutated["artifact_scope"] = _humanize_identifier(
                str(mutated["artifact_scope"])
            )
        mutated_upstream_references.append(mutated)

    mutated_artifact_references: list[dict[str, object]] = []
    for entry in artifact_references:
        mutated = copy.deepcopy(entry)
        mutated["artifact_role_id"] = _humanize_identifier(
            str(mutated["artifact_role_id"])
        )
        mutated["source_kind"] = _humanize_identifier(str(mutated["source_kind"]))
        if mutated["artifact_id"] is not None:
            mutated["artifact_id"] = _humanize_identifier(str(mutated["artifact_id"]))
        if mutated["artifact_scope"] is not None:
            mutated["artifact_scope"] = _humanize_identifier(
                str(mutated["artifact_scope"])
            )
        if mutated["suite_cell_id"] is not None:
            mutated["suite_cell_id"] = _humanize_identifier(str(mutated["suite_cell_id"]))
        if mutated["work_item_id"] is not None:
            mutated["work_item_id"] = _humanize_identifier(str(mutated["work_item_id"]))
        mutated_artifact_references.append(mutated)

    if reverse:
        mutated_cells.reverse()
        mutated_work_items.reverse()
        mutated_upstream_references.reverse()
        mutated_artifact_references.reverse()

    return {
        "suite_cells": mutated_cells,
        "work_items": mutated_work_items,
        "upstream_references": mutated_upstream_references,
        "artifact_references": mutated_artifact_references,
    }


class ExperimentSuiteContractTest(unittest.TestCase):
    def test_default_contract_exposes_milestone15_taxonomy(self) -> None:
        metadata = build_experiment_suite_contract_metadata()

        self.assertEqual(metadata["contract_version"], EXPERIMENT_SUITE_CONTRACT_VERSION)
        self.assertEqual(metadata["design_note"], EXPERIMENT_SUITE_DESIGN_NOTE)
        self.assertEqual(
            [item["dimension_id"] for item in discover_experiment_suite_dimensions(metadata)],
            list(SUPPORTED_DIMENSION_IDS),
        )
        self.assertEqual(
            [
                item["ablation_family_id"]
                for item in discover_experiment_suite_ablation_families(
                    metadata,
                    required_only=True,
                )
            ],
            list(SUPPORTED_ABLATION_FAMILY_IDS),
        )
        self.assertEqual(
            get_experiment_suite_dimension_definition(
                "Motion Speed",
                record=metadata,
            )["dimension_id"],
            MOTION_SPEED_DIMENSION_ID,
        )
        self.assertEqual(
            get_experiment_suite_ablation_family_definition(
                "No Waves",
                record=metadata,
            )["ablation_family_id"],
            NO_WAVES_ABLATION_FAMILY_ID,
        )
        self.assertEqual(
            [
                item["artifact_role_id"]
                for item in discover_experiment_suite_artifact_roles(
                    metadata,
                    artifact_scope="Downstream Bundle",
                )
            ],
            [
                SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
                VALIDATION_BUNDLE_ROLE_ID,
                DASHBOARD_SESSION_ROLE_ID,
            ],
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            metadata_path = Path(tmp_dir_str) / "experiment_suite_contract.json"
            written_path = write_experiment_suite_contract_metadata(metadata, metadata_path)
            self.assertEqual(load_experiment_suite_contract_metadata(written_path), metadata)

    def test_fixture_contract_serializes_deterministically_and_discovers_taxonomy(self) -> None:
        default_metadata = build_experiment_suite_contract_metadata()
        fixture_a = _mutate_contract_fixture(default_metadata, reverse=False)
        fixture_b = _mutate_contract_fixture(default_metadata, reverse=True)

        metadata_a = build_experiment_suite_contract_metadata(**fixture_a)
        metadata_b = build_experiment_suite_contract_metadata(**fixture_b)

        self.assertEqual(metadata_a, metadata_b)
        self.assertEqual(
            [
                item["dimension_id"]
                for item in discover_experiment_suite_dimensions(metadata_a)
            ],
            list(SUPPORTED_DIMENSION_IDS),
        )
        self.assertEqual(
            [
                item["ablation_family_id"]
                for item in discover_experiment_suite_ablation_families(metadata_a)
            ],
            list(SUPPORTED_ABLATION_FAMILY_IDS),
        )

    def test_fixture_suite_metadata_serializes_deterministically_and_discovers_cells(self) -> None:
        contract_metadata = build_experiment_suite_contract_metadata()
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            temp_root = Path(tmp_dir_str)

            upstream_references = [
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Simulation Plan",
                    source_kind="Simulation Plan",
                    path=temp_root / "plans/motion_demo/simulation_plan.json",
                    contract_version=SIMULATION_PLAN_VERSION,
                    artifact_id="simulation_plan",
                    format="json_simulation_plan.v1",
                    artifact_scope="contract_metadata",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Experiment Manifest Input",
                    source_kind="Experiment Manifest",
                    path=temp_root / "manifests/motion_demo.yaml",
                    artifact_id="motion_demo_manifest",
                    format="yaml_experiment_manifest.v1",
                    artifact_scope="source_manifest",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Suite Manifest Input",
                    source_kind="Suite Manifest",
                    path=temp_root / "suite/manifests/m15_motion_suite.yaml",
                    artifact_id="m15_motion_suite",
                    format="yaml_experiment_suite_manifest.v1",
                    artifact_scope="source_manifest",
                ),
            ]

            base_dimensions = [
                build_experiment_suite_dimension_assignment(
                    dimension_id="Fidelity Class",
                    value_id="Mixed Surface Priority",
                    value_label="Mixed Surface Priority",
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Solver Settings",
                    value_id="dt_0_5_ms",
                    value_label="dt = 0.5 ms",
                    parameter_snapshot={"dt_ms": 0.5},
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Mesh Resolution",
                    value_id="Fine",
                    value_label="Fine Mesh",
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Coupling Mode",
                    value_id="full_coupling",
                    value_label="Full Coupling",
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Wave Kernel",
                    value_id="surface_wave_default",
                    value_label="Surface Wave Default",
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Active Subset",
                    value_id="t4_t5_fixture",
                    value_label="T4/T5 Fixture",
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Noise Level",
                    value_id="low_noise",
                    value_label="Low Noise",
                    parameter_snapshot={"noise_std": 0.05},
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Contrast Level",
                    value_id="high_contrast",
                    value_label="High Contrast",
                    parameter_snapshot={"contrast": 0.8},
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Motion Speed",
                    value_id="fast",
                    value_label="Fast",
                    parameter_snapshot={"speed_deg_s": 45.0},
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Motion Direction",
                    value_id="preferred",
                    value_label="Preferred",
                ),
                build_experiment_suite_dimension_assignment(
                    dimension_id="Scene Type",
                    value_id="moving_bar",
                    value_label="Moving Bar",
                ),
            ]

            suite_cells = [
                build_experiment_suite_cell_metadata(
                    suite_cell_id="Motion Demo No Waves Seed 17",
                    display_name="Motion Demo No Waves Seed 17",
                    lineage_kind="Seeded Ablation Variant",
                    parent_cell_id="Motion Demo Intact",
                    root_cell_id="Motion Demo Intact",
                    simulation_seed=17,
                    dimension_assignments=list(reversed(base_dimensions)),
                    ablation_references=[
                        build_experiment_suite_ablation_reference(
                            ablation_family_id="Shuffle Morphology",
                            variant_id="shuffled",
                            display_name="Shuffled Morphology",
                            perturbation_seed=9001,
                        ),
                        build_experiment_suite_ablation_reference(
                            ablation_family_id="No Waves",
                            variant_id="disabled",
                            display_name="Waves Disabled",
                        ),
                    ],
                ),
                build_experiment_suite_cell_metadata(
                    suite_cell_id="Motion Demo Intact",
                    display_name="Motion Demo Intact",
                    lineage_kind="Base Condition",
                    dimension_assignments=list(reversed(base_dimensions)),
                ),
            ]

            work_items = [
                build_experiment_suite_work_item(
                    work_item_id="Analyze Motion Demo No Waves Seed 17",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                    stage_id="Analysis",
                    status="Partial",
                    artifact_role_ids=[
                        "Comparison Plot",
                        "Experiment Analysis Bundle",
                        "Summary Table",
                    ],
                    status_detail="Analysis bundle is ready; reporting artifacts are still pending.",
                ),
                build_experiment_suite_work_item(
                    work_item_id="Simulate Motion Demo Intact",
                    suite_cell_id="Motion Demo Intact",
                    stage_id="Simulation",
                    status="Succeeded",
                    artifact_role_ids=["Simulator Result Bundle"],
                ),
            ]

            artifact_references = [
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Review Artifact",
                    source_kind="Review Artifact",
                    path=temp_root / "suite/review/m15_motion_suite_review.md",
                    format="md_suite_review.v1",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                    work_item_id="Analyze Motion Demo No Waves Seed 17",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Comparison Plot",
                    source_kind="Comparison Plot",
                    path=temp_root / "suite/plots/no_waves_vs_intact.png",
                    format="png_suite_comparison_plot.v1",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                    work_item_id="Analyze Motion Demo No Waves Seed 17",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Summary Table",
                    source_kind="Summary Table",
                    path=temp_root / "suite/tables/motion_summary.csv",
                    format="csv_suite_summary_table.v1",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                    work_item_id="Analyze Motion Demo No Waves Seed 17",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Dashboard Session",
                    source_kind="Dashboard Session",
                    path=temp_root / "dashboard/session/dashboard_session.json",
                    contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
                    bundle_id="dashboard_session.v1:motion_demo:" + ("4" * 64),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                    format="json_dashboard_session_metadata.v1",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Validation Bundle",
                    source_kind="Validation Bundle",
                    path=temp_root / "validation/validation_bundle.json",
                    contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                    bundle_id="validation_ladder.v1:motion_demo:" + ("3" * 64),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                    format="json_validation_bundle_metadata.v1",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Experiment Analysis Bundle",
                    source_kind="Experiment Analysis Bundle",
                    path=temp_root / "analysis/experiment_analysis_bundle.json",
                    contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
                    bundle_id="experiment_analysis_bundle.v1:motion_demo:" + ("2" * 64),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                    format="json_experiment_analysis_bundle_metadata.v1",
                    suite_cell_id="Motion Demo No Waves Seed 17",
                    work_item_id="Analyze Motion Demo No Waves Seed 17",
                ),
                build_experiment_suite_artifact_reference(
                    artifact_role_id="Simulator Result Bundle",
                    source_kind="Simulator Result Bundle",
                    path=temp_root / "bundles/intact/simulator_result_bundle.json",
                    contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
                    bundle_id=(
                        "simulator_result_bundle.v1:motion_demo:intact:" + ("1" * 64)
                    ),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                    format="json_simulator_result_bundle_metadata.v1",
                    suite_cell_id="Motion Demo Intact",
                    work_item_id="Simulate Motion Demo Intact",
                ),
            ]

            metadata_a = build_experiment_suite_metadata(
                suite_id="M15 Motion Suite",
                suite_label="Milestone 15 Motion Suite",
                upstream_references=upstream_references,
                suite_cells=suite_cells,
                work_items=work_items,
                artifact_references=artifact_references,
                contract_metadata=contract_metadata,
            )
            fixture_b = _mutate_suite_fixture(
                suite_cells=[copy.deepcopy(item) for item in reversed(suite_cells)],
                work_items=[copy.deepcopy(item) for item in reversed(work_items)],
                upstream_references=[
                    copy.deepcopy(item) for item in reversed(upstream_references)
                ],
                artifact_references=[
                    copy.deepcopy(item) for item in reversed(artifact_references)
                ],
                reverse=True,
            )
            metadata_b = build_experiment_suite_metadata(
                suite_id="M15 Motion Suite",
                suite_label="Milestone 15 Motion Suite",
                contract_metadata=contract_metadata,
                **fixture_b,
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(metadata_a["contract_version"], EXPERIMENT_SUITE_CONTRACT_VERSION)
            self.assertEqual(metadata_a["suite_id"], "m15_motion_suite")
            self.assertEqual(
                [item["dimension_id"] for item in metadata_a["suite_cells"][0]["dimension_assignments"]],
                list(SUPPORTED_DIMENSION_IDS),
            )
            self.assertEqual(
                [
                    item["ablation_family_id"]
                    for item in metadata_a["suite_cells"][1]["ablation_references"]
                ],
                [
                    NO_WAVES_ABLATION_FAMILY_ID,
                    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
                ],
            )
            self.assertEqual(
                [
                    item["suite_cell_id"]
                    for item in discover_experiment_suite_cells(
                        metadata_a,
                        ablation_family_id="Shuffle Morphology",
                        contract_metadata=contract_metadata,
                    )
                ],
                ["motion_demo_no_waves_seed_17"],
            )
            self.assertEqual(
                [
                    item["artifact_role_id"]
                    for item in discover_experiment_suite_artifact_references(
                        metadata_a,
                        contract_metadata=contract_metadata,
                        include_upstream=False,
                    )
                ],
                [
                    SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                    EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
                    VALIDATION_BUNDLE_ROLE_ID,
                    DASHBOARD_SESSION_ROLE_ID,
                    SUMMARY_TABLE_ROLE_ID,
                    COMPARISON_PLOT_ROLE_ID,
                    REVIEW_ARTIFACT_ROLE_ID,
                ],
            )
            self.assertEqual(
                [
                    item["work_item_id"]
                    for item in discover_experiment_suite_work_items(
                        metadata_a,
                        status="Succeeded",
                        contract_metadata=contract_metadata,
                    )
                ],
                ["simulate_motion_demo_intact"],
            )

            metadata_path = temp_root / "experiment_suite_fixture.json"
            written_path = write_experiment_suite_metadata(
                metadata_a,
                metadata_path,
                contract_metadata=contract_metadata,
            )
            self.assertEqual(
                load_experiment_suite_metadata(
                    written_path,
                    contract_metadata=contract_metadata,
                ),
                metadata_a,
            )
