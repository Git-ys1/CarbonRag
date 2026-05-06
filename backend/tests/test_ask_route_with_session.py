import httpx

from fastapi.testclient import TestClient

from app.files.service import FileService
from app.files.storage import FileStorage
from app.main import app
from app.session.adapters.sqlite_store import SQLiteSessionStore
from app.session.service import SessionService
from tests.test_helpers import patch_test_auth_service, register_and_login

client = TestClient(app)


class FakeStreamingResponse:
    def __init__(self, *, status_code: int, lines: list[str]) -> None:
        self.status_code = status_code
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def iter_lines(self):
        for line in self._lines:
            yield line


def build_test_services(tmp_path):
    session_service = SessionService(store=SQLiteSessionStore(tmp_path / "carbonrag.sqlite3"))
    file_service = FileService(
        session_service=session_service,
        storage=FileStorage(tmp_path / "uploads"),
    )
    return session_service, file_service


def test_session_ask_route_persists_history_and_citations(monkeypatch, tmp_path) -> None:
    session_service, file_service = build_test_services(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    monkeypatch.setattr("app.api.v1.endpoints.files.get_file_service", lambda: file_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    captured: dict[str, dict] = {}

    def fake_stream(method: str, url: str, *, headers: dict, json: dict, timeout: float):
        captured["payload"] = json
        return FakeStreamingResponse(
            status_code=200,
            lines=[
                'data: {"id":"chatcmpl-session-ok","choices":[{"delta":{"role":"assistant","content":"双碳目标包括"}}]}',
                'data: {"id":"chatcmpl-session-ok","choices":[{"delta":{"role":"assistant","content":"碳达峰和碳中和。"}}]}',
                "data: [DONE]",
            ],
        )

    monkeypatch.setattr("app.ai_runtime.providers.chat_openai_compatible.httpx.stream", fake_stream)

    register_and_login(client, prefix="ask-history")
    session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]

    first_response = client.post(
        f"/api/v1/sessions/{session_id}/ask",
        json={
            "question": "什么是双碳目标？",
            "knowledge_scope": "public",
            "top_k": 3,
        },
    )
    second_response = client.post(
        f"/api/v1/sessions/{session_id}/ask",
        json={
            "question": "它和企业有什么关系？",
            "knowledge_scope": "public",
            "top_k": 3,
        },
    )
    detail = client.get(f"/api/v1/sessions/{session_id}").json()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["messages"][-1]["role"] == "assistant"
    assert detail["messages"][-1]["citations"]
    assert "history-1" in captured["payload"]["messages"][0]["content"]


def test_session_ask_route_supports_mixed_scope_without_private_hits(monkeypatch, tmp_path) -> None:
    session_service, file_service = build_test_services(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    monkeypatch.setattr("app.api.v1.endpoints.files.get_file_service", lambda: file_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    def fake_stream(method: str, url: str, *, headers: dict, json: dict, timeout: float):
        del method, url, headers, json, timeout
        return FakeStreamingResponse(
            status_code=200,
            lines=[
                'data: {"id":"chatcmpl-mixed-no-private","choices":[{"delta":{"role":"assistant","content":"当前仅检索到公共政策依据，企业样例侧暂无命中。"}}]}',
                "data: [DONE]",
            ],
        )

    monkeypatch.setattr("app.ai_runtime.providers.chat_openai_compatible.httpx.stream", fake_stream)

    register_and_login(client, prefix="ask-mixed")
    session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
    response = client.post(
        f"/api/v1/sessions/{session_id}/ask",
        json={
            "question": "企业样例可以用吗？",
            "knowledge_scope": "mixed",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["source_summary"]["knowledge_scope"] == "mixed"


def test_session_ask_route_records_provider_error_message(monkeypatch, tmp_path) -> None:
    session_service, file_service = build_test_services(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    monkeypatch.setattr("app.api.v1.endpoints.files.get_file_service", lambda: file_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    def failing_stream(method: str, url: str, *, headers: dict, json: dict, timeout: float):
        raise httpx.ConnectError("provider down")

    monkeypatch.setattr("app.ai_runtime.providers.chat_openai_compatible.httpx.stream", failing_stream)

    register_and_login(client, prefix="ask-provider")
    session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
    response = client.post(
        f"/api/v1/sessions/{session_id}/ask",
        json={
            "question": "什么是双碳目标？",
            "knowledge_scope": "public",
            "top_k": 3,
        },
    )
    detail = client.get(f"/api/v1/sessions/{session_id}").json()

    assert response.status_code == 502
    assert response.json()["status"] == "provider_error"
    assert detail["messages"][-1]["role"] == "assistant"
    assert detail["messages"][-1]["status"] == "provider_error"


def test_session_ask_stream_persists_real_thinking_content(monkeypatch, tmp_path) -> None:
    session_service, file_service = build_test_services(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.sessions.get_session_service", lambda: session_service)
    monkeypatch.setattr("app.api.v1.endpoints.files.get_file_service", lambda: file_service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    def fake_stream(method: str, url: str, *, headers: dict, json: dict, timeout: float):
        del method, url, headers, json, timeout
        return FakeStreamingResponse(
            status_code=200,
            lines=[
                'event: reasoning',
                'data: {"id":"chatcmpl-session-thinking","choices":[{"delta":{"reasoning_content":"先梳理当前会话，再输出结论。"}}]}',
                "",
                'event: message',
                'data: {"id":"chatcmpl-session-thinking","choices":[{"delta":{"content":"双碳目标包括碳达峰和碳中和。"}}]}',
                "",
                "data: [DONE]",
            ],
        )

    monkeypatch.setattr("app.ai_runtime.providers.chat_openai_compatible.httpx.stream", fake_stream)

    register_and_login(client, prefix="ask-stream-thinking")
    session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]

    with client.stream(
        "POST",
        f"/api/v1/sessions/{session_id}/ask/stream",
        json={
            "question": "什么是双碳目标？",
            "knowledge_scope": "public",
            "top_k": 3,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
        assert "先梳理当前会话，再输出结论。" in body

    detail = client.get(f"/api/v1/sessions/{session_id}").json()
    assert detail["messages"][-1]["thinking_content"] == "先梳理当前会话，再输出结论。"
