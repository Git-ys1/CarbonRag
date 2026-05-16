from fastapi.testclient import TestClient

from app.main import app
from app.session.adapters.sqlite_store import SQLiteSessionStore
from app.session.service import SessionService
from tests.test_helpers import TEST_PASSWORD, patch_test_auth_service

client = TestClient(app)


def build_session_service(tmp_path) -> SessionService:
    store = SQLiteSessionStore(tmp_path / "carbonrag.sqlite3")
    return SessionService(store=store)


def test_auth_register_login_logout_and_me(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/system/info").status_code == 401

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "trial_user", "password": TEST_PASSWORD},
    )
    assert register_response.status_code == 200
    assert register_response.json()["user"]["role"] == "user"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "trial_user", "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is False

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "trial_user"

    create_session_response = client.post("/api/v1/sessions", json={})
    assert create_session_response.status_code == 200

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_self_account_delete_requires_current_password(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    client.cookies.clear()
    client.post(
        "/api/v1/auth/register",
        json={"username": "delete_me_user", "password": TEST_PASSWORD},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "delete_me_user", "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200

    wrong_password_response = client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"current_password": "wrongpass123"},
    )
    assert wrong_password_response.status_code == 422
    assert client.get("/api/v1/auth/me").status_code == 200

    delete_response = client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"current_password": TEST_PASSWORD},
    )
    assert delete_response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401

    relogin_response = client.post(
        "/api/v1/auth/login",
        json={"username": "delete_me_user", "password": TEST_PASSWORD},
    )
    assert relogin_response.status_code == 401


def test_seed_admin_must_change_password_before_access(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    auth_service = patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")
    auth_service.ensure_seed_admin_and_backfill()

    client.cookies.clear()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True

    blocked_response = client.get("/api/v1/sessions")
    assert blocked_response.status_code == 403

    change_response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "123456", "new_password": "newpass123"},
    )
    assert change_response.status_code == 200
    assert change_response.json()["must_change_password"] is False

    sessions_response = client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    system_response = client.get("/api/v1/system/info")
    assert system_response.status_code == 200


def test_register_admin_with_seed_password_recovers_missing_seed_admin(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    auth_service = patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")
    auth_service.ensure_seed_admin_and_backfill()

    with auth_service._connect() as connection:  # noqa: SLF001 - test recovery path against actual runtime store
        connection.execute("DELETE FROM auth_sessions")
        connection.execute("DELETE FROM users WHERE username = ?", ("admin",))

    client.cookies.clear()
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "admin", "password": "123456"},
    )
    assert register_response.status_code == 200
    recovered_user = register_response.json()["user"]
    assert recovered_user["username"] == "admin"
    assert recovered_user["role"] == "super_admin"
    assert recovered_user["password_must_change"] is True

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True


def test_register_admin_with_seed_password_recovers_existing_broken_admin(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    auth_service = patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")
    seed_admin = auth_service.ensure_seed_admin_and_backfill()
    with auth_service._connect() as connection:  # noqa: SLF001 - simulate a corrupted bootstrap row
        connection.execute(
            "UPDATE users SET role = ?, is_active = ?, password_must_change = ? WHERE user_id = ?",
            ("user", 0, 0, seed_admin.user_id),
        )

    client.cookies.clear()
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "admin", "password": "123456"},
    )
    assert register_response.status_code == 200
    recovered_user = register_response.json()["user"]
    assert recovered_user["role"] == "super_admin"
    assert recovered_user["is_active"] is True
    assert recovered_user["password_must_change"] is True

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True


def test_seed_admin_login_repairs_demoted_runtime_row(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    auth_service = patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")
    seed_admin = auth_service.ensure_seed_admin_and_backfill()
    with auth_service._connect() as connection:  # noqa: SLF001 - simulate stale runtime data after a bad merge
        connection.execute(
            "UPDATE users SET role = ?, is_active = ?, password_must_change = ? WHERE user_id = ?",
            ("user", 1, 1, seed_admin.user_id),
        )

    client.cookies.clear()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["user"]["role"] == "super_admin"
    assert login_response.json()["must_change_password"] is True


def test_seed_admin_me_repairs_demoted_runtime_row(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    auth_service = patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    client.cookies.clear()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200, login_response.text
    with auth_service._connect() as connection:  # noqa: SLF001 - existing browser session sees stale role until /me repairs
        connection.execute("UPDATE users SET role = ? WHERE username = ?", ("user", "admin"))

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["user"]["role"] == "super_admin"


def test_seed_admin_backfill_allows_two_active_super_admins_temporarily(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    auth_service = patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")
    auth_service.ensure_seed_admin_and_backfill()

    second_super = auth_service.register({"username": "second-super", "password": TEST_PASSWORD})
    third_super = auth_service.register({"username": "third-super", "password": TEST_PASSWORD})
    with auth_service._connect() as connection:  # noqa: SLF001 - test temporary bootstrap repair cap
        connection.execute(
            "UPDATE users SET role = ? WHERE user_id IN (?, ?)",
            ("super_admin", second_super.user_id, third_super.user_id),
        )

    auth_service.ensure_seed_admin_and_backfill()
    with auth_service._connect() as connection:  # noqa: SLF001 - assert persisted repair result
        rows = connection.execute(
            "SELECT username, role FROM users WHERE username IN (?, ?, ?) ORDER BY username",
            ("admin", "second-super", "third-super"),
        ).fetchall()
    role_by_username = {row["username"]: row["role"] for row in rows}
    assert role_by_username["admin"] == "super_admin"
    assert role_by_username["second-super"] == "super_admin"
    assert role_by_username["third-super"] == "admin"


def test_register_admin_with_non_seed_password_is_rejected(monkeypatch, tmp_path) -> None:
    session_service = build_session_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    client.cookies.clear()
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "admin", "password": "otherpass123"},
    )
    assert register_response.status_code == 422
    assert "admin / 123456" in register_response.json()["detail"]
