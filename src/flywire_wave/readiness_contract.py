from __future__ import annotations

from collections.abc import Mapping
from typing import Any


OPERATOR_READINESS_GATE_KEY = "operator_readiness_gate"
OPERATOR_BUNDLE_READY_KEY = "operator_bundle_ready"
FOLLOW_ON_READINESS_KEY = "follow_on_readiness"
READY_FOR_FOLLOW_ON_WORK_KEY = "ready_for_follow_on_work"

LEGACY_OPERATOR_READINESS_GATE_KEY = "milestone10_gate"
LEGACY_OPERATOR_BUNDLE_READY_KEY = "milestone10_engine_ready"
LEGACY_FOLLOW_ON_READINESS_KEY = "milestone10_readiness"
LEGACY_READY_FOR_FOLLOW_ON_WORK_KEY = "ready_for_engine_work"

READINESS_GATE_GO = "go"
READINESS_GATE_REVIEW = "review"
READINESS_GATE_HOLD = "hold"


def resolve_operator_readiness_gate(payload: Mapping[str, Any] | None, *, default: str = "") -> str:
    if not isinstance(payload, Mapping):
        return str(default)
    if OPERATOR_READINESS_GATE_KEY in payload:
        return str(payload[OPERATOR_READINESS_GATE_KEY])
    return str(payload.get(LEGACY_OPERATOR_READINESS_GATE_KEY, default))


def resolve_operator_bundle_ready(payload: Mapping[str, Any] | None, *, default: bool = False) -> bool:
    if not isinstance(payload, Mapping):
        return bool(default)
    if OPERATOR_BUNDLE_READY_KEY in payload:
        return bool(payload[OPERATOR_BUNDLE_READY_KEY])
    return bool(payload.get(LEGACY_OPERATOR_BUNDLE_READY_KEY, default))


def resolve_follow_on_readiness(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    if isinstance(payload.get(FOLLOW_ON_READINESS_KEY), Mapping):
        return dict(payload[FOLLOW_ON_READINESS_KEY])
    if not isinstance(payload.get(LEGACY_FOLLOW_ON_READINESS_KEY), Mapping):
        return {}

    readiness = dict(payload[LEGACY_FOLLOW_ON_READINESS_KEY])
    if READY_FOR_FOLLOW_ON_WORK_KEY not in readiness and LEGACY_READY_FOR_FOLLOW_ON_WORK_KEY in readiness:
        readiness[READY_FOR_FOLLOW_ON_WORK_KEY] = bool(readiness[LEGACY_READY_FOR_FOLLOW_ON_WORK_KEY])
    return readiness


def build_follow_on_readiness(*, status: str, local_operator_gate: str) -> dict[str, Any]:
    return {
        "status": str(status),
        "local_operator_gate": str(local_operator_gate),
        READY_FOR_FOLLOW_ON_WORK_KEY: bool(str(status) != READINESS_GATE_HOLD),
    }
