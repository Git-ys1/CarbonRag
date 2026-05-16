from collections.abc import Callable
import json

from fastapi import Cookie, Depends, Header, HTTPException, Request

from app.auth.schemas import AuthenticatedUser
from app.auth.service import get_auth_service


def _load_user_from_cookie(carbonrag_session: str | None = Cookie(default=None)) -> AuthenticatedUser | None:
    if not carbonrag_session:
        return None
    return get_auth_service().get_user_from_token(carbonrag_session)


def require_authenticated_user(user: AuthenticatedUser | None = Depends(_load_user_from_cookie)) -> AuthenticatedUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if user.password_must_change:
        raise HTTPException(status_code=403, detail="Password change required.")
    return user


def get_current_user(user: AuthenticatedUser | None = Depends(_load_user_from_cookie)) -> AuthenticatedUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def require_admin(user: AuthenticatedUser = Depends(require_authenticated_user)) -> AuthenticatedUser:
    if user.role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def require_super_admin(user: AuthenticatedUser = Depends(require_authenticated_user)) -> AuthenticatedUser:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required.")
    return user


def require_admin_relay_ack(user: AuthenticatedUser = Depends(require_admin)) -> AuthenticatedUser:
    return require_management_active_relay(user)


def require_management_active_relay(user: AuthenticatedUser = Depends(require_admin)) -> AuthenticatedUser:
    from app.management.service import get_management_service

    if not get_management_service().has_active_relay(user_id=user.user_id, role=user.role):
        raise HTTPException(status_code=403, detail="Active management relay required.")
    return user


def require_super_admin_relay_ack(user: AuthenticatedUser = Depends(require_super_admin)) -> AuthenticatedUser:
    from app.management.service import get_management_service

    if not get_management_service().has_active_relay(user_id=user.user_id, role=user.role):
        raise HTTPException(status_code=403, detail="Active super admin relay required.")
    return user


def require_management_action_ack(
    action_type: str,
    target_type: str,
    *,
    target_param: str | None = None,
    default_target_id: str | None = None,
) -> Callable[..., AuthenticatedUser]:
    async def _dependency(
        request: Request,
        user: AuthenticatedUser = Depends(require_management_active_relay),
        action_request_id: str | None = Header(default=None, alias="X-Management-Action-Request-Id"),
        payload_hash: str | None = Header(default=None, alias="X-Management-Payload-Hash"),
    ) -> AuthenticatedUser:
        if not action_request_id or not payload_hash:
            raise HTTPException(status_code=403, detail="Management ACTION_ACK headers are required.")
        actual_payload_hash = await _hash_request_payload(request)
        if actual_payload_hash != payload_hash:
            raise HTTPException(status_code=403, detail="Management ACTION_ACK payload hash mismatch.")
        target_id = default_target_id
        if target_param:
            target_id = str(request.path_params.get(target_param) or "")
        from app.management.service import get_management_service

        consumed = get_management_service().consume_action_ack(
            user_id=user.user_id,
            role=user.role,
            action_request_id=action_request_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            payload_hash=payload_hash,
        )
        if not consumed:
            raise HTTPException(status_code=403, detail="Valid one-time management ACTION_ACK required.")
        return user

    return _dependency


async def _hash_request_payload(request: Request) -> str:
    from app.management.protocol import canonical_json, sha256_text

    body = await request.body()
    if not body:
        return sha256_text(canonical_json({}))
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Management ACTION_ACK payload must be valid JSON.") from exc
    return sha256_text(canonical_json(payload))
