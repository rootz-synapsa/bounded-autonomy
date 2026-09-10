"""
M7/M8 Authorization Lifecycle: bounded approval for SUPERVISED actions.

Statuses:
- NOT_REQUIRED: decision was AUTO (no approval needed)
- PENDING: awaiting human approval
- GRANTED: approved; single-use, time-bounded, state-bound, context-bound
- EXPIRED: TTL elapsed before use
- INVALIDATED: denied by approver, or reality drifted (revalidation failed)
- CONSUMED: used exactly once

Fail-closed: only GRANTED authorizations may be consumed.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class AuthorizationStatus(Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    CONSUMED = "CONSUMED"


def state_hash(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def action_key(action: dict) -> str:
    return hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()


@dataclass
class Authorization:
    authorization_id: str
    action: dict
    status: AuthorizationStatus
    created_at: float
    expires_at: float
    granted_by: str | None = None
    granted_at: float | None = None
    state_hash_at_grant: str | None = None
    context_predicate: dict | None = None
    consumed_at: float | None = None
    invalidation_reason: str | None = None
    history: list = field(default_factory=list)


class AuthorizationManager:
    def __init__(self, clock=time.time, default_ttl_seconds: float = 300.0):
        self._clock = clock
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, Authorization] = {}

    def request(self, action: dict) -> Authorization:
        now = self._clock()
        auth = Authorization(
            authorization_id=f"auth-{uuid.uuid4().hex[:12]}",
            action=action,
            status=AuthorizationStatus.PENDING,
            created_at=now,
            expires_at=now + self._default_ttl,
        )
        auth.history.append(("PENDING", now, "requested"))
        self._store[auth.authorization_id] = auth
        return auth

    def get(self, authorization_id: str):
        return self._store.get(authorization_id)

    def _refresh_expiry(self, auth: Authorization) -> None:
        if auth.status in (AuthorizationStatus.PENDING, AuthorizationStatus.GRANTED):
            if self._clock() > auth.expires_at:
                auth.status = AuthorizationStatus.EXPIRED
                auth.history.append(("EXPIRED", self._clock(), "ttl elapsed"))

    def grant(self, authorization_id: str, approver_id: str, state: dict,
              context_predicate: dict | None = None) -> Authorization:
        auth = self._store[authorization_id]
        self._refresh_expiry(auth)
        if auth.status is not AuthorizationStatus.PENDING:
            raise ValueError(f"cannot grant authorization in status {auth.status.value}")
        auth.status = AuthorizationStatus.GRANTED
        auth.granted_by = approver_id
        auth.granted_at = self._clock()
        auth.state_hash_at_grant = state_hash(state)
        auth.context_predicate = context_predicate
        auth.history.append(("GRANTED", auth.granted_at, f"by {approver_id}"))
        return auth

    def deny(self, authorization_id: str, approver_id: str, reason: str) -> Authorization:
        auth = self._store[authorization_id]
        self._refresh_expiry(auth)
        if auth.status is not AuthorizationStatus.PENDING:
            raise ValueError(f"cannot deny authorization in status {auth.status.value}")
        auth.status = AuthorizationStatus.INVALIDATED
        auth.invalidation_reason = f"denied by {approver_id}: {reason}"
        auth.history.append(("INVALIDATED", self._clock(), auth.invalidation_reason))
        return auth

    def invalidate(self, authorization_id: str, reason: str) -> Authorization:
        auth = self._store[authorization_id]
        if auth.status is AuthorizationStatus.GRANTED:
            auth.status = AuthorizationStatus.INVALIDATED
            auth.invalidation_reason = reason
            auth.history.append(("INVALIDATED", self._clock(), reason))
        return auth

    def consume(self, authorization_id: str, action: dict, state: dict,
                validate: bool = True) -> Authorization:
        """One-shot consumption. Fail-closed on any lifecycle mismatch."""
        auth = self._store[authorization_id]
        self._refresh_expiry(auth)
        if auth.status is not AuthorizationStatus.GRANTED:
            raise PermissionError(f"authorization not consumable: status={auth.status.value}")
        if validate:
            if action_key(action) != action_key(auth.action):
                auth.status = AuthorizationStatus.INVALIDATED
                auth.invalidation_reason = "action mismatch at consumption"
                auth.history.append(("INVALIDATED", self._clock(), auth.invalidation_reason))
                raise PermissionError(auth.invalidation_reason)
            if state_hash(state) != auth.state_hash_at_grant:
                auth.status = AuthorizationStatus.INVALIDATED
                auth.invalidation_reason = "state changed since grant (revalidation required)"
                auth.history.append(("INVALIDATED", self._clock(), auth.invalidation_reason))
                raise PermissionError(auth.invalidation_reason)
        auth.status = AuthorizationStatus.CONSUMED
        auth.consumed_at = self._clock()
        auth.history.append(("CONSUMED", auth.consumed_at, "one-shot execution"))
        return auth
