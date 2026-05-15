from app.ai_runtime.modes import resolve_mode
from app.ai_runtime.schemas.result import RuntimeResult


def test_ask_mode_contract() -> None:
    mode = resolve_mode("ask")

    assert mode.allowed_tools == (
        "policy_retrieve",
        "enterprise_retrieve",
        "mixed_retrieve",
        "session_file_search",
        "rag_pro_search",
        "rag_pro_answer",
        "langchain_rag_search",
        "langchain_rag_answer",
        "carbon_factor_lookup",
        "report_carbon_extract_calc",
        "report_file_generate",
    )
    assert mode.default_stub_tool_sequence == ("policy_retrieve",)
    assert mode.response_schema is RuntimeResult
    assert "Do not use Markdown # headings" in mode.prompt_policy
    assert "tables" in mode.prompt_policy


def test_carbon_mode_contract() -> None:
    mode = resolve_mode("carbon")

    assert mode.allowed_tools == (
        "enterprise_retrieve",
        "carbon_factor_lookup",
        "carbon_calc",
    )
    assert mode.default_stub_tool_sequence == (
        "enterprise_retrieve",
        "carbon_factor_lookup",
        "carbon_calc",
    )
    assert mode.response_schema is RuntimeResult


def test_report_mode_contract() -> None:
    mode = resolve_mode("report")

    assert mode.allowed_tools == (
        "policy_retrieve",
        "enterprise_retrieve",
        "report_draft",
        "report_file_generate",
    )
    assert mode.default_stub_tool_sequence == (
        "policy_retrieve",
        "enterprise_retrieve",
        "report_draft",
    )
    assert mode.response_schema is RuntimeResult
