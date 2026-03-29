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

from flywire_wave.validation_contract import (
    CIRCUIT_RESPONSE_FAMILY_ID,
    CIRCUIT_SANITY_LAYER_ID,
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
    EXPERIMENT_NULL_TEST_SCOPE,
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
    METADATA_JSON_KEY,
    MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
    MORPHOLOGY_DEPENDENCE_FAMILY_ID,
    MORPHOLOGY_SANITY_LAYER_ID,
    NUMERICAL_SANITY_LAYER_ID,
    NUMERICAL_STABILITY_FAMILY_ID,
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
    OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
    REVIEW_HANDOFF_ARTIFACT_ID,
    REVIEW_OWNER_GRANT,
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
    TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
    TASK_SANITY_LAYER_ID,
    VALIDATION_LADDER_CONTRACT_VERSION,
    VALIDATION_LADDER_DESIGN_NOTE,
    VALIDATION_STATUS_REVIEW,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    build_validation_bundle_metadata,
    build_validation_ladder_contract_metadata,
    build_validation_plan_reference,
    discover_validation_bundle_paths,
    discover_validation_layers,
    discover_validation_validator_definitions,
    discover_validation_validator_families,
    get_validation_validator_definition,
    load_validation_bundle_metadata,
    load_validation_ladder_contract_metadata,
    write_validation_bundle_metadata,
    write_validation_ladder_contract_metadata,
)


def _humanize_identifier(identifier: str) -> str:
    return identifier.replace("_", " ").title()


def _mutate_contract_fixture(
    metadata: dict[str, object],
    *,
    reverse: bool,
) -> dict[str, list[dict[str, object]]]:
    evidence_scopes: list[dict[str, object]] = []
    for entry in metadata["evidence_scope_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["evidence_scope_id"] = _humanize_identifier(
            str(mutated["evidence_scope_id"])
        )
        mutated["required_upstream_contracts"] = list(
            reversed(list(mutated["required_upstream_contracts"]))
        )
        evidence_scopes.append(mutated)

    layers: list[dict[str, object]] = []
    for entry in metadata["layer_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["layer_id"] = _humanize_identifier(str(mutated["layer_id"]))
        mutated["validator_family_ids"] = [
            _humanize_identifier(str(item))
            for item in reversed(list(mutated["validator_family_ids"]))
        ]
        mutated["required_upstream_contracts"] = list(
            reversed(list(mutated["required_upstream_contracts"]))
        )
        layers.append(mutated)

    families: list[dict[str, object]] = []
    for entry in metadata["validator_family_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["validator_family_id"] = _humanize_identifier(
            str(mutated["validator_family_id"])
        )
        mutated["layer_id"] = _humanize_identifier(str(mutated["layer_id"]))
        mutated["validator_ids"] = [
            _humanize_identifier(str(item))
            for item in reversed(list(mutated["validator_ids"]))
        ]
        mutated["required_evidence_scope_ids"] = [
            _humanize_identifier(str(item))
            for item in reversed(list(mutated["required_evidence_scope_ids"]))
        ]
        mutated["required_upstream_contracts"] = list(
            reversed(list(mutated["required_upstream_contracts"]))
        )
        families.append(mutated)

    validators: list[dict[str, object]] = []
    for entry in metadata["validator_catalog"]:
        mutated = copy.deepcopy(entry)
        mutated["validator_id"] = _humanize_identifier(str(mutated["validator_id"]))
        mutated["validator_family_id"] = _humanize_identifier(
            str(mutated["validator_family_id"])
        )
        mutated["required_evidence_scope_ids"] = [
            _humanize_identifier(str(item))
            for item in reversed(list(mutated["required_evidence_scope_ids"]))
        ]
        mutated["required_upstream_contracts"] = list(
            reversed(list(mutated["required_upstream_contracts"]))
        )
        mutated["supported_result_statuses"] = list(
            reversed(list(mutated["supported_result_statuses"]))
        )
        validators.append(mutated)

    if reverse:
        evidence_scopes.reverse()
        layers.reverse()
        families.reverse()
        validators.reverse()

    return {
        "evidence_scopes": evidence_scopes,
        "layer_definitions": layers,
        "validator_family_definitions": families,
        "validator_definitions": validators,
    }


class ValidationContractTest(unittest.TestCase):
    def test_default_contract_exposes_milestone13_taxonomy(self) -> None:
        metadata = build_validation_ladder_contract_metadata()

        self.assertEqual(metadata["contract_version"], VALIDATION_LADDER_CONTRACT_VERSION)
        self.assertEqual(metadata["design_note"], VALIDATION_LADDER_DESIGN_NOTE)
        self.assertEqual(
            [item["layer_id"] for item in discover_validation_layers(metadata)],
            [
                NUMERICAL_SANITY_LAYER_ID,
                MORPHOLOGY_SANITY_LAYER_ID,
                CIRCUIT_SANITY_LAYER_ID,
                TASK_SANITY_LAYER_ID,
            ],
        )
        self.assertEqual(
            [
                item["validator_family_id"]
                for item in discover_validation_validator_families(
                    metadata,
                    layer_id="Numerical Sanity",
                )
            ],
            [NUMERICAL_STABILITY_FAMILY_ID],
        )
        self.assertEqual(
            [
                item["validator_family_id"]
                for item in discover_validation_validator_families(
                    metadata,
                    layer_id=CIRCUIT_SANITY_LAYER_ID,
                )
            ],
            [CIRCUIT_RESPONSE_FAMILY_ID],
        )
        self.assertEqual(
            [
                item["validator_id"]
                for item in discover_validation_validator_definitions(
                    metadata,
                    layer_id=TASK_SANITY_LAYER_ID,
                )
            ],
            [
                SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
            ],
        )
        self.assertEqual(
            [
                item["validator_id"]
                for item in discover_validation_validator_definitions(
                    metadata,
                    evidence_scope_id=EXPERIMENT_NULL_TEST_SCOPE,
                )
            ],
            [
                GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
                SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
            ],
        )
        self.assertEqual(
            get_validation_validator_definition(
                "Surface Wave Stability Envelope",
                record=metadata,
            )["validator_id"],
            SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
        )
        self.assertEqual(
            get_validation_validator_definition(
                "Geometry Dependence Collapse",
                record=metadata,
            )["criteria_profile_reference"],
            "validation_criteria.morphology_dependence.geometry_dependence_collapse.v1",
        )
        self.assertEqual(metadata["criteria_handoff"]["review_owner"], REVIEW_OWNER_GRANT)
        self.assertEqual(
            metadata["criteria_handoff"]["review_status"],
            VALIDATION_STATUS_REVIEW,
        )
        self.assertEqual(
            metadata["criteria_handoff"]["review_artifact_id"],
            REVIEW_HANDOFF_ARTIFACT_ID,
        )
        self.assertEqual(
            metadata["artifact_catalog"][REVIEW_HANDOFF_ARTIFACT_ID]["relative_path"],
            "review_handoff.json",
        )

    def test_fixture_contract_serializes_deterministically_and_discovers_validators(self) -> None:
        default_metadata = build_validation_ladder_contract_metadata()
        fixture_a = _mutate_contract_fixture(default_metadata, reverse=False)
        fixture_b = _mutate_contract_fixture(default_metadata, reverse=True)

        metadata_a = build_validation_ladder_contract_metadata(**fixture_a)
        metadata_b = build_validation_ladder_contract_metadata(**fixture_b)

        self.assertEqual(metadata_a, metadata_b)
        self.assertEqual(
            [
                item["validator_family_id"]
                for item in metadata_a["validator_family_catalog"]
            ],
            [
                CIRCUIT_RESPONSE_FAMILY_ID,
                MORPHOLOGY_DEPENDENCE_FAMILY_ID,
                NUMERICAL_STABILITY_FAMILY_ID,
                TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
            ],
        )
        self.assertEqual(
            [item["validator_id"] for item in metadata_a["validator_catalog"]],
            [
                COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
                MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
                MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
                SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
            ],
        )
        self.assertEqual(
            [
                item["validator_id"]
                for item in discover_validation_validator_definitions(
                    {"validation_ladder_contract": metadata_a},
                    layer_id="Morphology Sanity",
                )
            ],
            [
                GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
                MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
            ],
        )
        self.assertEqual(
            [
                item["validator_id"]
                for item in discover_validation_validator_definitions(
                    metadata_a,
                    validator_family_id="Task Effect Reproducibility",
                )
            ],
            [
                SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
            ],
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            contract_path = tmp_dir / "validation_ladder_contract.json"
            written_contract_path = write_validation_ladder_contract_metadata(
                metadata_a,
                contract_path,
            )
            loaded_contract = load_validation_ladder_contract_metadata(written_contract_path)

            self.assertEqual(loaded_contract, metadata_a)
            self.assertEqual(
                written_contract_path.read_text(encoding="utf-8"),
                json.dumps(metadata_a, indent=2, sort_keys=True),
            )

            plan_a = build_validation_plan_reference(
                experiment_id="Fixture Motion Demo",
                active_layer_ids=[
                    "Task Sanity",
                    "Circuit Sanity",
                    "Morphology Sanity",
                    "Numerical Sanity",
                ],
                active_validator_family_ids=[
                    "Task Effect Reproducibility",
                    "Circuit Response",
                    "Morphology Dependence",
                    "Numerical Stability",
                ],
                active_validator_ids=[
                    "Task Decoder Robustness",
                    "Shared Effect Reproducibility",
                    "Motion Pathway Asymmetry",
                    "Coupling Semantics Continuity",
                    "Geometry Dependence Collapse",
                    "Mixed Fidelity Surrogate Preservation",
                    "Surface Wave Stability Envelope",
                    "Operator Bundle Gate Alignment",
                ],
                criteria_profile_references=[
                    "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1",
                    "validation_criteria.task_effect_reproducibility.shared_effect_reproducibility.v1",
                    "validation_criteria.circuit_response.motion_pathway_asymmetry.v1",
                    "validation_criteria.circuit_response.coupling_semantics_continuity.v1",
                    "validation_criteria.morphology_dependence.geometry_dependence_collapse.v1",
                    "validation_criteria.morphology_dependence.mixed_fidelity_surrogate_preservation.v1",
                    "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1",
                    "validation_criteria.numerical_stability.operator_bundle_gate_alignment.v1",
                ],
                evidence_bundle_references={
                    "experiment_analysis_bundle": {
                        "bundle_id": "experiment_analysis_bundle.v1:fixture_motion_demo:analysishash",
                        "contract_version": "experiment_analysis_bundle.v1",
                    },
                    "simulator_result_bundle": {
                        "bundle_ids": [
                            "simulator_result_bundle.v1:fixture_motion_demo:surface_wave_intact:runhash"
                        ]
                    },
                },
                target_arm_ids=[
                    "surface_wave_intact",
                    "baseline_p0_intact",
                ],
                comparison_group_ids=[
                    "geometry_ablation__p0",
                    "matched_surface_wave_vs_p0__intact",
                ],
                criteria_profile_assignments=[
                    {
                        "validator_id": "Task Decoder Robustness",
                        "criteria_profile_reference": "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1",
                    },
                    {
                        "validator_id": "Surface Wave Stability Envelope",
                        "criteria_profile_reference": "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1",
                    },
                ],
                perturbation_suite_references=[
                    {
                        "suite_id": "Noise Robustness",
                        "suite_kind": "noise_robustness",
                        "target_layer_ids": ["Task Sanity"],
                        "target_validator_ids": ["Task Decoder Robustness"],
                        "variant_ids": ["seed_17__noise_0p0", "seed_23__noise_0p1"],
                    },
                    {
                        "suite_id": "Geometry Variants",
                        "suite_kind": "geometry_variant",
                        "target_layer_ids": ["Morphology Sanity"],
                        "target_validator_ids": ["Geometry Dependence Collapse"],
                        "variant_ids": ["shuffled", "intact"],
                    },
                ],
            )
            plan_b = build_validation_plan_reference(
                experiment_id="fixture_motion_demo",
                active_layer_ids=list(reversed(plan_a["active_layer_ids"])),
                active_validator_family_ids=list(
                    reversed(plan_a["active_validator_family_ids"])
                ),
                active_validator_ids=list(reversed(plan_a["active_validator_ids"])),
                criteria_profile_references=list(
                    reversed(plan_a["criteria_profile_references"])
                ),
                evidence_bundle_references=dict(plan_a["evidence_bundle_references"]),
                target_arm_ids=list(reversed(plan_a["target_arm_ids"])),
                comparison_group_ids=list(reversed(plan_a["comparison_group_ids"])),
                criteria_profile_assignments=list(
                    reversed(plan_a["criteria_profile_assignments"])
                ),
                perturbation_suite_references=list(
                    reversed(plan_a["perturbation_suite_references"])
                ),
            )

            self.assertEqual(
                plan_a["criteria_profile_assignments"],
                [
                    {
                        "validator_id": SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                        "criteria_profile_reference": "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1",
                    },
                    {
                        "validator_id": TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                        "criteria_profile_reference": "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1",
                    },
                ],
            )
            self.assertEqual(
                [item["suite_id"] for item in plan_a["perturbation_suite_references"]],
                ["geometry_variants", "noise_robustness"],
            )

            bundle_metadata_a = build_validation_bundle_metadata(
                validation_plan_reference=plan_a,
                processed_simulator_results_dir=tmp_dir / "out",
                contract_metadata=metadata_a,
            )
            bundle_metadata_b = build_validation_bundle_metadata(
                validation_plan_reference=plan_b,
                processed_simulator_results_dir=tmp_dir / "out",
                contract_metadata=metadata_b,
            )
            self.assertEqual(bundle_metadata_a, bundle_metadata_b)

            written_bundle_path = write_validation_bundle_metadata(bundle_metadata_a)
            loaded_bundle = load_validation_bundle_metadata(written_bundle_path)
            discovered_paths = discover_validation_bundle_paths(
                {"validation_bundle": loaded_bundle}
            )

            self.assertEqual(loaded_bundle, bundle_metadata_a)
            self.assertEqual(discovered_paths[METADATA_JSON_KEY], written_bundle_path.resolve())
            self.assertEqual(
                discovered_paths[VALIDATION_SUMMARY_ARTIFACT_ID].name,
                "validation_summary.json",
            )
            self.assertEqual(
                discovered_paths[REVIEW_HANDOFF_ARTIFACT_ID].name,
                "review_handoff.json",
            )
            self.assertEqual(
                discovered_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID].name,
                "validation_report.md",
            )


if __name__ == "__main__":
    unittest.main()
