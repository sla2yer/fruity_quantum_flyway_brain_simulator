from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script_with_blocked_imports(
    script_name: str,
    *,
    blocked_imports: list[str],
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        (tmp_dir / "sitecustomize.py").write_text(
            textwrap.dedent(
                """
                import importlib.abc
                import importlib.util
                import os
                import sys


                _BLOCKED = {
                    item.strip()
                    for item in os.getenv("FLYWIRE_WAVE_TEST_BLOCK_IMPORTS", "").split(",")
                    if item.strip()
                }


                class _BlockedLoader(importlib.abc.Loader):
                    def create_module(self, spec):
                        return None


                    def exec_module(self, module):
                        raise ModuleNotFoundError(
                            f"No module named '{module.__spec__.name}'",
                            name=module.__spec__.name,
                        )


                class _BlockedFinder(importlib.abc.MetaPathFinder):
                    def find_spec(self, fullname, path=None, target=None):
                        top_level = fullname.split(".", 1)[0]
                        if top_level in _BLOCKED:
                            return importlib.util.spec_from_loader(
                                fullname,
                                _BlockedLoader(),
                                origin="blocked-import",
                            )
                        return None


                if _BLOCKED:
                    sys.meta_path.insert(0, _BlockedFinder())
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["FLYWIRE_WAVE_TEST_BLOCK_IMPORTS"] = ",".join(blocked_imports)
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(tmp_dir)
            if not existing_pythonpath
            else os.pathsep.join([str(tmp_dir), existing_pythonpath])
        )

        args = [
            sys.executable,
            str(ROOT / "scripts" / script_name),
            "--config",
            str(ROOT / "config" / "local.yaml"),
        ]
        if extra_args:
            args.extend(extra_args)

        return subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
