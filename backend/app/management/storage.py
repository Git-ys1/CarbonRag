import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.runtime_db.bootstrap import bootstrap_runtime_database, get_runtime_backend_kind
from app.runtime_db.compat import connect_postgres
from app.session.store import DEFAULT_SESSION_DB_PATH


class ManagementStore:
    def __init__(self, *, database_url: str | None = None, sqlite_db_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.sqlite_db_path = Path(sqlite_db_path or DEFAULT_SESSION_DB_PATH)
        self.backend_kind = get_runtime_backend_kind(self.database_url)
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_runtime_database(database_url=self.database_url, sqlite_db_path=self.sqlite_db_path)

    def _connect(self):
        if self.backend_kind == "postgresql":
            return connect_postgres(self.database_url)
        connection = sqlite3.connect(self.sqlite_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @property
    def _p(self) -> str:
        return "%s" if self.backend_kind == "postgresql" else "?"

    def _row(self, row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    def _rows(self, rows: list[Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def fetch_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT user_id, username, display_name, role, is_active, created_at, last_login_at
                        FROM users
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                    return self._row(cursor.fetchone())
            return self._row(
                connection.execute(
                    """
                    SELECT user_id, username, display_name, role, is_active, created_at, last_login_at
                    FROM users
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
            )

    def list_management_users(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            query = """
                SELECT user_id, username, display_name, role, is_active, created_at, last_login_at
                FROM users
                WHERE role IN ('admin', 'super_admin')
                ORDER BY CASE WHEN role = 'super_admin' THEN 0 ELSE 1 END, created_at ASC
            """
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    return self._rows(cursor.fetchall())
            return self._rows(connection.execute(query).fetchall())

    def list_active_super_admins(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            query = "SELECT user_id, username, role, is_active FROM users WHERE role = 'super_admin' AND is_active = TRUE"
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    return self._rows(cursor.fetchall())
            return self._rows(
                connection.execute(
                    "SELECT user_id, username, role, is_active FROM users WHERE role = 'super_admin' AND is_active = 1"
                ).fetchall()
            )

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT * FROM admin_devices WHERE device_id = %s", (device_id,))
                    return self._row(cursor.fetchone())
            return self._row(connection.execute("SELECT * FROM admin_devices WHERE device_id = ?", (device_id,)).fetchone())

    def list_devices(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            query = "SELECT * FROM admin_devices ORDER BY created_at DESC"
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    return self._rows(cursor.fetchall())
            return self._rows(connection.execute(query).fetchall())

    def count_active_admin_devices_for_fingerprint(self, fingerprint_hash: str) -> int:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM admin_devices
                        WHERE fingerprint_hash = %s AND role_scope = 'admin' AND is_active = TRUE
                        """,
                        (fingerprint_hash,),
                    )
                    row = cursor.fetchone()
                    return int(row["count"] if row else 0)
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM admin_devices
                WHERE fingerprint_hash = ? AND role_scope = 'admin' AND is_active = 1
                """,
                (fingerprint_hash,),
            ).fetchone()
            return int(row["count"] if row else 0)

    def upsert_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        columns = [
            "device_id",
            "role_scope",
            "owner_user_id",
            "device_name",
            "mac_hint",
            "device_public_key",
            "fingerprint_hash",
            "is_active",
            "approved_by",
            "approved_at",
            "created_at",
            "last_seen_at",
            "revoked_at",
        ]
        values = [payload.get(column) for column in columns]
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO admin_devices (
                            device_id, role_scope, owner_user_id, device_name, mac_hint,
                            device_public_key, fingerprint_hash, is_active, approved_by, approved_at,
                            created_at, last_seen_at, revoked_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (device_id) DO UPDATE SET
                            role_scope = EXCLUDED.role_scope,
                            owner_user_id = EXCLUDED.owner_user_id,
                            device_name = EXCLUDED.device_name,
                            mac_hint = EXCLUDED.mac_hint,
                            device_public_key = EXCLUDED.device_public_key,
                            fingerprint_hash = EXCLUDED.fingerprint_hash,
                            is_active = EXCLUDED.is_active,
                            approved_by = EXCLUDED.approved_by,
                            approved_at = EXCLUDED.approved_at,
                            last_seen_at = EXCLUDED.last_seen_at,
                            revoked_at = EXCLUDED.revoked_at
                        """,
                        values,
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO admin_devices (
                        device_id, role_scope, owner_user_id, device_name, mac_hint,
                        device_public_key, fingerprint_hash, is_active, approved_by, approved_at,
                        created_at, last_seen_at, revoked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        role_scope = excluded.role_scope,
                        owner_user_id = excluded.owner_user_id,
                        device_name = excluded.device_name,
                        mac_hint = excluded.mac_hint,
                        device_public_key = excluded.device_public_key,
                        fingerprint_hash = excluded.fingerprint_hash,
                        is_active = excluded.is_active,
                        approved_by = excluded.approved_by,
                        approved_at = excluded.approved_at,
                        last_seen_at = excluded.last_seen_at,
                        revoked_at = excluded.revoked_at
                    """,
                    values,
                )
        device = self.get_device(str(payload["device_id"]))
        if device is None:
            raise RuntimeError("Management device was not persisted.")
        return device

    def insert_access_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            params = (
                payload["request_id"],
                payload["admin_user_id"],
                payload["device_id"],
                payload.get("device_name"),
                payload.get("mac_hint"),
                payload["device_public_key"],
                payload["fingerprint_hash"],
                payload["status"],
                payload["requested_at"],
                payload.get("decided_by"),
                payload.get("decided_at"),
                payload.get("decision_note"),
            )
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO admin_access_requests (
                            request_id, admin_user_id, device_id, device_name, mac_hint,
                            device_public_key, fingerprint_hash, status, requested_at,
                            decided_by, decided_at, decision_note
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        params,
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO admin_access_requests (
                        request_id, admin_user_id, device_id, device_name, mac_hint,
                        device_public_key, fingerprint_hash, status, requested_at,
                        decided_by, decided_at, decision_note
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
        request = self.get_access_request(str(payload["request_id"]))
        if request is None:
            raise RuntimeError("Management access request was not persisted.")
        return request

    def get_access_request(self, request_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT * FROM admin_access_requests WHERE request_id = %s", (request_id,))
                    return self._row(cursor.fetchone())
            return self._row(
                connection.execute("SELECT * FROM admin_access_requests WHERE request_id = ?", (request_id,)).fetchone()
            )

    def list_access_requests(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            query = "SELECT * FROM admin_access_requests ORDER BY requested_at DESC"
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    return self._rows(cursor.fetchall())
            return self._rows(connection.execute(query).fetchall())

    def update_access_request(self, request_id: str, *, status: str, decided_by: str, decided_at: str, decision_note: str | None) -> dict[str, Any] | None:
        with self._connect() as connection:
            params = (status, decided_by, decided_at, decision_note, request_id)
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE admin_access_requests
                        SET status = %s, decided_by = %s, decided_at = %s, decision_note = %s
                        WHERE request_id = %s
                        """,
                        params,
                    )
            else:
                connection.execute(
                    """
                    UPDATE admin_access_requests
                    SET status = ?, decided_by = ?, decided_at = ?, decision_note = ?
                    WHERE request_id = ?
                    """,
                    params,
                )
        return self.get_access_request(request_id)

    def insert_relay_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            params = (
                payload["relay_session_id"],
                payload["user_id"],
                payload["role"],
                payload["device_id"],
                payload["status"],
                payload["connected_at"],
                payload["last_heartbeat_at"],
                payload["expires_at"],
                payload.get("server_ack_status"),
            )
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO edge_relay_sessions (
                            relay_session_id, user_id, role, device_id, status,
                            connected_at, last_heartbeat_at, expires_at, server_ack_status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        params,
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO edge_relay_sessions (
                        relay_session_id, user_id, role, device_id, status,
                        connected_at, last_heartbeat_at, expires_at, server_ack_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
        session = self.get_relay_session(str(payload["relay_session_id"]))
        if session is None:
            raise RuntimeError("Relay session was not persisted.")
        return session

    def get_relay_session(self, relay_session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT * FROM edge_relay_sessions WHERE relay_session_id = %s", (relay_session_id,))
                    return self._row(cursor.fetchone())
            return self._row(
                connection.execute("SELECT * FROM edge_relay_sessions WHERE relay_session_id = ?", (relay_session_id,)).fetchone()
            )

    def get_current_relay_session(self, *, user_id: str | None = None, role: str | None = None) -> dict[str, Any] | None:
        conditions = ["status = 'connected'", "expires_at > ?"]
        params: list[Any] = []
        if self.backend_kind == "postgresql":
            conditions = ["status = 'connected'", "expires_at > %s"]
        params.append(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
        if user_id:
            conditions.append(f"user_id = {self._p}")
            params.append(user_id)
        if role:
            conditions.append(f"role = {self._p}")
            params.append(role)
        query = f"SELECT * FROM edge_relay_sessions WHERE {' AND '.join(conditions)} ORDER BY last_heartbeat_at DESC LIMIT 1"
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    return self._row(cursor.fetchone())
            return self._row(connection.execute(query, tuple(params)).fetchone())

    def update_relay_heartbeat(self, relay_session_id: str, now: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            params = (now, relay_session_id)
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE edge_relay_sessions SET last_heartbeat_at = %s WHERE relay_session_id = %s",
                        params,
                    )
            else:
                connection.execute(
                    "UPDATE edge_relay_sessions SET last_heartbeat_at = ? WHERE relay_session_id = ?",
                    params,
                )
        return self.get_relay_session(relay_session_id)

    def insert_action_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            params = (
                payload["action_request_id"],
                payload["user_id"],
                payload["role"],
                payload["device_id"],
                payload["action_type"],
                payload["payload_hash"],
                payload["status"],
                payload.get("ack_token_hash"),
                payload["expires_at"],
                payload["created_at"],
                payload.get("decided_at"),
            )
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO management_action_requests (
                            action_request_id, user_id, role, device_id, action_type,
                            payload_hash, status, ack_token_hash, expires_at, created_at, decided_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        params,
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO management_action_requests (
                        action_request_id, user_id, role, device_id, action_type,
                        payload_hash, status, ack_token_hash, expires_at, created_at, decided_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
        action = self.get_action_request(str(payload["action_request_id"]))
        if action is None:
            raise RuntimeError("Management action request was not persisted.")
        return action

    def get_action_request(self, action_request_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT * FROM management_action_requests WHERE action_request_id = %s", (action_request_id,))
                    return self._row(cursor.fetchone())
            return self._row(
                connection.execute("SELECT * FROM management_action_requests WHERE action_request_id = ?", (action_request_id,)).fetchone()
            )

    def has_valid_action_ack(self, *, user_id: str, role: str) -> bool:
        with self._connect() as connection:
            params = (user_id, role, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT 1 FROM management_action_requests
                        WHERE user_id = %s AND role = %s AND status = 'approved' AND expires_at > %s
                        LIMIT 1
                        """,
                        params,
                    )
                    return cursor.fetchone() is not None
            return (
                connection.execute(
                    """
                    SELECT 1 FROM management_action_requests
                    WHERE user_id = ? AND role = ? AND status = 'approved' AND expires_at > ?
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
                is not None
            )

    def insert_audit_log(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {**payload, "detail_json": json.dumps(payload.get("detail_json") or {}, ensure_ascii=False)}
        with self._connect() as connection:
            params = (
                payload["audit_id"],
                payload["actor_user_id"],
                payload["actor_role"],
                payload.get("device_id"),
                payload["action_type"],
                payload.get("target_type"),
                payload.get("target_id"),
                payload["decision"],
                payload["detail_json"],
                payload["created_at"],
            )
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO management_audit_logs (
                            audit_id, actor_user_id, actor_role, device_id, action_type,
                            target_type, target_id, decision, detail_json, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        params,
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO management_audit_logs (
                        audit_id, actor_user_id, actor_role, device_id, action_type,
                        target_type, target_id, decision, detail_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
        return payload

    def list_audit_logs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            query = "SELECT * FROM management_audit_logs ORDER BY created_at DESC LIMIT " + str(int(limit))
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
            else:
                rows = connection.execute(query).fetchall()
        result = self._rows(rows)
        for row in result:
            try:
                row["detail_json"] = json.loads(row.get("detail_json") or "{}")
            except json.JSONDecodeError:
                row["detail_json"] = {}
        return result
