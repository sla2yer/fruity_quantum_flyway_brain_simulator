from __future__ import annotations

import contextlib
import io

CAVE_AUTH_DOMAINS = ("global.daf-apis.com", "prod.flywire-daf.com")


def ensure_flywire_secret(token: str) -> str:
    """Sync a repo token into the local CAVE/cloudvolume secret store if needed."""
    normalized = token.strip()
    if not normalized:
        return "missing"

    try:
        from cloudvolume.secrets import cave_credentials
    except Exception as exc:
        raise RuntimeError("cloudvolume is required for FlyWire secret handling.") from exc

    resolved_tokens = []
    for domain in CAVE_AUTH_DOMAINS:
        creds = cave_credentials(domain)
        resolved_tokens.append((creds.get("token") or "").strip())

    if resolved_tokens and all(current == normalized for current in resolved_tokens):
        return "already-configured"

    try:
        from fafbseg import flywire
    except Exception as exc:
        raise RuntimeError("fafbseg is required for FlyWire secret handling.") from exc

    with contextlib.redirect_stdout(io.StringIO()):
        flywire.set_chunkedgraph_secret(normalized, overwrite=True)
    return "updated"
