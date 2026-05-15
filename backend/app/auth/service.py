import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.auth.schemas import (
    AuthLoginResult,
    AuthSessionCookie,
    AuthenticatedUser,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserRole,
)
from app.core.config import get_settings
from app.runtime_db.compat import connect_postgres
from app.runtime_db.bootstrap import bootstrap_runtime_database, get_runtime_backend_kind
from app.session.store import DEFAULT_SESSION_DB_PATH

SEED_ADMIN_USERNAME = "admin"
SEED_ADMIN_PASSWORD = "123456"


class AuthenticationError(ValueError):
    pass


class InactiveUserError(PermissionError):
    pass


class PasswordChangeRequiredError(PermissionError):
    pass


class UserAlreadyExistsError(ValueError):
    pass


class ReservedUsernameError(ValueError):
    pass


class ProtectedAccountDeletionError(ValueError):
    pass


class AuthService:
    def __init__(
        self,
        *,
        database_url: str | None = None,
        sqlite_db_path: Path | str | None = None,
    ) -> None:
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.sqlite_db_path = Path(sqlite_db_path or DEFAULT_SESSION_DB_PATH)
        self.backend_kind = get_runtime_backend_kind(self.database_url)
        self.cookie = AuthSessionCookie()
        self.password_hasher = PasswordHasher()
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_runtime_database(
            database_url=self.database_url,
            sqlite_db_path=self.sqlite_db_path,
        )
        self.ensure_seed_admin_and_backfill()

    def _connect(self):
        if self.backend_kind == "postgresql":
            return connect_postgres(self.database_url)

        connection = sqlite3.connect(self.sqlite_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_user(row) -> AuthenticatedUser:
        payload = dict(row)
        payload["is_active"] = bool(payload["is_active"])
        payload["password_must_change"] = bool(payload["password_must_change"])
        payload["display_name"] = payload.get("display_name") or AuthService._default_display_name(
            role=str(payload.get("role") or "user"),
            user_id=str(payload.get("user_id") or ""),
        )
        return AuthenticatedUser.model_validate(payload)

    @staticmethod
    def _default_display_name(*, role: str, user_id: str) -> str:
        role_label = {"super_admin": "超级管理员", "admin": "管理员"}.get(role, "用户")
        numeric = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8], 16) % 1_000_000
        return f"{role_label}{numeric:06d}"

    def _fetch_user_by_username(self, username: str):
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            user_id, username, display_name, avatar_url, password_hash, role, is_active,
                            password_must_change, created_at, updated_at, last_login_at
                        FROM users
                        WHERE username = %s
                        """,
                        (username,),
                    )
                    return cursor.fetchone()

            return connection.execute(
                """
                SELECT
                    user_id, username, display_name, avatar_url, password_hash, role, is_active,
                    password_must_change, created_at, updated_at, last_login_at
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

    def _fetch_user_by_id(self, user_id: str):
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            user_id, username, display_name, avatar_url, password_hash, role, is_active,
                            password_must_change, created_at, updated_at, last_login_at
                        FROM users
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                    return cursor.fetchone()

            return connection.execute(
                """
                SELECT
                    user_id, username, display_name, avatar_url, password_hash, role, is_active,
                    password_must_change, created_at, updated_at, last_login_at
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

    def _fetch_user_by_display_name(self, display_name: str):
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            user_id, username, display_name, avatar_url, password_hash, role, is_active,
                            password_must_change, created_at, updated_at, last_login_at
                        FROM users
                        WHERE display_name = %s
                        """,
                        (display_name,),
                    )
                    return cursor.fetchone()

            return connection.execute(
                """
                SELECT
                    user_id, username, display_name, avatar_url, password_hash, role, is_active,
                    password_must_change, created_at, updated_at, last_login_at
                FROM users
                WHERE display_name = ?
                """,
                (display_name,),
            ).fetchone()

    def ensure_seed_admin_and_backfill(self) -> AuthenticatedUser:
        seed_row = self._fetch_user_by_username(SEED_ADMIN_USERNAME)
        if seed_row is None:
            self._create_seed_admin()
            seed_row = self._fetch_user_by_username(SEED_ADMIN_USERNAME)

        if seed_row is None:
            raise RuntimeError("Seed admin could not be created.")

        seed_user = self._row_to_user(seed_row)
        if seed_user.role != "super_admin":
            self._promote_seed_super_admin(seed_user.user_id)
            seed_row = self._fetch_user_by_id(seed_user.user_id)
            if seed_row is None:
                raise RuntimeError("Seed super admin could not be reloaded.")
            seed_user = self._row_to_user(seed_row)
        self._enforce_single_super_admin(seed_user.user_id)
        self._backfill_owner_fields(seed_user.user_id)
        return seed_user

    def _promote_seed_super_admin(self, user_id: str) -> None:
        updated_at = self._utcnow().isoformat()
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE users SET role = %s, updated_at = %s WHERE user_id = %s",
                        ("super_admin", updated_at, user_id),
                    )
            else:
                connection.execute(
                    "UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?",
                    ("super_admin", updated_at, user_id),
                )

    def _enforce_single_super_admin(self, seed_user_id: str) -> None:
        updated_at = self._utcnow().isoformat()
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET role = %s, updated_at = %s
                        WHERE role = %s AND user_id <> %s
                        """,
                        ("admin", updated_at, "super_admin", seed_user_id),
                    )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET role = ?, updated_at = ?
                    WHERE role = ? AND user_id <> ?
                    """,
                    ("admin", updated_at, "super_admin", seed_user_id),
                )

    def _create_seed_admin(self) -> None:
        created_at = self._utcnow().isoformat()
        user_id = f"user-{uuid4().hex[:12]}"
        password_hash = self.password_hasher.hash(SEED_ADMIN_PASSWORD)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (
                            user_id,
                            username,
                            display_name,
                            avatar_url,
                            password_hash,
                            role,
                            is_active,
                            password_must_change,
                            created_at,
                            updated_at,
                            last_login_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                        """,
                        (
                            user_id,
                            SEED_ADMIN_USERNAME,
                            SEED_ADMIN_USERNAME,
                            None,
                            password_hash,
                            "super_admin",
                            True,
                            True,
                            created_at,
                            created_at,
                        ),
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        username,
                        display_name,
                        avatar_url,
                        password_hash,
                        role,
                        is_active,
                        password_must_change,
                        created_at,
                        updated_at,
                        last_login_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        user_id,
                        SEED_ADMIN_USERNAME,
                        SEED_ADMIN_USERNAME,
                        None,
                        password_hash,
                        "super_admin",
                        1,
                        1,
                        created_at,
                        created_at,
                    ),
                )

    def recover_seed_admin(self) -> AuthenticatedUser:
        existing_row = self._fetch_user_by_username(SEED_ADMIN_USERNAME)
        if existing_row is None:
            self._create_seed_admin()
            recovered_row = self._fetch_user_by_username(SEED_ADMIN_USERNAME)
            if recovered_row is None:
                raise RuntimeError("Seed admin could not be recovered.")
            recovered_user = self._row_to_user(recovered_row)
            self._backfill_owner_fields(recovered_user.user_id)
            return recovered_user

        updated_at = self._utcnow().isoformat()
        password_hash = self.password_hasher.hash(SEED_ADMIN_PASSWORD)
        user_id = existing_row["user_id"]
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET password_hash = %s,
                            role = %s,
                            is_active = %s,
                            password_must_change = %s,
                            updated_at = %s
                        WHERE user_id = %s
                        """,
                        (password_hash, "super_admin", True, True, updated_at, user_id),
                    )
                    cursor.execute("DELETE FROM auth_sessions WHERE user_id = %s", (user_id,))
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?,
                        role = ?,
                        is_active = ?,
                        password_must_change = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (password_hash, "super_admin", 1, 1, updated_at, user_id),
                )
                connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))

        recovered_row = self._fetch_user_by_id(user_id)
        if recovered_row is None:
            raise RuntimeError("Recovered seed admin could not be reloaded.")
        recovered_user = self._row_to_user(recovered_row)
        self._backfill_owner_fields(recovered_user.user_id)
        return recovered_user

    def _backfill_owner_fields(self, owner_user_id: str) -> None:
        statements = {
            "postgresql": (
                "UPDATE sessions SET owner_user_id = %s WHERE owner_user_id IS NULL",
                "UPDATE files SET owner_user_id = %s WHERE owner_user_id IS NULL",
                "UPDATE feedback_entries SET owner_user_id = %s WHERE owner_user_id IS NULL",
                "UPDATE carbon_calculations SET owner_user_id = %s WHERE owner_user_id IS NULL",
                "UPDATE reports SET owner_user_id = %s WHERE owner_user_id IS NULL",
            ),
            "sqlite": (
                "UPDATE sessions SET owner_user_id = ? WHERE owner_user_id IS NULL",
                "UPDATE files SET owner_user_id = ? WHERE owner_user_id IS NULL",
                "UPDATE feedback_entries SET owner_user_id = ? WHERE owner_user_id IS NULL",
                "UPDATE carbon_calculations SET owner_user_id = ? WHERE owner_user_id IS NULL",
                "UPDATE reports SET owner_user_id = ? WHERE owner_user_id IS NULL",
            ),
        }
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    for statement in statements["postgresql"]:
                        cursor.execute(statement, (owner_user_id,))
            else:
                for statement in statements["sqlite"]:
                    connection.execute(statement, (owner_user_id,))

    def register(self, payload: RegisterRequest | dict) -> AuthenticatedUser:
        request = payload if isinstance(payload, RegisterRequest) else RegisterRequest.model_validate(payload)
        if request.username == SEED_ADMIN_USERNAME:
            if request.password != SEED_ADMIN_PASSWORD:
                raise ReservedUsernameError(
                    "用户名 admin 为系统保留账号；如需恢复初始管理员，请在注册页使用 admin / 123456。"
                )
            return self.recover_seed_admin()

        if self._fetch_user_by_username(request.username) is not None:
            raise UserAlreadyExistsError("username already exists.")

        created_at = self._utcnow().isoformat()
        user_id = f"user-{uuid4().hex[:12]}"
        display_name = request.display_name or self._default_display_name(role="user", user_id=user_id)
        existing_display_name = self._fetch_user_by_display_name(display_name)
        if existing_display_name is not None:
            raise UserAlreadyExistsError("display name already exists.")
        password_hash = self.password_hasher.hash(request.password)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (
                            user_id,
                            username,
                            display_name,
                            avatar_url,
                            password_hash,
                            role,
                            is_active,
                            password_must_change,
                            created_at,
                            updated_at,
                            last_login_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                        """,
                        (
                            user_id,
                            request.username,
                            display_name,
                            None,
                            password_hash,
                            "user",
                            True,
                            False,
                            created_at,
                            created_at,
                        ),
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        username,
                        display_name,
                        avatar_url,
                        password_hash,
                        role,
                        is_active,
                        password_must_change,
                        created_at,
                        updated_at,
                        last_login_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        user_id,
                        request.username,
                        display_name,
                        None,
                        password_hash,
                        "user",
                        1,
                        0,
                        created_at,
                        created_at,
                    ),
                )

        row = self._fetch_user_by_id(user_id)
        if row is None:
            raise RuntimeError("Registered user could not be reloaded.")
        return self._row_to_user(row)

    def login(self, payload: LoginRequest | dict) -> AuthLoginResult:
        request = payload if isinstance(payload, LoginRequest) else LoginRequest.model_validate(payload)
        row = self._fetch_user_by_username(request.username)
        if row is None:
            raise AuthenticationError("Invalid username or password.")

        try:
            self.password_hasher.verify(row["password_hash"], request.password)
        except (VerifyMismatchError, InvalidHashError) as exc:
            raise AuthenticationError("Invalid username or password.") from exc

        user = self._row_to_user(row)
        if not user.is_active:
            raise InactiveUserError("This account has been disabled.")

        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        created_at = self._utcnow()
        expires_at = created_at + timedelta(days=7)
        auth_session_id = f"auth-{uuid4().hex[:12]}"

        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO auth_sessions (
                            auth_session_id,
                            user_id,
                            token_hash,
                            created_at,
                            expires_at,
                            last_seen_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            auth_session_id,
                            user.user_id,
                            token_hash,
                            created_at.isoformat(),
                            expires_at.isoformat(),
                            created_at.isoformat(),
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE users
                        SET last_login_at = %s, updated_at = %s
                        WHERE user_id = %s
                        """,
                        (created_at.isoformat(), created_at.isoformat(), user.user_id),
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO auth_sessions (
                        auth_session_id,
                        user_id,
                        token_hash,
                        created_at,
                        expires_at,
                        last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        auth_session_id,
                        user.user_id,
                        token_hash,
                        created_at.isoformat(),
                        expires_at.isoformat(),
                        created_at.isoformat(),
                    ),
                )
                connection.execute(
                    """
                    UPDATE users
                    SET last_login_at = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (created_at.isoformat(), created_at.isoformat(), user.user_id),
                )

        refreshed = self._fetch_user_by_id(user.user_id)
        if refreshed is None:
            raise RuntimeError("Logged-in user could not be reloaded.")
        return AuthLoginResult(
            user=self._row_to_user(refreshed),
            raw_token=raw_token,
            expires_at=expires_at,
        )

    def get_user_from_token(self, raw_token: str | None) -> AuthenticatedUser | None:
        if not raw_token:
            return None

        token_hash = self._hash_token(raw_token)
        now = self._utcnow()
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            u.user_id,
                            u.username,
                            u.display_name,
                            u.avatar_url,
                            u.role,
                            u.is_active,
                            u.password_must_change,
                            u.created_at,
                            u.updated_at,
                            u.last_login_at
                        FROM auth_sessions s
                        JOIN users u ON u.user_id = s.user_id
                        WHERE s.token_hash = %s
                          AND s.expires_at > %s
                        """,
                        (token_hash, now.isoformat()),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        cursor.execute(
                            "UPDATE auth_sessions SET last_seen_at = %s WHERE token_hash = %s",
                            (now.isoformat(), token_hash),
                        )
            else:
                row = connection.execute(
                    """
                    SELECT
                        u.user_id,
                        u.username,
                        u.display_name,
                        u.avatar_url,
                        u.role,
                        u.is_active,
                        u.password_must_change,
                        u.created_at,
                        u.updated_at,
                        u.last_login_at
                    FROM auth_sessions s
                    JOIN users u ON u.user_id = s.user_id
                    WHERE s.token_hash = ?
                      AND s.expires_at > ?
                    """,
                    (token_hash, now.isoformat()),
                ).fetchone()
                if row is not None:
                    connection.execute(
                        "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
                        (now.isoformat(), token_hash),
                    )

        if row is None:
            return None
        return self._row_to_user(row)

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return

        token_hash = self._hash_token(raw_token)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (token_hash,))
            else:
                connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))

    def change_password(self, *, user_id: str, current_password: str, new_password: str) -> AuthenticatedUser:
        row = self._fetch_user_by_id(user_id)
        if row is None:
            raise KeyError(user_id)
        self._verify_user_password(row, current_password)

        updated_at = self._utcnow().isoformat()
        password_hash = self.password_hasher.hash(new_password)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET password_hash = %s,
                            password_must_change = %s,
                            updated_at = %s
                        WHERE user_id = %s
                        """,
                        (password_hash, False, updated_at, user_id),
                    )
                    cursor.execute("DELETE FROM auth_sessions WHERE user_id = %s", (user_id,))
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?,
                        password_must_change = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (password_hash, 0, updated_at, user_id),
                )
                connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))

        refreshed = self._fetch_user_by_id(user_id)
        if refreshed is None:
            raise RuntimeError("Changed-password user could not be reloaded.")
        return self._row_to_user(refreshed)

    def _verify_user_password(self, row, current_password: str) -> None:
        try:
            self.password_hasher.verify(row["password_hash"], current_password)
        except (VerifyMismatchError, InvalidHashError) as exc:
            raise AuthenticationError("Current password is incorrect.") from exc

    def delete_non_admin_users(
        self,
        *,
        actor_user_id: str,
        current_password: str,
        target_user_ids: list[str],
    ) -> list[str]:
        actor_row = self._fetch_user_by_id(actor_user_id)
        if actor_row is None:
            raise KeyError(actor_user_id)
        self._verify_user_password(actor_row, current_password)

        deduped_target_ids = list(dict.fromkeys(target_user_ids))
        if not deduped_target_ids:
            raise ProtectedAccountDeletionError("No users selected for deletion.")
        if actor_user_id in deduped_target_ids:
            raise ProtectedAccountDeletionError("Cannot delete the current account from admin user management.")

        target_rows = []
        missing_ids: list[str] = []
        for user_id in deduped_target_ids:
            row = self._fetch_user_by_id(user_id)
            if row is None:
                missing_ids.append(user_id)
            else:
                target_rows.append(row)
        if missing_ids:
            raise KeyError(", ".join(missing_ids))

        protected = [row["username"] for row in target_rows if row["role"] in {"admin", "super_admin"}]
        if protected:
            raise ProtectedAccountDeletionError("Cannot delete administrator accounts.")

        self._delete_user_rows(deduped_target_ids)
        return deduped_target_ids

    def delete_own_account(self, *, user_id: str, current_password: str) -> str:
        row = self._fetch_user_by_id(user_id)
        if row is None:
            raise KeyError(user_id)
        self._verify_user_password(row, current_password)
        self._delete_user_rows([user_id])
        return user_id

    def _delete_user_rows(self, user_ids: list[str]) -> None:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    for user_id in user_ids:
                        cursor.execute("DELETE FROM auth_sessions WHERE user_id = %s", (user_id,))
                        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            else:
                for user_id in user_ids:
                    connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
                    connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    def update_profile(self, *, user_id: str, payload: UpdateProfileRequest | dict) -> AuthenticatedUser:
        request = payload if isinstance(payload, UpdateProfileRequest) else UpdateProfileRequest.model_validate(payload)
        current_row = self._fetch_user_by_id(user_id)
        if current_row is None:
            raise KeyError(user_id)
        current_payload = dict(current_row)

        fields_set = request.model_fields_set
        next_display_name = (
            request.display_name
            if "display_name" in fields_set
            else current_payload.get("display_name")
        )
        if next_display_name:
            existing = self._fetch_user_by_display_name(next_display_name)
            if existing is not None and existing["user_id"] != user_id:
                raise UserAlreadyExistsError("display name already exists.")

        next_avatar_url = request.avatar_url if "avatar_url" in fields_set else current_payload.get("avatar_url")
        updated_at = self._utcnow().isoformat()
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET display_name = %s,
                            avatar_url = %s,
                            updated_at = %s
                        WHERE user_id = %s
                        """,
                        (next_display_name, next_avatar_url, updated_at, user_id),
                    )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET display_name = ?,
                        avatar_url = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (next_display_name, next_avatar_url, updated_at, user_id),
                )

        refreshed = self._fetch_user_by_id(user_id)
        if refreshed is None:
            raise RuntimeError("Updated user profile could not be reloaded.")
        return self._row_to_user(refreshed)

    def update_user(self, *, user_id: str, role: UserRole, is_active: bool) -> AuthenticatedUser:
        if role == "super_admin":
            raise ProtectedAccountDeletionError("super_admin role can only be managed by the protected bootstrap flow.")
        current_row = self._fetch_user_by_id(user_id)
        if current_row is None:
            raise KeyError(user_id)
        current_user = self._row_to_user(current_row)
        if current_user.role == "super_admin":
            raise ProtectedAccountDeletionError("super_admin account can only be managed by the protected bootstrap flow.")
        updated_at = self._utcnow().isoformat()
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET role = %s,
                            is_active = %s,
                            updated_at = %s
                        WHERE user_id = %s
                        """,
                        (role, is_active, updated_at, user_id),
                    )
                    if cursor.rowcount == 0:
                        raise KeyError(user_id)
                    if not is_active:
                        cursor.execute("DELETE FROM auth_sessions WHERE user_id = %s", (user_id,))
            else:
                cursor = connection.execute(
                    """
                    UPDATE users
                    SET role = ?,
                        is_active = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (role, int(is_active), updated_at, user_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(user_id)
                if not is_active:
                    connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))

        refreshed = self._fetch_user_by_id(user_id)
        if refreshed is None:
            raise KeyError(user_id)
        return self._row_to_user(refreshed)

    def reset_password(self, *, user_id: str) -> str:
        temporary_password = secrets.token_urlsafe(9)[:12]
        updated_at = self._utcnow().isoformat()
        password_hash = self.password_hasher.hash(temporary_password)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET password_hash = %s,
                            password_must_change = %s,
                            updated_at = %s
                        WHERE user_id = %s
                        """,
                        (password_hash, True, updated_at, user_id),
                    )
                    if cursor.rowcount == 0:
                        raise KeyError(user_id)
                    cursor.execute("DELETE FROM auth_sessions WHERE user_id = %s", (user_id,))
            else:
                cursor = connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?,
                        password_must_change = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (password_hash, 1, updated_at, user_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(user_id)
                connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        return temporary_password

    def list_users(self) -> list[AuthenticatedUser]:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT user_id, username, display_name, avatar_url, role, is_active,
                               password_must_change, created_at, updated_at, last_login_at
                        FROM users
                        ORDER BY created_at ASC
                        """
                    )
                    rows = cursor.fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT user_id, username, display_name, avatar_url, role, is_active,
                           password_must_change, created_at, updated_at, last_login_at
                    FROM users
                    ORDER BY created_at ASC
                    """
                ).fetchall()
        return [self._row_to_user(row) for row in rows]


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService()
