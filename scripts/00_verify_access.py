#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.auth import ensure_flywire_secret
from flywire_wave.config import load_config


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify FlyWire/CAVE access for FAFB public.")
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--require-materialize",
        action="store_true",
        help="Exit non-zero if the FlyWire materialize service is unavailable.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    cfg = load_config(args.config)
    datastack = cfg["dataset"]["datastack_name"]
    version = cfg["dataset"]["materialization_version"]
    flywire_dataset = cfg["dataset"].get("flywire_dataset", "public")
    token = os.getenv("FLYWIRE_TOKEN", "").strip()

    try:
        from caveclient import CAVEclient
    except Exception as exc:
        raise RuntimeError("caveclient is not installed. Run: pip install -r requirements.txt") from exc

    try:
        import requests
    except Exception as exc:
        raise RuntimeError("requests is not installed. Run: pip install -r requirements.txt") from exc

    try:
        client = CAVEclient(datastack_name=datastack, auth_token=token or None)
    except requests.HTTPError as exc:
        status = _http_status(exc)
        url = _http_url(exc) or "<unknown>"
        if status in {400, 401, 403}:
            print("FlyWire/CAVE auth failed while contacting the global info service.")
            print(f"URL: {url}")
            print("Refresh the token and update .env, then rerun this script.")
            return 1
        print(f"Could not initialize the CAVE client: HTTP {status} from {url}")
        return 1
    except (requests.ConnectionError, requests.Timeout) as exc:
        print(f"Network error while contacting the FlyWire info service: {exc}")
        return 1

    datastack_info = client.info.get_datastack_info(datastack_name=datastack)
    local_server = client.info.local_server()
    print(f"Datastack: {datastack}")
    print(f"Auth source: {'.env FLYWIRE_TOKEN' if token else 'caveclient default token lookup'}")
    print(f"Aligned volume: {datastack_info['aligned_volume']['name']}")
    print(f"Local server: {local_server}")
    print(f"Segmentation source: {datastack_info['segmentation_source']}")
    print("Info service auth: OK")

    materialize_available = False
    try:
        versions = _call_with_retries("Materialize version lookup", client.materialize.get_versions)
        tables = _call_with_retries("Materialize table lookup", client.materialize.get_tables)
        materialize_available = True
    except requests.HTTPError as exc:
        status = _http_status(exc)
        url = _http_url(exc) or f"{local_server}/materialize"
        if _is_transient_http_error(exc):
            print(
                "Materialize access: TEMPORARILY UNAVAILABLE "
                f"(HTTP {status} from {url})"
            )
            print(
                "This appears to be an upstream FlyWire service outage, not a token failure."
            )
            print("Requested materialization version check skipped for now.")
            if args.require_materialize:
                return 2
        else:
            print(f"Materialize access failed: HTTP {status} from {url}")
            return 1
    except (requests.ConnectionError, requests.Timeout) as exc:
        print(f"Materialize access failed with a network error: {exc}")
        if args.require_materialize:
            return 2

    print(f"Requested version: {version}")
    if materialize_available:
        print(f"Materialization versions visible: {versions}")
        print(f"Tables: {tables}")
        print("Materialize access: OK")

        if int(version) not in [int(v) for v in versions]:
            print(
                f"Requested materialization version {version} is not visible in this environment."
            )
            return 1

    try:
        from fafbseg import flywire

        token_sync = "missing"
        if token:
            token_sync = ensure_flywire_secret(token)
        flywire.set_default_dataset(flywire_dataset)
        if token_sync == "updated":
            print("fafbseg token sync: updated local secret storage")
        elif token_sync == "already-configured":
            print("fafbseg token sync: already configured")
        else:
            print("fafbseg token sync: skipped (no .env token)")
        print("fafbseg setup: OK")
    except Exception as exc:
        print(f"Warning: fafbseg verification skipped/failed: {exc}")

    if materialize_available:
        print("Access looks good.")
    else:
        print("Access looks partially verified: token/auth OK, materialize unavailable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
