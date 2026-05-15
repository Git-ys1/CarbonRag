import sqlite3

from app.runtime_db.bootstrap import bootstrap_runtime_database
from app.runtime_db.schema import CORE_TABLES


class FakeCursor:
    def __init__(self, executed: list[str]) -> None:
        self.executed = executed

    def execute(self, statement: str, params=None) -> None:
        self.executed.append(" ".join(statement.split()))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnection:
    def __init__(self, executed: list[str]) -> None:
        self.executed = executed

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.executed)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_bootstrap_runtime_database_creates_sqlite_schema(tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"

    backend_kind = bootstrap_runtime_database(sqlite_db_path=db_path)

    assert backend_kind == "sqlite"
    connection = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        message_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        calculation_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(carbon_calculations)").fetchall()
        }
        factor_record_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(carbon_factor_records)").fetchall()
        }
    finally:
        connection.close()
    assert set(CORE_TABLES).issubset(tables)
    assert "thinking_content" in message_columns
    assert "carbon_inventories" in tables
    assert "carbon_activity_items" in tables
    assert "carbon_factor_sources" in tables
    assert "carbon_factor_records" in tables
    assert "carbon_factor_catalog_entries" in tables
    assert "carbon_factor_aliases" in tables
    assert "carbon_factor_import_jobs" in tables
    assert "policy_crawl_sources" in tables
    assert "policy_crawl_runs" in tables
    assert "policy_crawl_candidates" in tables
    assert "admin_devices" in tables
    assert "edge_relay_sessions" in tables
    assert "admin_access_requests" in tables
    assert "management_action_requests" in tables
    assert "management_audit_logs" in tables
    assert "inventory_id" in calculation_columns
    assert "scope_summary_json" in calculation_columns
    assert "metadata_json" in factor_record_columns


def test_bootstrap_runtime_database_executes_postgres_schema(monkeypatch) -> None:
    executed: list[str] = []

    monkeypatch.setattr(
        "app.runtime_db.bootstrap.connect_postgres",
        lambda *args, **kwargs: FakeConnection(executed),
    )

    backend_kind = bootstrap_runtime_database(database_url="postgresql://example")

    assert backend_kind == "postgresql"
    assert any("CREATE TABLE IF NOT EXISTS sessions" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS feedback_entries" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_calculations" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_inventories" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_activity_items" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_factor_sources" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_factor_records" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_factor_catalog_entries" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS carbon_factor_import_jobs" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS reports" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS report_sources" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS policy_crawl_sources" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS policy_crawl_runs" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS policy_crawl_candidates" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS admin_devices" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS edge_relay_sessions" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS admin_access_requests" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS management_action_requests" in statement for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS management_audit_logs" in statement for statement in executed)
    assert any("ALTER TABLE messages ADD COLUMN IF NOT EXISTS thinking_content TEXT" in statement for statement in executed)
