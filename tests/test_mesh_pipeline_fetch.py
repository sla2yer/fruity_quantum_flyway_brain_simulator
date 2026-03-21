from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    ASSET_STATUS_SKIPPED,
    FETCH_STATUS_CACHE_HIT,
    FETCH_STATUS_FAILED,
    FETCH_STATUS_FETCHED,
    FETCH_STATUS_SKIPPED,
    GeometryBundlePaths,
    RAW_MESH_KEY,
    RAW_SKELETON_KEY,
    build_geometry_bundle_paths,
)
from flywire_wave.mesh_pipeline import RawAssetFetchError, fetch_mesh_and_optional_skeleton


class _MeshNeuron:
    def __init__(self, *, apex_z: float = 1.0) -> None:
        self.vertices = [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, apex_z],
        ]
        self.faces = [
            [0, 1, 2],
            [0, 1, 3],
            [0, 2, 3],
            [1, 2, 3],
        ]


class MeshFetchPipelineTest(unittest.TestCase):
    def test_fetch_reuses_valid_cached_assets_by_default(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            bundle_paths = _bundle_paths(Path(tmp_dir_str))
            _write_valid_mesh(bundle_paths.raw_mesh_path)
            _write_valid_swc(bundle_paths.raw_skeleton_path)

            def unexpected_mesh_fetch(_root_id: int) -> _MeshNeuron:
                raise AssertionError("mesh fetch should not run on a healthy cache hit")

            def unexpected_skeleton_fetch(_root_id: int) -> object:
                raise AssertionError("skeleton fetch should not run on a healthy cache hit")

            outputs = fetch_mesh_and_optional_skeleton(
                root_id=101,
                bundle_paths=bundle_paths,
                flywire_dataset="public",
                fetch_skeletons=True,
                set_default_dataset=lambda _dataset: None,
                mesh_fetcher=unexpected_mesh_fetch,
                skeleton_fetcher=unexpected_skeleton_fetch,
                skeleton_writer=lambda _skeleton, _path: None,
            )

            self.assertEqual(outputs["asset_statuses"][RAW_MESH_KEY], ASSET_STATUS_READY)
            self.assertEqual(outputs["asset_statuses"][RAW_SKELETON_KEY], ASSET_STATUS_READY)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["fetch_status"], FETCH_STATUS_CACHE_HIT)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["fetch_status"], FETCH_STATUS_CACHE_HIT)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["cache_before"]["state"], "valid")
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["cache_before"]["state"], "valid")

    def test_fetch_recovers_from_invalid_mesh_cache(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            bundle_paths = _bundle_paths(Path(tmp_dir_str))
            bundle_paths.raw_mesh_path.parent.mkdir(parents=True, exist_ok=True)
            bundle_paths.raw_mesh_path.write_bytes(b"")

            mesh_fetch_calls = 0

            def mesh_fetcher(_root_id: int) -> _MeshNeuron:
                nonlocal mesh_fetch_calls
                mesh_fetch_calls += 1
                return _MeshNeuron(apex_z=2.0)

            outputs = fetch_mesh_and_optional_skeleton(
                root_id=101,
                bundle_paths=bundle_paths,
                flywire_dataset="public",
                fetch_skeletons=False,
                set_default_dataset=lambda _dataset: None,
                mesh_fetcher=mesh_fetcher,
            )

            self.assertEqual(mesh_fetch_calls, 1)
            self.assertEqual(outputs["asset_statuses"][RAW_MESH_KEY], ASSET_STATUS_READY)
            self.assertEqual(outputs["asset_statuses"][RAW_SKELETON_KEY], ASSET_STATUS_SKIPPED)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["fetch_status"], FETCH_STATUS_FETCHED)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["fetch_reason"], "invalid_cache")
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["cache_before"]["reason"], "empty_file")
            self.assertGreater(bundle_paths.raw_mesh_path.stat().st_size, 0)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["fetch_status"], FETCH_STATUS_SKIPPED)

    def test_force_refetch_bypasses_healthy_cache(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            bundle_paths = _bundle_paths(Path(tmp_dir_str))
            _write_valid_mesh(bundle_paths.raw_mesh_path)
            _write_valid_swc(bundle_paths.raw_skeleton_path)

            mesh_fetch_calls = 0
            skeleton_fetch_calls = 0

            def mesh_fetcher(_root_id: int) -> _MeshNeuron:
                nonlocal mesh_fetch_calls
                mesh_fetch_calls += 1
                return _MeshNeuron(apex_z=2.0)

            def skeleton_fetcher(_root_id: int) -> object:
                nonlocal skeleton_fetch_calls
                skeleton_fetch_calls += 1
                return object()

            outputs = fetch_mesh_and_optional_skeleton(
                root_id=101,
                bundle_paths=bundle_paths,
                flywire_dataset="public",
                fetch_skeletons=True,
                refetch_mesh=True,
                refetch_skeleton=True,
                set_default_dataset=lambda _dataset: None,
                mesh_fetcher=mesh_fetcher,
                skeleton_fetcher=skeleton_fetcher,
                skeleton_writer=lambda _skeleton, path: _write_valid_swc(Path(path)),
            )

            self.assertEqual(mesh_fetch_calls, 1)
            self.assertEqual(skeleton_fetch_calls, 1)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["fetch_status"], FETCH_STATUS_FETCHED)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["fetch_status"], FETCH_STATUS_FETCHED)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_MESH_KEY]["fetch_reason"], "forced_refetch")
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["fetch_reason"], "forced_refetch")

    def test_optional_skeleton_failure_is_recorded_without_failing_run(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            bundle_paths = _bundle_paths(Path(tmp_dir_str))

            outputs = fetch_mesh_and_optional_skeleton(
                root_id=101,
                bundle_paths=bundle_paths,
                flywire_dataset="public",
                fetch_skeletons=True,
                set_default_dataset=lambda _dataset: None,
                mesh_fetcher=lambda _root_id: _MeshNeuron(),
                skeleton_fetcher=_failing_skeleton_fetcher,
                skeleton_writer=lambda _skeleton, path: _write_valid_swc(Path(path)),
            )

            self.assertEqual(outputs["asset_statuses"][RAW_MESH_KEY], ASSET_STATUS_READY)
            self.assertEqual(outputs["asset_statuses"][RAW_SKELETON_KEY], ASSET_STATUS_MISSING)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["fetch_status"], FETCH_STATUS_FAILED)
            self.assertEqual(outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["cache_before"]["state"], "missing")
            self.assertIn("skeleton endpoint unavailable", outputs["raw_asset_provenance"][RAW_SKELETON_KEY]["error"])

    def test_required_skeleton_failure_raises_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            bundle_paths = _bundle_paths(Path(tmp_dir_str))

            with self.assertRaises(RawAssetFetchError) as exc_info:
                fetch_mesh_and_optional_skeleton(
                    root_id=101,
                    bundle_paths=bundle_paths,
                    flywire_dataset="public",
                    fetch_skeletons=True,
                    require_skeletons=True,
                    set_default_dataset=lambda _dataset: None,
                    mesh_fetcher=lambda _root_id: _MeshNeuron(),
                    skeleton_fetcher=_failing_skeleton_fetcher,
                    skeleton_writer=lambda _skeleton, path: _write_valid_swc(Path(path)),
                )

            exc = exc_info.exception
            self.assertEqual(exc.asset_statuses[RAW_MESH_KEY], ASSET_STATUS_READY)
            self.assertEqual(exc.asset_statuses[RAW_SKELETON_KEY], ASSET_STATUS_MISSING)
            self.assertEqual(exc.raw_asset_provenance[RAW_SKELETON_KEY]["fetch_status"], FETCH_STATUS_FAILED)


def _bundle_paths(tmp_dir: Path) -> GeometryBundlePaths:
    return build_geometry_bundle_paths(
        101,
        meshes_raw_dir=tmp_dir / "meshes_raw",
        skeletons_raw_dir=tmp_dir / "skeletons_raw",
        processed_mesh_dir=tmp_dir / "processed_meshes",
        processed_graph_dir=tmp_dir / "processed_graphs",
    )


def _write_valid_mesh(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ply
            format ascii 1.0
            element vertex 4
            property float x
            property float y
            property float z
            element face 4
            property list uchar int vertex_indices
            end_header
            0 0 0
            1 0 0
            0 1 0
            0 0 1
            3 0 1 2
            3 0 1 3
            3 0 2 3
            3 1 2 3
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_valid_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# stub skeleton",
                "1 1 0 0 0 1 -1",
                "2 3 0 1 0 1 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _failing_skeleton_fetcher(_root_id: int) -> object:
    raise RuntimeError("skeleton endpoint unavailable")


if __name__ == "__main__":
    unittest.main()
