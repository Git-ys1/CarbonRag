import json
from urllib.parse import urlparse

from fastapi import APIRouter, Cookie, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.auth.dependencies import (
    require_authenticated_user,
    require_management_action_ack,
    require_super_admin,
    require_super_admin_relay_ack,
)
from app.auth.schemas import AuthenticatedUser
from app.auth.service import get_auth_service
from app.management.schemas import (
    ActionAckEnvelope,
    ActionRequestCreate,
    AdminAccessDecisionRequest,
    AdminAccessRequestCreate,
    AdminAccessRequestEnvelope,
    AdminDeviceEnvelope,
    DeviceEnrollRequest,
    ManagementAck,
    ManagementFrame,
    ManagementListEnvelope,
    RelayHeartbeatRequest,
    RelayStatusResponse,
    ServerOpsRunRequest,
    ServerOpsRunResponse,
)
from app.management.server_ops import list_allowed_server_ops_commands, run_allowed_server_ops_command
from app.management.service import get_management_service
from app.management.ssh_terminal import get_terminal_status, run_terminal_session

router = APIRouter(prefix="/management")


@router.post("/device/enroll", response_model=AdminDeviceEnvelope)
def enroll_device(
    payload: DeviceEnrollRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AdminDeviceEnvelope:
    return get_management_service().enroll_device(current_user, payload)


@router.post("/super-admin/hello", response_model=ManagementAck)
def super_admin_hello(
    frame: ManagementFrame,
    current_user: AuthenticatedUser = Depends(require_super_admin),
) -> ManagementAck:
    return get_management_service().super_admin_hello(current_user, frame)


@router.post("/admin/hello", response_model=ManagementAck)
def admin_hello(
    frame: ManagementFrame,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> ManagementAck:
    return get_management_service().admin_hello(current_user, frame)


@router.post("/action/request", response_model=ActionAckEnvelope)
def request_action_ack(
    payload: ActionRequestCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> ActionAckEnvelope:
    return get_management_service().request_action_ack(current_user, payload)


@router.post("/action/ack", response_model=ActionAckEnvelope)
def create_action_ack(
    payload: ActionRequestCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> ActionAckEnvelope:
    return get_management_service().request_action_ack(current_user, payload)


@router.post("/admin-access/request", response_model=AdminAccessRequestEnvelope)
def request_admin_access(
    payload: AdminAccessRequestCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AdminAccessRequestEnvelope:
    return get_management_service().create_access_request(current_user, payload)


@router.post("/admin-access/{request_id}/approve", response_model=AdminAccessRequestEnvelope)
def approve_admin_access(
    request_id: str,
    payload: AdminAccessDecisionRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_ACCESS_APPROVE", "admin_access_request", target_param="request_id")),
) -> AdminAccessRequestEnvelope:
    return get_management_service().approve_access_request(current_user, request_id, payload)


@router.post("/admin-access/{request_id}/reject", response_model=AdminAccessRequestEnvelope)
def reject_admin_access(
    request_id: str,
    payload: AdminAccessDecisionRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_ACCESS_REJECT", "admin_access_request", target_param="request_id")),
) -> AdminAccessRequestEnvelope:
    return get_management_service().reject_access_request(current_user, request_id, payload)


@router.get("/relay/status", response_model=RelayStatusResponse)
def relay_status(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RelayStatusResponse:
    return get_management_service().relay_status(current_user)


@router.post("/relay/heartbeat", response_model=RelayStatusResponse)
def relay_heartbeat(
    payload: RelayHeartbeatRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RelayStatusResponse:
    return get_management_service().heartbeat(current_user, payload)


@router.get("/audit-logs", response_model=ManagementListEnvelope)
def audit_logs(
    current_user: AuthenticatedUser = Depends(require_super_admin_relay_ack),
) -> ManagementListEnvelope:
    logs = get_management_service().list_audit_logs(current_user)
    return ManagementListEnvelope(audit_logs=logs)


@router.get("/overview", response_model=ManagementListEnvelope)
def overview(
    current_user: AuthenticatedUser = Depends(require_super_admin_relay_ack),
) -> ManagementListEnvelope:
    return get_management_service().list_management(current_user)


@router.get("/ssh-terminal/status")
def ssh_terminal_status(
    current_user: AuthenticatedUser = Depends(require_super_admin_relay_ack),
) -> dict[str, bool | str | int]:
    del current_user
    return get_terminal_status()


@router.websocket("/ssh-terminal/ws")
async def ssh_terminal_ws(websocket: WebSocket, carbonrag_session: str | None = Cookie(default=None)) -> None:
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")
    if not _is_allowed_ws_origin(origin=origin, host=host):
        await websocket.close(code=1008)
        return

    user = get_auth_service().get_user_from_token(carbonrag_session)
    if user is None or user.role != "super_admin":
        await websocket.close(code=1008)
        return
    if not get_management_service().has_active_relay(user_id=user.user_id, role=user.role):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    get_management_service().record_audit(
        actor_user_id=user.user_id,
        actor_role=user.role,
        action_type="WEB_SSH_TERMINAL_OPEN",
        decision="allow",
        detail_json={"transport": "websocket"},
    )

    def audit_input(command: str) -> None:
        get_management_service().record_audit(
            actor_user_id=user.user_id,
            actor_role=user.role,
            action_type="WEB_SSH_TERMINAL_INPUT",
            target_type="terminal_command",
            decision="allow",
            detail_json={"command": command},
        )

    await run_terminal_session(websocket, audit_input=audit_input)
    get_management_service().record_audit(
        actor_user_id=user.user_id,
        actor_role=user.role,
        action_type="WEB_SSH_TERMINAL_CLOSE",
        decision="allow",
        detail_json={"transport": "websocket"},
    )


@router.get("/server-ops/commands")
def list_server_ops_commands(
    current_user: AuthenticatedUser = Depends(require_super_admin_relay_ack),
) -> dict[str, object]:
    del current_user
    return {"commands": list_allowed_server_ops_commands()}


@router.post("/server-ops/commands/{command_id}/run", response_model=ServerOpsRunResponse)
def run_server_ops_command(
    command_id: str,
    payload: ServerOpsRunRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("SERVER_OPS_RUN", "server_ops_command", target_param="command_id")),
) -> ServerOpsRunResponse:
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required.")
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Server ops command requires explicit confirmation.")
    result = run_allowed_server_ops_command(command_id)
    get_management_service().record_audit(
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
        action_type="SERVER_OPS_RUN",
        target_type="server_ops_command",
        target_id=command_id,
        decision="allow" if result.get("status") == "completed" else "deny",
        detail_json={
            "status": result.get("status"),
            "exit_code": result.get("exit_code"),
            "duration_ms": result.get("duration_ms"),
            "reason": payload.reason,
        },
    )
    return ServerOpsRunResponse.model_validate(result)


@router.get("/server-ops/history", response_model=ManagementListEnvelope)
def server_ops_history(
    current_user: AuthenticatedUser = Depends(require_super_admin_relay_ack),
) -> ManagementListEnvelope:
    logs = [
        item
        for item in get_management_service().list_audit_logs(current_user)
        if item.action_type.startswith("SERVER_OPS")
    ]
    return ManagementListEnvelope(audit_logs=logs)


@router.websocket("/relay/ws")
async def relay_ws(websocket: WebSocket, carbonrag_session: str | None = Cookie(default=None)) -> None:
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")
    if not _is_allowed_ws_origin(origin=origin, host=host):
        await websocket.close(code=1008)
        return

    user = get_auth_service().get_user_from_token(carbonrag_session)
    if user is None or user.role not in {"admin", "super_admin"}:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "role": user.role})
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8", "replace")) > 4096:
                await websocket.close(code=1009)
                return
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid relay message JSON."})
                continue
            if not isinstance(message, dict):
                await websocket.send_json({"type": "error", "detail": "Relay message must be an object."})
                continue
            if not get_management_service().has_active_relay(user_id=user.user_id, role=user.role):
                await websocket.close(code=1008)
                return
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "unsupported", "detail": "Relay message type is not allowed."})
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            return


def _is_allowed_ws_origin(*, origin: str, host: str) -> bool:
    if not origin:
        return False
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    origin_host = parsed.netloc
    if host and origin_host == host:
        return True
    return origin_host.startswith("localhost:") or origin_host.startswith("127.0.0.1:")
