from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


ArtifactReferenceBuilder = Callable[..., dict[str, Any]]
ArtifactStatusResolver = Callable[
    [str, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], str], str
]


def lift_packaged_artifact_references(
    *,
    metadata: Mapping[str, Any],
    bundle_paths: Mapping[str, str | Path],
    contract_metadata: Mapping[str, Any],
    source_kind: str,
    build_artifact_reference: ArtifactReferenceBuilder,
) -> list[dict[str, Any]]:
    artifacts = _artifact_catalog(metadata)
    discovered: list[dict[str, Any]] = []
    for hook in _artifact_hooks_for_source_kind(
        contract_metadata,
        source_kind=source_kind,
    ):
        artifact_id = str(hook["artifact_id"])
        artifact = _artifact_record(
            artifacts,
            artifact_id=artifact_id,
            field_name=f"metadata.artifacts[{artifact_id!r}]",
        )
        if artifact_id not in bundle_paths:
            raise ValueError(
                "Bundle paths are missing an artifact path for "
                f"{artifact_id!r} required by source_kind {source_kind!r}."
            )
        discovered.append(
            build_artifact_reference(
                artifact_role_id=str(hook["artifact_role_id"]),
                source_kind=str(hook["source_kind"]),
                path=bundle_paths[artifact_id],
                contract_version=hook.get("required_contract_version"),
                bundle_id=str(metadata["bundle_id"]),
                artifact_id=artifact_id,
                format=_optional_string(artifact.get("format")),
                artifact_scope=_optional_string(hook.get("artifact_scope")),
                status=_status_value(artifact),
            )
        )
    return discovered


def merge_explicit_artifact_overrides(
    discovered: Sequence[Mapping[str, Any]],
    *,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
    build_artifact_reference: ArtifactReferenceBuilder,
    resolve_status: ArtifactStatusResolver,
) -> list[dict[str, Any]]:
    hooks = artifact_hook_catalog_by_role(contract_metadata)
    merged = {
        str(item["artifact_role_id"]): copy.deepcopy(dict(item)) for item in discovered
    }
    for role_id, raw in raw_explicit_artifacts.items():
        hook = hooks.get(role_id)
        if hook is None:
            raise ValueError(
                "explicit_artifact_references contains unsupported "
                f"artifact_role_id {role_id!r}."
            )
        base = merged.get(role_id, {})
        resolved_path = raw.get("path", base.get("path"))
        if resolved_path is None:
            raise ValueError(
                "explicit_artifact_references must provide a path for "
                f"artifact_role_id {role_id!r}."
            )
        resolved_contract_version = raw.get(
            "contract_version",
            base.get("contract_version"),
        )
        if resolved_contract_version is None:
            resolved_contract_version = hook.get("required_contract_version")
        resolved_format = raw.get("format", base.get("format"))
        resolved_artifact_scope = raw.get(
            "artifact_scope",
            base.get("artifact_scope", hook.get("artifact_scope")),
        )
        merged[role_id] = build_artifact_reference(
            artifact_role_id=role_id,
            source_kind=str(
                raw.get("source_kind", base.get("source_kind", hook["source_kind"]))
            ),
            path=resolved_path,
            contract_version=resolved_contract_version,
            bundle_id=str(
                raw.get("bundle_id", base.get("bundle_id", f"explicit:{role_id}"))
            ),
            artifact_id=str(
                raw.get("artifact_id", base.get("artifact_id", hook["artifact_id"]))
            ),
            format=_optional_string(resolved_format),
            artifact_scope=_optional_string(resolved_artifact_scope),
            status=str(
                resolve_status(
                    role_id,
                    raw,
                    base,
                    hook,
                    str(Path(resolved_path).resolve()),
                )
            ),
        )
    return list(merged.values())


def artifact_hook_catalog_by_role(
    contract_metadata: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        str(item["artifact_role_id"]): dict(item)
        for item in contract_metadata["artifact_hook_catalog"]
    }


def validate_packaged_bundle_reference_alignment(
    *,
    surface_name: str,
    metadata: Mapping[str, Any],
    record: Mapping[str, Any],
    record_name: str,
) -> None:
    bundle_reference = record.get("bundle_reference")
    if not isinstance(bundle_reference, Mapping) or "bundle_id" not in bundle_reference:
        raise ValueError(
            f"{surface_name} {record_name} must include bundle_reference.bundle_id."
        )
    if str(metadata["bundle_id"]) != str(bundle_reference["bundle_id"]):
        raise ValueError(
            f"{surface_name} metadata and {record_name} must reference the same bundle_id."
        )


def validate_packaged_dashboard_bundle_alignment(
    *,
    metadata: Mapping[str, Any],
    payload: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    validate_packaged_bundle_reference_alignment(
        surface_name="dashboard_session",
        metadata=metadata,
        record=payload,
        record_name="payload",
    )
    validate_packaged_bundle_reference_alignment(
        surface_name="dashboard_session",
        metadata=metadata,
        record=state,
        record_name="state",
    )


def validate_packaged_showcase_bundle_alignment(
    *,
    metadata: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    validate_packaged_bundle_reference_alignment(
        surface_name="showcase_session",
        metadata=metadata,
        record=state,
        record_name="state",
    )


def _artifact_hooks_for_source_kind(
    contract_metadata: Mapping[str, Any],
    *,
    source_kind: str,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in contract_metadata["artifact_hook_catalog"]
        if str(item["source_kind"]) == str(source_kind)
    ]


def _artifact_catalog(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("metadata.artifacts must be a mapping.")
    return artifacts


def _artifact_record(
    artifacts: Mapping[str, Any],
    *,
    artifact_id: str,
    field_name: str,
) -> Mapping[str, Any]:
    artifact = artifacts.get(artifact_id)
    if not isinstance(artifact, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return artifact


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _status_value(artifact: Mapping[str, Any]) -> str:
    status = artifact.get("status")
    if status is None:
        raise ValueError("Packaged artifact metadata must include status.")
    return str(status)
