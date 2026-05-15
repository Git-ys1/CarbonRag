from fastapi import APIRouter, Cookie, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.auth.dependencies import require_authenticated_user, require_super_admin
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
)
from app.management.service import get_management_service
from app.management.ssh_terminal import get_terminal_status

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
    current_user: AuthenticatedUser = Depends(require_super_admin),
) -> AdminAccessRequestEnvelope:
    return get_management_service().approve_access_request(current_user, request_id, payload)


@router.post("/admin-access/{request_id}/reject", response_model=AdminAccessRequestEnvelope)
def reject_admin_access(
    request_id: str,
    payload: AdminAccessDecisionRequest,
    current_user: AuthenticatedUser = Depends(require_super_admin),
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
    current_user: AuthenticatedUser = Depends(require_super_admin),
) -> ManagementListEnvelope:
    logs = get_management_service().list_audit_logs(current_user)
    return ManagementListEnvelope(audit_logs=logs)


@router.get("/overview", response_model=ManagementListEnvelope)
def overview(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> ManagementListEnvelope:
    return get_management_service().list_management(current_user)


@router.get("/ssh-terminal/status")
def ssh_terminal_status(
    current_user: AuthenticatedUser = Depends(require_super_admin),
) -> dict[str, bool | str]:
    del current_user
    return get_terminal_status()


@router.websocket("/relay/ws")
async def relay_ws(websocket: WebSocket, carbonrag_session: str | None = Cookie(default=None)) -> None:
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")
    if origin and host and host not in origin:
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
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "unsupported", "detail": "relay ws skeleton only"})
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            return
