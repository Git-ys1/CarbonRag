from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.management.service import ManagementService
from app.management.storage import ManagementStore
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


def _management_frame(*, frame_type: str, user_id: str, device_id: str, nonce: str | None = None) -> dict:
    return {
        "frame_type": frame_type,
        "protocol_version": "1.0",
        "user_id": user_id,
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": nonce or f"nonce-{uuid4().hex[:16]}",
        "payload_hash": "f" * 64,
        "signature": "signed-management-frame",
    }


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
    device_id = "sa-device-001"
    enroll_response = client.post(
        "/api/v1/management/device/enroll",
        json={
            "device_id": device_id,
            "role_scope": "super_admin",
            "device_name": "测试超级管理员设备",
            "mac_hint": "aa:bb",
            "device_public_key": "super-admin-public-key",
            "fingerprint_hash": "super-admin-fingerprint",
        },
    )
    assert enroll_response.status_code == 200, enroll_response.text
    assert enroll_response.json()["device"]["approved_at"]

    frame = _management_frame(frame_type="SA_HELLO", user_id=super_admin["user_id"], device_id=device_id)
    hello_response = client.post("/api/v1/management/super-admin/hello", json=frame)
    assert hello_response.status_code == 200, hello_response.text
    assert hello_response.json()["frame_type"] == "SA_ACK"

    replay_response = client.post("/api/v1/management/super-admin/hello", json=frame)
    assert replay_response.status_code == 409

    relay_response = client.get("/api/v1/management/relay/status")
    assert relay_response.status_code == 200
    assert relay_response.json()["super_admin_online"] is True


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

    device_payload = {
        "device_id": "admin-device-001",
        "device_name": "测试管理员设备",
        "mac_hint": "cc:dd",
        "device_public_key": "admin-public-key",
        "fingerprint_hash": "admin-device-fingerprint",
    }
    request_response = client.post("/api/v1/management/admin-access/request", json=device_payload)
    assert request_response.status_code == 200, request_response.text
    request_id = request_response.json()["request"]["request_id"]

    client.cookies.clear()
    _login_seed_super_admin()
    approve_response = client.post(
        f"/api/v1/management/admin-access/{request_id}/approve",
        json={"decision_note": "测试通过"},
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["request"]["status"] == "approved"

    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"username": "pending-admin", "password": TEST_PASSWORD})
    frame = _management_frame(frame_type="AD_HELLO", user_id=admin_user_id, device_id=device_payload["device_id"])
    hello_response = client.post("/api/v1/management/admin/hello", json=frame)
    assert hello_response.status_code == 200, hello_response.text
    assert hello_response.json()["frame_type"] == "AD_ACK"
