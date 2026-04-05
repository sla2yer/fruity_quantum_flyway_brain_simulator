from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")

_PACKAGE_NAME_OVERRIDES = {
    "dotenv": "python-dotenv",
    "PIL": "pillow",
    "yaml": "pyyaml",
}


def package_name_for_module(module_name: str) -> str:
    top_level = module_name.split(".", 1)[0]
    return _PACKAGE_NAME_OVERRIDES.get(top_level, top_level)


def format_missing_dependency_message(*, command_name: str, module_name: str) -> str:
    package_name = package_name_for_module(module_name)
    return (
        f"Missing Python package `{package_name}` in the active interpreter; "
        f"run `make bootstrap` in this repo, then rerun `make {command_name}`."
    )


def bootstrap_runtime(command_name: str, loader: Callable[[], T]) -> T | None:
    try:
        return loader()
    except ModuleNotFoundError as exc:
        module_name = (exc.name or "").split(".", 1)[0]
        if not module_name or module_name == "flywire_wave":
            raise
        print(format_missing_dependency_message(command_name=command_name, module_name=module_name))
        return None
