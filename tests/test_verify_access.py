from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

try:
    from .cli_startup_test_utils import run_script_with_blocked_imports
except ImportError:
    from cli_startup_test_utils import run_script_with_blocked_imports  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


class VerifyAccessScriptTest(unittest.TestCase):
    def test_verify_startup_missing_dotenv_is_shaped(self) -> None:
        result = run_script_with_blocked_imports(
            "00_verify_access.py",
            blocked_imports=["dotenv"],
        )

        self.assertNotEqual(result.returncode, 0)
        combined_output = result.stdout + result.stderr
        self.assertNotIn("Traceback", combined_output)
        self.assertIn("python-dotenv", combined_output)
        self.assertIn("make bootstrap", combined_output)
        self.assertIn("make verify", combined_output)

    def test_verify_shapes_info_lookup_failures(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=False)
            stub_dir = _write_verify_stubs(tmp_dir, include_fafbseg=True)

            result = _run_verify(
                config_path,
                stub_dir,
                env_overrides={"VERIFY_STUB_INFO_MODE": "http404"},
                expect_success=False,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertNotIn("Traceback", combined_output)
            self.assertIn("FlyWire/CAVE info lookup failed for datastack 'flywire_fafb_public'", combined_output)
            self.assertIn("dataset.datastack_name", combined_output)

    def test_verify_fails_when_token_sync_needs_cloudvolume(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=False)
            stub_dir = _write_verify_stubs(tmp_dir, include_fafbseg=True)

            result = _run_verify(
                config_path,
                stub_dir,
                env_overrides={"FLYWIRE_TOKEN": "secret-token"},
                expect_success=False,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("FlyWire token sync failed", combined_output)
            self.assertIn("cloudvolume", combined_output)
            self.assertIn("Next step:", combined_output)

    def test_verify_fails_when_fafbseg_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=False)
            stub_dir = _write_verify_stubs(tmp_dir)

            result = _run_verify(config_path, stub_dir, expect_success=False)

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("fafbseg is required for FlyWire mesh access", combined_output)
            self.assertIn("make bootstrap", combined_output)

    def test_verify_requires_navis_when_fetch_skeletons_enabled(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=True)
            stub_dir = _write_verify_stubs(tmp_dir, include_fafbseg=True)

            result = _run_verify(config_path, stub_dir, expect_success=False)

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("navis is required because `meshing.fetch_skeletons` is enabled.", combined_output)
            self.assertIn("meshing.fetch_skeletons: false", combined_output)

    def test_verify_skips_navis_when_fetch_skeletons_disabled(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=False)
            stub_dir = _write_verify_stubs(tmp_dir, include_fafbseg=True)

            result = _run_verify(config_path, stub_dir)

            self.assertEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("navis setup: skipped (`meshing.fetch_skeletons` is false)", combined_output)
            self.assertIn("Mesh preflight looks good.", combined_output)

    def test_verify_auth_only_is_partial_and_skips_mesh_dependencies(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=True)
            stub_dir = _write_verify_stubs(tmp_dir)

            result = _run_verify(config_path, stub_dir, extra_args=["--auth-only"])

            self.assertEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("Verifier mode: auth-only (partial)", combined_output)
            self.assertIn("Access partially verified: auth-only check passed; mesh dependency preflight skipped.", combined_output)
            self.assertNotIn("Mesh preflight looks good.", combined_output)

    def test_verify_fails_when_secret_sync_raises_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=False)
            stub_dir = _write_verify_stubs(tmp_dir, include_fafbseg=True, include_cloudvolume=True)

            result = _run_verify(
                config_path,
                stub_dir,
                env_overrides={
                    "FLYWIRE_TOKEN": "secret-token",
                    "VERIFY_STUB_SECRET_MODE": "error",
                },
                expect_success=False,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("FlyWire token sync failed", combined_output)
            self.assertIn("secret-store access", combined_output)

    def test_verify_rejects_invalid_skeleton_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(
                tmp_dir,
                fetch_skeletons=False,
                require_skeletons=True,
            )
            stub_dir = _write_verify_stubs(tmp_dir)

            result = _run_verify(config_path, stub_dir, expect_success=False)

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("meshing.require_skeletons", combined_output)
            self.assertIn("meshing.fetch_skeletons", combined_output)

    def test_verify_succeeds_when_mesh_prerequisites_are_present(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_verify_config(tmp_dir, fetch_skeletons=True)
            stub_dir = _write_verify_stubs(
                tmp_dir,
                include_fafbseg=True,
                include_navis=True,
                include_cloudvolume=True,
            )

            result = _run_verify(config_path, stub_dir)

            self.assertEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("Info service auth: OK", combined_output)
            self.assertIn("fafbseg setup: OK", combined_output)
            self.assertIn("navis setup: OK", combined_output)
            self.assertIn("Mesh preflight looks good.", combined_output)


def _run_verify(
    config_path: Path,
    stub_dir: Path,
    *,
    env_overrides: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FLYWIRE_TOKEN"] = ""
    env["VERIFY_STUB_INFO_MODE"] = "ok"
    env["VERIFY_STUB_CAVE_INIT_MODE"] = "ok"
    env["VERIFY_STUB_SECRET_MODE"] = ""
    env["VERIFY_STUB_CREDENTIAL_MODE"] = ""
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(stub_dir)
        if not existing_pythonpath
        else os.pathsep.join([str(stub_dir), existing_pythonpath])
    )
    if env_overrides:
        env.update(env_overrides)

    args = [
        sys.executable,
        str(ROOT / "scripts" / "00_verify_access.py"),
        "--config",
        str(config_path),
    ]
    if extra_args:
        args.extend(extra_args)

    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            "verify script failed unexpectedly\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _write_verify_config(
    fixture_dir: Path,
    *,
    fetch_skeletons: bool,
    require_skeletons: bool = False,
) -> Path:
    config_path = fixture_dir / "verify_config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            dataset:
              datastack_name: flywire_fafb_public
              materialization_version: 783
              flywire_dataset: public

            meshing:
              fetch_skeletons: {"true" if fetch_skeletons else "false"}
              require_skeletons: {"true" if require_skeletons else "false"}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path.resolve()


def _write_verify_stubs(
    fixture_dir: Path,
    *,
    include_fafbseg: bool = False,
    include_navis: bool = False,
    include_cloudvolume: bool = False,
) -> Path:
    stub_dir = fixture_dir / "stubs"
    stub_dir.mkdir(parents=True, exist_ok=True)

    (stub_dir / "requests.py").write_text(
        textwrap.dedent(
            """
            class _Response:
                def __init__(self, status_code: int, url: str) -> None:
                    self.status_code = status_code
                    self.url = url


            class HTTPError(Exception):
                def __init__(self, message: str = "", response: _Response | None = None) -> None:
                    super().__init__(message)
                    self.response = response


            class ConnectionError(Exception):
                pass


            class Timeout(Exception):
                pass
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    (stub_dir / "caveclient.py").write_text(
        textwrap.dedent(
            """
            import os
            import requests


            class _Response:
                def __init__(self, status_code: int, url: str) -> None:
                    self.status_code = status_code
                    self.url = url


            def _http_error(status: int, url: str, message: str) -> requests.HTTPError:
                return requests.HTTPError(message, response=_Response(status, url))


            class _InfoClient:
                def get_datastack_info(self, datastack_name: str) -> dict[str, object]:
                    mode = os.getenv("VERIFY_STUB_INFO_MODE", "ok")
                    if mode == "ok":
                        return {
                            "aligned_volume": {"name": "fafb14"},
                            "segmentation_source": "precomputed://stub-segmentation",
                        }
                    if mode == "http404":
                        raise _http_error(
                            404,
                            f"https://global.daf-apis.com/info/datastack/{datastack_name}",
                            "unknown datastack",
                        )
                    if mode == "http403":
                        raise _http_error(
                            403,
                            f"https://global.daf-apis.com/info/datastack/{datastack_name}",
                            "forbidden",
                        )
                    if mode == "network":
                        raise requests.ConnectionError("stub network failure")
                    if mode == "timeout":
                        raise requests.Timeout("stub timeout")
                    raise RuntimeError("stub info-service failure")


            class _MaterializeClient:
                def get_versions(self) -> list[int]:
                    return [783]


                def get_tables(self) -> list[str]:
                    return ["cells"]


            class CAVEclient:
                def __init__(self, datastack_name: str, auth_token: str | None = None) -> None:
                    del auth_token
                    mode = os.getenv("VERIFY_STUB_CAVE_INIT_MODE", "ok")
                    if mode == "http401":
                        raise _http_error(401, "https://global.daf-apis.com/info", "bad token")
                    if mode == "network":
                        raise requests.ConnectionError("stub init network failure")
                    if mode == "timeout":
                        raise requests.Timeout("stub init timeout")
                    if mode == "generic":
                        raise RuntimeError(f"unexpected init failure for {datastack_name}")
                    self.info = _InfoClient()
                    self.materialize = _MaterializeClient()
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    if include_fafbseg:
        fafbseg_dir = stub_dir / "fafbseg"
        fafbseg_dir.mkdir(parents=True, exist_ok=True)
        (fafbseg_dir / "__init__.py").write_text("from . import flywire\n", encoding="utf-8")
        (fafbseg_dir / "flywire.py").write_text(
            textwrap.dedent(
                """
                import os


                def set_default_dataset(dataset: str) -> None:
                    if os.getenv("VERIFY_STUB_DATASET_MODE") == "error":
                        raise ValueError(f"unsupported dataset: {dataset}")


                def set_chunkedgraph_secret(token: str, overwrite: bool = True) -> None:
                    del token, overwrite
                    if os.getenv("VERIFY_STUB_SECRET_MODE") == "error":
                        raise RuntimeError("secret storage unavailable")
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    if include_navis:
        (stub_dir / "navis.py").write_text(
            textwrap.dedent(
                """
                def write_swc(_skeleton: object, _path: str) -> None:
                    return None
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    if include_cloudvolume:
        cloudvolume_dir = stub_dir / "cloudvolume"
        cloudvolume_dir.mkdir(parents=True, exist_ok=True)
        (cloudvolume_dir / "__init__.py").write_text("", encoding="utf-8")
        (cloudvolume_dir / "secrets.py").write_text(
            textwrap.dedent(
                """
                import os


                def cave_credentials(_domain: str) -> dict[str, str]:
                    mode = os.getenv("VERIFY_STUB_CREDENTIAL_MODE", "")
                    if mode == "already-configured":
                        return {"token": os.getenv("FLYWIRE_TOKEN", "").strip()}
                    return {"token": ""}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    return stub_dir


if __name__ == "__main__":
    unittest.main()
