from fastapi.testclient import TestClient

from app.main import app
from app.management.service import ManagementService
from app.management.storage import ManagementStore
from tests.management_test_utils import (
    build_action_ack_headers,
    build_signed_management_frame,
    create_management_test_device,
    enroll_management_device,
    start_management_relay,
)
from tests.test_helpers import TEST_PASSWORD, patch_test_auth_service

client = TestClient(app)


def _patch_management(monkeypatch, *, db_path):
    management_service = ManagementService(store=ManagementStore(sqlite_db_path=db_path))
    monkeypatch.setattr("app.management.router.get_management_service", lambda: management_service)
    monkeypatch.setattr("app.management.service.get_management_service", lambda: management_service)
    return management_service


def _login_seed_super_admin() -> dict:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["user"]["role"] == "super_admin"
    if login_response.json()["must_change_password"]:
        change_response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "123456", "new_password": "newpass123"},
        )
        assert change_response.status_code == 200, change_response.text
    return client.get("/api/v1/auth/me").json()["user"]


def test_seed_admin_is_super_admin_and_user_is_blocked(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    _patch_management(monkeypatch, db_path=db_path)

    client.cookies.clear()
    user_response = client.post(
        "/api/v1/auth/register",
        json={"username": "normal-user", "password": TEST_PASSWORD},
    )
    assert user_response.status_code == 200, user_response.text
    assert user_response.json()["user"]["role"] == "user"

    client.post("/api/v1/auth/login", json={"username": "normal-user", "password": TEST_PASSWORD})
    blocked_response = client.get("/api/v1/management/audit-logs")
    assert blocked_response.status_code == 403

    client.cookies.clear()
    super_admin = _login_seed_super_admin()
    assert super_admin["role"] == "super_admin"


def test_super_admin_device_hello_and_replay_rejected(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    _patch_management(monkeypatch, db_path=db_path)

    client.cookies.clear()
    super_admin = _login_seed_super_admin()
    device = create_management_test_device("sa-device")
    enrolled = enroll_management_device(client, device=device, role_scope="super_admin", device_name="测试超级管理员设备")
    assert enrolled["approved_at"]

    frame = build_signed_management_frame(frame_type="SA_HELLO", user_id=super_admin["user_id"], device=device)
    hello_response = client.post("/api/v1/management/super-admin/hello", json=frame)
    assert hello_response.status_code == 200, hello_response.text
    assert hello_response.json()["frame_type"] == "SA_ACK"

    _patch_management(monkeypatch, db_path=db_path)
    replay_response = client.post("/api/v1/management/super-admin/hello", json=frame)
    assert replay_response.status_code == 409

    relay_response = client.get("/api/v1/management/relay/status")
    assert relay_response.status_code == 200
    assert relay_response.json()["super_admin_online"] is True


def test_super_admin_can_read_web_ssh_terminal_status_after_relay(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    _patch_management(monkeypatch, db_path=db_path)

    client.cookies.clear()
    super_admin = _login_seed_super_admin()
    device = create_management_test_device("sa-device")
    enroll_management_device(client, device=device, role_scope="super_admin", device_name="测试超级管理员设备")
    start_management_relay(client, user_id=super_admin["user_id"], role="super_admin", device=device)

    status_response = client.get("/api/v1/management/ssh-terminal/status")
    assert status_response.status_code == 200, status_response.text
    payload = status_response.json()
    assert isinstance(payload["enabled"], bool)
    assert payload["mode"] in {"disabled-placeholder", "pipe-proxy", "pty-proxy"}
    assert "command_preview" in payload


def test_admin_access_request_approval_enables_admin_hello(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    _patch_management(monkeypatch, db_path=db_path)

    client.cookies.clear()
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "pending-admin", "password": TEST_PASSWORD},
    )
    admin_user_id = register_response.json()["user"]["user_id"]
    auth_service.update_user(user_id=admin_user_id, role="admin", is_active=True)

    client.post("/api/v1/auth/login", json={"username": "pending-admin", "password": TEST_PASSWORD})
    blocked_admin_route = client.get("/api/v1/admin/users")
    assert blocked_admin_route.status_code == 403

    admin_device = create_management_test_device("admin-device")
    device_payload = {
        "device_id": admin_device.device_id,
        "device_name": "测试管理员设备",
        "mac_hint": "cc:dd",
        "device_public_key": admin_device.public_jwk,
        "fingerprint_hash": admin_device.fingerprint_hash,
    }
    request_response = client.post("/api/v1/management/admin-access/request", json=device_payload)
    assert request_response.status_code == 200, request_response.text
    request_id = request_response.json()["request"]["request_id"]

    client.cookies.clear()
    super_admin = _login_seed_super_admin()
    super_device = create_management_test_device("sa-device")
    enroll_management_device(client, device=super_device, role_scope="super_admin", device_name="测试超级管理员设备")
    start_management_relay(client, user_id=super_admin["user_id"], role="super_admin", device=super_device)
    approve_payload = {"decision_note": "测试通过"}
    approve_headers = build_action_ack_headers(
        client,
        device=super_device,
        action_type="ADMIN_ACCESS_APPROVE",
        target_type="admin_access_request",
        target_id=request_id,
        payload=approve_payload,
    )
    approve_response = client.post(
        f"/api/v1/management/admin-access/{request_id}/approve",
        json=approve_payload,
        headers=approve_headers,
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["request"]["status"] == "approved"

    replay_ack_response = client.post(
        f"/api/v1/management/admin-access/{request_id}/approve",
        json=approve_payload,
        headers=approve_headers,
    )
    assert replay_ack_response.status_code == 403

    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"username": "pending-admin", "password": TEST_PASSWORD})
    frame = build_signed_management_frame(frame_type="AD_HELLO", user_id=admin_user_id, device=admin_device)
    hello_response = client.post("/api/v1/management/admin/hello", json=frame)
    assert hello_response.status_code == 200, hello_response.text
    assert hello_response.json()["frame_type"] == "AD_ACK"
