from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.config import load_config
from flywire_wave.coupling_contract import build_coupling_contract_paths
from flywire_wave.io_utils import read_root_ids, write_json
from flywire_wave.selection import build_subset_artifact_paths
from flywire_wave.showcase_session_planning import (
    package_showcase_session,
    resolve_showcase_session_plan,
)
from flywire_wave.whole_brain_context_contract import (
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    METADATA_JSON_KEY,
    discover_whole_brain_context_session_bundle_paths,
    load_whole_brain_context_session_metadata,
)
from flywire_wave.whole_brain_context_planning import (
    package_whole_brain_context_session,
    resolve_whole_brain_context_session_plan,
)

try:
    from tests.test_dashboard_session_planning import (
        _materialize_dashboard_fixture,
    )
except ModuleNotFoundError:
    from test_dashboard_session_planning import _materialize_dashboard_fixture  # type: ignore[no-redef]

try:
    from tests.test_showcase_session_planning import (
        _materialize_packaged_showcase_fixture,
    )
except ModuleNotFoundError:
    from test_showcase_session_planning import (  # type: ignore[no-redef]
        _materialize_packaged_showcase_fixture,
    )


class WholeBrainContextPlanningTest(unittest.TestCase):
    def test_subset_source_resolves_deterministically_and_packages_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            _materialize_subset_bundle_from_config(
                fixture["config_path"],
                subset_name="motion_minimal",
            )

            first = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                subset_name="motion_minimal",
                explicit_artifact_references=[
                    _fixture_synapse_registry_reference(fixture["config_path"])
                ],
            )
            second = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                subset_name="motion_minimal",
                explicit_artifact_references=[
                    _fixture_synapse_registry_reference(fixture["config_path"])
                ],
            )

            self.assertEqual(first, second)
            self.assertEqual(first["source_mode"], "subset")
            self.assertEqual(first["experiment_id"], "subset_context_motion_minimal")
            self.assertEqual(
                first["query_profile_resolution"]["active_query_profile_id"],
                "downstream_connectivity_context",
            )
            self.assertEqual(
                first["query_profile_resolution"]["available_query_profile_ids"],
                [
                    "active_subset_shell",
                    "upstream_connectivity_context",
                    "downstream_connectivity_context",
                ],
            )

            packaged = package_whole_brain_context_session(first)
            metadata = load_whole_brain_context_session_metadata(packaged["metadata_path"])
            bundle_paths = discover_whole_brain_context_session_bundle_paths(metadata)

            self.assertEqual(metadata["bundle_id"], first["whole_brain_context_session"]["bundle_id"])
            self.assertEqual(
                bundle_paths[METADATA_JSON_KEY],
                Path(packaged["metadata_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID],
                Path(packaged["context_view_payload_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID],
                Path(packaged["context_query_catalog_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID],
                Path(packaged["context_view_state_path"]).resolve(),
            )
            self.assertTrue(
                str(Path(packaged["bundle_directory"]).resolve()).endswith(
                    f"/whole_brain_context_sessions/subset_context_motion_minimal/"
                    f"{metadata['context_spec_hash']}"
                )
            )

    def test_dashboard_source_links_packaged_dashboard_and_uses_bidirectional_defaults(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            plan = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
            )

            self.assertEqual(plan["source_mode"], "dashboard_session")
            self.assertEqual(
                plan["query_profile_resolution"]["active_query_profile_id"],
                "bidirectional_connectivity_context",
            )
            self.assertEqual(
                plan["query_profile_resolution"]["available_query_profile_ids"],
                [
                    "upstream_connectivity_context",
                    "downstream_connectivity_context",
                    "bidirectional_connectivity_context",
                ],
            )
            self.assertEqual(
                plan["linked_sessions"]["dashboard"]["metadata_path"],
                str(Path(fixture["dashboard_metadata_path"]).resolve()),
            )

            packaged = package_whole_brain_context_session(plan)
            query_catalog = json.loads(
                Path(packaged["context_query_catalog_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                query_catalog["active_query_profile_id"],
                "bidirectional_connectivity_context",
            )
            self.assertEqual(
                query_catalog["available_query_profile_ids"],
                plan["query_profile_resolution"]["available_query_profile_ids"],
            )
            self.assertEqual(
                packaged["linked_dashboard_metadata_path"],
                str(Path(fixture["dashboard_metadata_path"]).resolve()),
            )

    def test_subset_source_explicit_artifact_override_wins_over_discovered_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            subset_paths = _materialize_subset_bundle_from_config(
                fixture["config_path"],
                subset_name="motion_minimal",
            )
            override_root_ids_path = Path(tmp_dir_str) / "override_root_ids.txt"
            override_root_ids_path.write_text(
                Path(subset_paths["root_ids_path"]).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            plan = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                subset_name="motion_minimal",
                explicit_artifact_references=[
                    {
                        "artifact_role_id": "selected_root_ids",
                        "path": override_root_ids_path,
                        "bundle_id": "explicit:selected_root_ids_override",
                        "artifact_id": "root_ids_override",
                    },
                    _fixture_synapse_registry_reference(fixture["config_path"]),
                ],
            )

            self.assertEqual(plan["source_mode"], "subset")
            self.assertEqual(
                plan["selection"]["selected_root_ids_path"],
                str(override_root_ids_path.resolve()),
            )
            self.assertEqual(
                plan["registry_sources"]["selected_root_ids"]["bundle_id"],
                "explicit:selected_root_ids_override",
            )
            self.assertEqual(
                plan["registry_sources"]["selected_root_ids"]["path"],
                str(override_root_ids_path.resolve()),
            )

    def test_showcase_source_enables_review_profiles_and_module_request_override(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            showcase_plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
            )
            showcase_package = package_showcase_session(showcase_plan)
            showcase_state = json.loads(
                Path(showcase_package["showcase_state_path"]).read_text(encoding="utf-8")
            )

            plan = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                showcase_session_metadata_path=showcase_package["metadata_path"],
                query_profile_id="downstream_module_review",
                query_profile_ids=["downstream_module_review"],
                requested_downstream_module_role_ids=["simplified_readout_module"],
            )

            self.assertEqual(plan["source_mode"], "showcase_session")
            self.assertEqual(
                plan["query_profile_resolution"]["active_query_profile_id"],
                "downstream_module_review",
            )
            self.assertEqual(
                plan["query_profile_resolution"]["available_query_profile_ids"],
                [
                    "upstream_connectivity_context",
                    "downstream_connectivity_context",
                    "bidirectional_connectivity_context",
                    "pathway_highlight_review",
                    "downstream_module_review",
                ],
            )
            self.assertEqual(
                [item["downstream_module_role_id"] for item in plan["downstream_module_requests"]],
                ["simplified_readout_module"],
            )
            self.assertEqual(
                plan["linked_sessions"]["showcase"]["metadata_path"],
                str(Path(showcase_package["metadata_path"]).resolve()),
            )
            self.assertEqual(
                plan["linked_sessions"]["dashboard"]["metadata_path"],
                str(Path(fixture["dashboard_metadata_path"]).resolve()),
            )
            self.assertEqual(
                plan["linked_sessions"]["showcase"]["focus_root_ids"],
                showcase_state["focus_root_ids"],
            )
            self.assertTrue(
                set(plan["linked_sessions"]["showcase"]["focus_root_ids"]).issubset(
                    set(plan["selection"]["selected_root_ids"])
                )
            )

    def test_planning_fails_clearly_for_missing_synapse_registry_unsupported_combo_and_subset_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            _materialize_subset_bundle_from_config(
                fixture["config_path"],
                subset_name="motion_minimal",
            )
            cfg = load_config(fixture["config_path"])
            synapse_registry_path = (
                Path(
                    _fixture_synapse_registry_reference(fixture["config_path"])["path"]
                ).resolve()
            )
            synapse_registry_path.unlink()

            with self.assertRaises(ValueError) as missing_synapse_ctx:
                resolve_whole_brain_context_session_plan(
                    config_path=fixture["config_path"],
                    subset_name="motion_minimal",
                    query_profile_id="downstream_connectivity_context",
                    explicit_artifact_references=[
                        _fixture_synapse_registry_reference(
                            fixture["config_path"],
                            path=synapse_registry_path,
                        )
                    ],
                )

            self.assertIn("Local synapse registry is missing", str(missing_synapse_ctx.exception))

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            with self.assertRaises(ValueError) as combo_ctx:
                resolve_whole_brain_context_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    query_profile_ids=[
                        "bidirectional_connectivity_context",
                        "downstream_connectivity_context",
                    ],
                )

            self.assertIn("Unsupported whole-brain-context query-profile combination", str(combo_ctx.exception))

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            dashboard_payload_path = Path(
                fixture["dashboard_package"]["session_payload_path"]
            ).resolve()
            payload = json.loads(dashboard_payload_path.read_text(encoding="utf-8"))
            payload["selection"]["selected_root_ids"] = [101, 999]
            payload["pane_inputs"]["circuit"]["selected_root_ids"] = [101, 999]
            write_json(payload, dashboard_payload_path)

            with self.assertRaises(ValueError) as mismatch_ctx:
                resolve_whole_brain_context_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                )

            self.assertIn("do not match the locally resolved active subset", str(mismatch_ctx.exception))


def _materialize_subset_bundle_from_config(
    config_path: str | Path,
    *,
    subset_name: str,
) -> dict[str, str]:
    cfg = load_config(config_path)
    root_ids = read_root_ids(cfg["paths"]["selected_root_ids"])
    subset_paths = build_subset_artifact_paths(
        cfg["paths"]["subset_output_dir"],
        subset_name,
    )
    subset_paths.artifact_dir.mkdir(parents=True, exist_ok=True)
    subset_paths.root_ids.write_text(
        "".join(f"{int(root_id)}\n" for root_id in root_ids),
        encoding="utf-8",
    )
    write_json(
        {
            "subset_manifest_version": "1",
            "preset_name": subset_name,
            "root_ids": [int(root_id) for root_id in root_ids],
            "neurons": [{"root_id": int(root_id)} for root_id in root_ids],
        },
        subset_paths.manifest_json,
    )
    write_json(
        {
            "selection": {
                "final_neuron_count": len(root_ids),
            },
            "relation_steps": [],
        },
        subset_paths.stats_json,
    )
    return {
        "root_ids_path": str(subset_paths.root_ids.resolve()),
        "subset_manifest_path": str(subset_paths.manifest_json.resolve()),
        "subset_stats_path": str(subset_paths.stats_json.resolve()),
    }


def _fixture_synapse_registry_reference(
    config_path: str | Path,
    *,
    path: str | Path | None = None,
) -> dict[str, str]:
    resolved_path = (
        Path(path).resolve()
        if path is not None
        else _discover_fixture_synapse_registry_path(config_path)
    )
    return {
        "artifact_role_id": "synapse_registry",
        "path": str(resolved_path),
        "bundle_id": f"explicit:synapse_registry:{resolved_path.name}",
        "artifact_id": "synapse_registry",
    }


def _discover_fixture_synapse_registry_path(config_path: str | Path) -> Path:
    cfg = load_config(config_path)
    selected_root_ids_parent = Path(cfg["paths"]["selected_root_ids"]).resolve().parent
    candidate = build_coupling_contract_paths(
        selected_root_ids_parent / "processed_coupling"
    ).local_synapse_registry_path
    if candidate.exists():
        return candidate.resolve()
    raise AssertionError(
        f"Expected fixture synapse registry beside selected_root_ids at {candidate}."
    )
