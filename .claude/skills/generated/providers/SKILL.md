---
name: providers
description: "Skill for the Providers area of CarbonRag. 48 symbols across 18 files."
---

# Providers

48 symbols | 18 files | Cohesion: 89%

## When to Use

- Working with code in `backend/`
- Understanding how test_chat_provider_stream_response_emits_thinking_and_answer_chunks, test_chat_provider_aggregates_streaming_chunks, test_chat_provider_falls_back_to_non_stream_when_stream_is_empty work
- Modifying providers-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/ai_runtime/providers/chat_openai_compatible.py` | generate_response, stream_response, _streaming_response, _aggregate_stream_response, _generate_non_stream_response (+7) |
| `backend/app/ai_runtime/providers/base.py` | describe, generate_response, stream_response, describe, describe (+2) |
| `backend/app/ai_runtime/providers/rerank_local.py` | NoopRerankProvider, FakeRerankProvider, rerank_stub, _keyword_overlap_score, _tokenize |
| `backend/app/ai_runtime/providers/factory.py` | get_chat_provider, get_embedding_provider, get_rerank_provider, reset_provider_factory_cache |
| `backend/app/ai_runtime/providers/ollama_chat.py` | OllamaChatProvider, generate_response, stream_response, _build_payload |
| `backend/tests/test_ai_runtime_chat_provider.py` | test_chat_provider_aggregates_streaming_chunks, test_chat_provider_falls_back_to_non_stream_when_stream_is_empty |
| `backend/tests/test_rerank_providers.py` | test_rerank_factory_defaults_to_noop_disabled_provider, test_fake_rerank_provider_uses_predictable_keyword_overlap |
| `backend/tests/test_ai_runtime_orchestrator.py` | FakeChatProvider, FailingChatProvider |
| `backend/tests/test_ai_runtime_streaming_contract.py` | test_chat_provider_stream_response_emits_thinking_and_answer_chunks |
| `backend/app/report/service.py` | get_chat_provider |

## Entry Points

Start here when exploring this area:

- **`test_chat_provider_stream_response_emits_thinking_and_answer_chunks`** (Function) — `backend/tests/test_ai_runtime_streaming_contract.py:104`
- **`test_chat_provider_aggregates_streaming_chunks`** (Function) — `backend/tests/test_ai_runtime_chat_provider.py:21`
- **`test_chat_provider_falls_back_to_non_stream_when_stream_is_empty`** (Function) — `backend/tests/test_ai_runtime_chat_provider.py:66`
- **`get_chat_provider`** (Function) — `backend/app/report/service.py:23`
- **`get_chat_provider`** (Function) — `backend/app/ai_runtime/providers/factory.py:10`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `FakeChatProvider` | Class | `backend/tests/test_ai_runtime_orchestrator.py` | 14 |
| `FailingChatProvider` | Class | `backend/tests/test_ai_runtime_orchestrator.py` | 35 |
| `OllamaChatProvider` | Class | `backend/app/ai_runtime/providers/ollama_chat.py` | 10 |
| `GeminiChatProvider` | Class | `backend/app/ai_runtime/providers/gemini_chat.py` | 8 |
| `OpenAICompatibleChatProvider` | Class | `backend/app/ai_runtime/providers/chat_openai_compatible.py` | 16 |
| `BaseChatProvider` | Class | `backend/app/ai_runtime/providers/base.py` | 52 |
| `AnthropicChatProvider` | Class | `backend/app/ai_runtime/providers/anthropic_chat.py` | 8 |
| `FakeRerankProvider` | Class | `backend/tests/test_rag_engine.py` | 86 |
| `NoopRerankProvider` | Class | `backend/app/ai_runtime/providers/rerank_local.py` | 14 |
| `FakeRerankProvider` | Class | `backend/app/ai_runtime/providers/rerank_local.py` | 48 |
| `DisabledRerankProvider` | Class | `backend/app/ai_runtime/providers/rerank_disabled.py` | 3 |
| `BaseRerankProvider` | Class | `backend/app/ai_runtime/providers/base.py` | 112 |
| `test_chat_provider_stream_response_emits_thinking_and_answer_chunks` | Function | `backend/tests/test_ai_runtime_streaming_contract.py` | 104 |
| `test_chat_provider_aggregates_streaming_chunks` | Function | `backend/tests/test_ai_runtime_chat_provider.py` | 21 |
| `test_chat_provider_falls_back_to_non_stream_when_stream_is_empty` | Function | `backend/tests/test_ai_runtime_chat_provider.py` | 66 |
| `get_chat_provider` | Function | `backend/app/report/service.py` | 23 |
| `get_chat_provider` | Function | `backend/app/ai_runtime/providers/factory.py` | 10 |
| `get_system_info` | Function | `backend/app/api/v1/endpoints/system.py` | 14 |
| `get_admin_system_status` | Function | `backend/app/api/v1/endpoints/admin.py` | 30 |
| `test_rerank_factory_defaults_to_noop_disabled_provider` | Function | `backend/tests/test_rerank_providers.py` | 35 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get_admin_system_status → Get_settings` | cross_community | 9 |
| `Get_admin_system_status → Load_local_chat_provider_override` | cross_community | 9 |
| `Get_system_status → Load_local_chat_provider_override` | cross_community | 8 |
| `Get_admin_system_status → _compute_sha256` | cross_community | 6 |
| `Get_chat_provider → Utcnow_iso` | cross_community | 5 |
| `Get_chat_provider → Get_settings` | cross_community | 5 |
| `Get_chat_provider → Load_local_chat_provider_override` | cross_community | 5 |
| `Get_system_info → Get_settings` | cross_community | 4 |
| `Get_system_info → Load_local_chat_provider_override` | cross_community | 4 |
| `Get_admin_system_status → Connect_postgres` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Settings | 4 calls |
| Admin | 2 calls |
| Carbon | 2 calls |
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_chat_provider_stream_response_emits_thinking_and_answer_chunks"})` — see callers and callees
2. `gitnexus_query({query: "providers"})` — find related execution flows
3. Read key files listed above for implementation details
