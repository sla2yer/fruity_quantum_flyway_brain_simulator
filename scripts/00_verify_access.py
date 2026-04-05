#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from _startup import bootstrap_runtime

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _bootstrap_dependencies():
    from dotenv import load_dotenv

    import flywire_wave.auth as auth_module
    import flywire_wave.config as config_module

    return load_dotenv, auth_module, config_module


def _http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _http_url(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    return getattr(response, "url", None)


def _is_transient_http_error(exc: BaseException) -> bool:
    status = _http_status(exc)
    return status in {429, 502, 503, 504}


def _call_with_retries(label: str, func: Callable[[], Any], attempts: int = 3) -> Any:
    try:
        import requests
    except Exception as exc:
        raise RuntimeError("requests is required for retry handling.") from exc

    last_exc: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            return func()
        except requests.HTTPError as exc:
            last_exc = exc
            if not _is_transient_http_error(exc) or attempt >= attempts:
                raise
            wait_seconds = 2 ** (attempt - 1)
            status = _http_status(exc)
            url = _http_url(exc) or "<unknown>"
            print(
                f"{label}: transient HTTP {status} from {url}; "
                f"retrying in {wait_seconds}s ({attempt}/{attempts})."
            )
            time.sleep(wait_seconds)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            wait_seconds = 2 ** (attempt - 1)
            print(
                f"{label}: transient network error ({exc}); "
                f"retrying in {wait_seconds}s ({attempt}/{attempts})."
            )
            time.sleep(wait_seconds)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{label} failed before making a request.")


def _format_exception(exc: BaseException) -> str:
    detail = str(exc).strip()
    if detail:
        return f"{type(exc).__name__}: {detail}"
    return type(exc).__name__


def _print_next_step(message: str) -> None:
    print(f"Next step: {message}")


def _resolved_config_path(
    cfg: dict[str, Any],
    fallback: str,
    *,
    config_module: Any,
) -> Path:
    config_path = config_module.get_config_path(cfg)
    if config_path is not None:
        return config_path.resolve()
    return Path(fallback).expanduser().resolve()


def _fail_missing_dependency(message: str) -> int:
    print(message)
    _print_next_step("run `make bootstrap` in this repo, then rerun `make verify`.")
    return 1


def _handle_http_failure(*, label: str, datastack: str, config_path: Path, exc: BaseException) -> int:
    status = _http_status(exc)
    url = _http_url(exc) or "<unknown>"
    if status in {400, 404}:
        print(f"{label} failed for datastack '{datastack}': HTTP {status} from {url}")
        _print_next_step(f"check `dataset.datastack_name` in {config_path} and retry.")
        return 1
    if status in {401, 403}:
        print(f"{label} auth failed for datastack '{datastack}': HTTP {status} from {url}")
        _print_next_step("refresh `FLYWIRE_TOKEN` or your local caveclient token, then rerun `make verify`.")
        return 1
    if _is_transient_http_error(exc):
        print(f"{label} is temporarily unavailable for datastack '{datastack}': HTTP {status} from {url}")
        _print_next_step("retry after the FlyWire service recovers or verify network reachability.")
        return 1
    print(f"{label} failed for datastack '{datastack}': HTTP {status} from {url}")
    _print_next_step(f"confirm the FlyWire service is reachable and recheck {config_path}.")
    return 1


def _handle_network_failure(*, label: str, datastack: str, exc: BaseException) -> int:
    print(f"{label} hit a network error for datastack '{datastack}': {exc}")
    _print_next_step("verify FlyWire network reachability and rerun `make verify`.")
    return 1


def _handle_unexpected_service_failure(*, label: str, datastack: str, config_path: Path, exc: BaseException) -> int:
    print(f"{label} failed for datastack '{datastack}': {_format_exception(exc)}")
    _print_next_step(f"check the FlyWire config in {config_path} and rerun `make verify`.")
    return 1


def _check_materialize_access(*, client: Any, version: int, datastack: str) -> int:
    try:
        import requests
    except Exception:
        return _fail_missing_dependency(
            "requests is required for the optional materialize probe."
        )

    try:
        versions = _call_with_retries("Materialize version lookup", client.materialize.get_versions)
        tables = _call_with_retries("Materialize table lookup", client.materialize.get_tables)
    except requests.HTTPError as exc:
        status = _http_status(exc)
        url = _http_url(exc) or "<unknown>"
        if _is_transient_http_error(exc):
            print(
                "Materialize access is temporarily unavailable "
                f"for datastack '{datastack}': HTTP {status} from {url}"
            )
            _print_next_step("retry after the FlyWire materialize service recovers.")
            return 1
        print(f"Materialize access failed for datastack '{datastack}': HTTP {status} from {url}")
        _print_next_step("confirm the configured materialization service is reachable and retry.")
        return 1
    except (requests.ConnectionError, requests.Timeout) as exc:
        print(f"Materialize access hit a network error for datastack '{datastack}': {exc}")
        _print_next_step("verify FlyWire network reachability and rerun `make verify`.")
        return 1
    except Exception as exc:
        print(f"Materialize access failed for datastack '{datastack}': {_format_exception(exc)}")
        _print_next_step("confirm the configured materialization service is reachable and retry.")
        return 1

    print(f"Requested version: {version}")
    print(f"Materialization versions visible: {versions}")
    print(f"Tables: {tables}")
    print("Materialize access: OK")

    if int(version) not in [int(v) for v in versions]:
        print(f"Requested materialization version {version} is not visible in this environment.")
        _print_next_step("set `dataset.materialization_version` to a visible version and rerun `make verify`.")
        return 1
    return 0


def _check_mesh_prerequisites(
    *,
    flywire_dataset: str,
    fetch_skeletons: bool,
    token: str,
    config_path: Path,
    auth_module: Any,
) -> int:
    if token:
        try:
            token_sync = auth_module.ensure_flywire_secret(token)
        except Exception as exc:
            detail = _format_exception(exc)
            print(f"FlyWire token sync failed for `.env` `FLYWIRE_TOKEN`: {detail}")
            detail_lower = detail.lower()
            if "cloudvolume" in detail_lower:
                _print_next_step(
                    "install `cloudvolume` in the active environment, or run `make bootstrap`, then rerun `make verify`."
                )
            elif "fafbseg" in detail_lower:
                _print_next_step(
                    "install `fafbseg` in the active environment, or run `make bootstrap`, then rerun `make verify`."
                )
            else:
                _print_next_step(
                    "check `.env` `FLYWIRE_TOKEN` and local CAVE/cloudvolume secret-store access, then rerun `make verify`."
                )
            return 1

        if token_sync == "updated":
            print("FlyWire token sync: updated local secret storage")
        elif token_sync == "already-configured":
            print("FlyWire token sync: already configured")
        else:
            print("FlyWire token sync: skipped (no `.env` token)")

    try:
        flywire = importlib.import_module("fafbseg.flywire")
    except Exception:
        return _fail_missing_dependency(
            "fafbseg is required for FlyWire mesh access before `make meshes` can run."
        )

    try:
        flywire.set_default_dataset(flywire_dataset)
    except Exception as exc:
        print(f"FlyWire dataset setup failed for dataset '{flywire_dataset}': {_format_exception(exc)}")
        _print_next_step(
            f"set `dataset.flywire_dataset` to a fafbseg-supported value in {config_path} and rerun `make verify`."
        )
        return 1
    print("fafbseg setup: OK")

    if fetch_skeletons:
        try:
            importlib.import_module("navis")
        except Exception:
            print("navis is required because `meshing.fetch_skeletons` is enabled.")
            _print_next_step(
                f"install `navis`, or set `meshing.fetch_skeletons: false` in {config_path}, before running `make meshes`."
            )
            return 1
        print("navis setup: OK")
    else:
        print("navis setup: skipped (`meshing.fetch_skeletons` is false)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the active FlyWire/CAVE mesh preflight for FAFB public."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--require-materialize",
        action="store_true",
        help="Also require the optional FlyWire materialize probe to succeed.",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Only verify FlyWire auth/info access; skip mesh dependency checks and label the result as partial.",
    )
    args = parser.parse_args()

    dependencies = bootstrap_runtime("verify", _bootstrap_dependencies)
    if dependencies is None:
        return 1
    load_dotenv, auth_module, config_module = dependencies

    load_dotenv(ROOT / ".env")
    try:
        cfg = config_module.load_config(args.config)
    except Exception as exc:
        print(f"Could not load config '{args.config}': {_format_exception(exc)}")
        _print_next_step("fix the config file and rerun `make verify`.")
        return 1

    config_path = _resolved_config_path(cfg, args.config, config_module=config_module)
    try:
        dataset_cfg = cfg["dataset"]
        meshing_cfg = dict(cfg.get("meshing", {}))
        datastack = str(dataset_cfg["datastack_name"])
        version = int(dataset_cfg["materialization_version"])
        flywire_dataset = str(dataset_cfg.get("flywire_dataset", "public"))
    except Exception as exc:
        print(f"Config '{config_path}' is missing required dataset settings: {_format_exception(exc)}")
        _print_next_step("define `dataset.datastack_name` and `dataset.materialization_version`, then rerun `make verify`.")
        return 1

    fetch_skeletons = bool(meshing_cfg.get("fetch_skeletons", True))
    require_skeletons = bool(meshing_cfg.get("require_skeletons", False))
    token = os.getenv("FLYWIRE_TOKEN", "").strip()

    if require_skeletons and not fetch_skeletons:
        print("Config error: `meshing.require_skeletons` cannot be true when `meshing.fetch_skeletons` is false.")
        _print_next_step(
            f"set `meshing.fetch_skeletons: true` or disable `meshing.require_skeletons` in {config_path}."
        )
        return 1

    try:
        from caveclient import CAVEclient
    except Exception:
        return _fail_missing_dependency("caveclient is required for FlyWire/CAVE access verification.")

    try:
        import requests
    except Exception:
        return _fail_missing_dependency("requests is required for FlyWire/CAVE access verification.")

    print(f"Config: {config_path}")
    print(f"Datastack: {datastack}")
    print(f"FlyWire dataset: {flywire_dataset}")
    print(f"Auth source: {'.env FLYWIRE_TOKEN' if token else 'caveclient default token lookup'}")
    print(f"Verifier mode: {'auth-only (partial)' if args.auth_only else 'full mesh preflight'}")
    print(f"Skeleton fetch prerequisite: {'enabled' if fetch_skeletons else 'disabled'}")

    try:
        client = CAVEclient(datastack_name=datastack, auth_token=token or None)
    except requests.HTTPError as exc:
        return _handle_http_failure(
            label="FlyWire/CAVE client initialization",
            datastack=datastack,
            config_path=config_path,
            exc=exc,
        )
    except (requests.ConnectionError, requests.Timeout) as exc:
        return _handle_network_failure(
            label="FlyWire/CAVE client initialization",
            datastack=datastack,
            exc=exc,
        )
    except Exception as exc:
        return _handle_unexpected_service_failure(
            label="FlyWire/CAVE client initialization",
            datastack=datastack,
            config_path=config_path,
            exc=exc,
        )

    try:
        datastack_info = client.info.get_datastack_info(datastack_name=datastack)
    except requests.HTTPError as exc:
        return _handle_http_failure(
            label="FlyWire/CAVE info lookup",
            datastack=datastack,
            config_path=config_path,
            exc=exc,
        )
    except (requests.ConnectionError, requests.Timeout) as exc:
        return _handle_network_failure(
            label="FlyWire/CAVE info lookup",
            datastack=datastack,
            exc=exc,
        )
    except Exception as exc:
        return _handle_unexpected_service_failure(
            label="FlyWire/CAVE info lookup",
            datastack=datastack,
            config_path=config_path,
            exc=exc,
        )

    aligned_volume = datastack_info.get("aligned_volume", {})
    print(f"Aligned volume: {aligned_volume.get('name', '<unknown>')}")
    print(f"Segmentation source: {datastack_info.get('segmentation_source', '<unknown>')}")
    print("Info service auth: OK")

    if args.require_materialize:
        materialize_status = _check_materialize_access(client=client, version=version, datastack=datastack)
        if materialize_status != 0:
            return materialize_status

    if args.auth_only:
        print("Access partially verified: auth-only check passed; mesh dependency preflight skipped.")
        return 0

    prerequisite_status = _check_mesh_prerequisites(
        flywire_dataset=flywire_dataset,
        fetch_skeletons=fetch_skeletons,
        token=token,
        config_path=config_path,
        auth_module=auth_module,
    )
    if prerequisite_status != 0:
        return prerequisite_status

    print("Mesh preflight looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
