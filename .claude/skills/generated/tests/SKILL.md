---
name: tests
description: "Skill for the Tests area of CarbonRag. 253 symbols across 91 files."
---

# Tests

253 symbols | 91 files | Cohesion: 75%

## When to Use

- Working with code in `backend/`
- Understanding how build_session_service, test_session_service_creates_default_title_and_builds_context, test_session_service_promotes_first_question_to_title work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/tests/test_rag_route.py` | test_rag_retrieve_route_returns_retrieval_only_data, test_rag_retrieve_route_returns_zero_hit_metadata, test_rag_retrieve_route_accepts_experimental_strategy, test_rag_retrieve_route_rejects_blank_question, test_rag_retrieve_route_rejects_invalid_top_k (+7) |
| `backend/app/session/service.py` | create_session, get_session, update_session_title, build_session_context, record_exchange (+5) |
| `backend/tests/test_report_service.py` | seed_mixed_session, build_factor_file, build_services, test_report_service_generates_mixed_report_and_appends_system_message, test_report_service_generates_carbon_summary (+2) |
| `backend/tests/test_postgres_runtime_mode.py` | patch_postgres_connect, build_factor_file, test_feedback_service_persists_with_postgres_backend, test_carbon_service_persists_with_postgres_backend, test_report_storage_persists_with_postgres_backend (+2) |
| `backend/tests/test_graph_index_builder.py` | build_chunk, test_graph_index_builder_build_returns_candidates, test_graph_index_builder_handles_empty_chunks, test_graph_candidates_can_be_looked_up_by_chunk_id, test_graph_local_returns_entity_candidates (+2) |
| `backend/tests/test_calc_carbon_route.py` | test_calc_carbon_route_accepts_activity_items_v2, build_factor_file, build_test_service, test_calc_carbon_route_returns_breakdown_and_citations, test_calc_carbon_route_rejects_unknown_session (+1) |
| `backend/app/memory/store.py` | build_memory_store, list_notes, create_note, _list_notes_postgres, _list_notes_sqlite |
| `backend/app/carbon/service.py` | _utcnow, calculate, get_stored_calculation, _connect, list_session_calculations |
| `backend/tests/test_ask_route_with_session.py` | build_test_services, test_session_ask_route_persists_history_and_citations, test_session_ask_route_supports_mixed_scope_without_private_hits, test_session_ask_route_records_provider_error_message, test_session_ask_stream_persists_real_thinking_content |
| `backend/app/rag/graph.py` | build_summary, build, candidates_by_chunk_id, select_graph_candidates, _dedupe_graph_candidates |

## Entry Points

Start here when exploring this area:

- **`build_session_service`** (Function) — `backend/tests/test_session_service.py:17`
- **`test_session_service_creates_default_title_and_builds_context`** (Function) — `backend/tests/test_session_service.py:27`
- **`test_session_service_promotes_first_question_to_title`** (Function) — `backend/tests/test_session_service.py:67`
- **`test_session_service_begin_and_finalize_exchange_updates_placeholder`** (Function) — `backend/tests/test_session_service.py:102`
- **`build_factor_file`** (Function) — `backend/tests/test_session_reports_listing.py:26`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KnowledgeService` | Class | `backend/app/knowledge/service.py` | 37 |
| `FakeEmbeddingProvider` | Class | `backend/tests/test_rag_engine.py` | 74 |
| `FakeEmbeddingProvider` | Class | `backend/tests/test_ai_runtime_orchestrator.py` | 52 |
| `OpenAICompatibleEmbeddingProvider` | Class | `backend/app/ai_runtime/providers/embedding_openai_compatible.py` | 7 |
| `BaseEmbeddingProvider` | Class | `backend/app/ai_runtime/providers/base.py` | 102 |
| `StaticSearchRetriever` | Class | `backend/tests/test_rag_route.py` | 98 |
| `LeakyPrivateSearchRetriever` | Class | `backend/tests/test_rag_route.py` | 108 |
| `InMemoryPgVectorStoreAdapter` | Class | `backend/tests/test_pgvector_adapter.py` | 25 |
| `PgVectorStoreAdapter` | Class | `backend/app/rag/vector_store.py` | 258 |
| `build_session_service` | Function | `backend/tests/test_session_service.py` | 17 |
| `test_session_service_creates_default_title_and_builds_context` | Function | `backend/tests/test_session_service.py` | 27 |
| `test_session_service_promotes_first_question_to_title` | Function | `backend/tests/test_session_service.py` | 67 |
| `test_session_service_begin_and_finalize_exchange_updates_placeholder` | Function | `backend/tests/test_session_service.py` | 102 |
| `build_factor_file` | Function | `backend/tests/test_session_reports_listing.py` | 26 |
| `test_session_reports_listing_and_carbon_results` | Function | `backend/tests/test_session_reports_listing.py` | 70 |
| `test_session_service_uses_memory_factory_in_postgres_mode_without_db_path` | Function | `backend/tests/test_session_memory_compat.py` | 50 |
| `test_report_update_route_persists_edited_content` | Function | `backend/tests/test_report_update_route.py` | 28 |
| `seed_mixed_session` | Function | `backend/tests/test_report_service.py` | 94 |
| `patch_postgres_connect` | Function | `backend/tests/test_postgres_runtime_mode.py` | 555 |
| `build_factor_file` | Function | `backend/tests/test_postgres_runtime_mode.py` | 564 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Ask_in_session_stream → Get_settings` | cross_community | 6 |
| `Ask_in_session_stream → Build_memory_store` | cross_community | 6 |
| `Ask_in_session_stream → Get_memory_service` | cross_community | 6 |
| `Upload_file → Get_settings` | cross_community | 6 |
| `Upload_file → Build_memory_store` | cross_community | 6 |
| `Upload_file → Get_memory_service` | cross_community | 6 |
| `Replace_attached_private_samples → Get_settings` | cross_community | 6 |
| `Replace_attached_private_samples → Build_memory_store` | cross_community | 6 |
| `Replace_attached_private_samples → Get_memory_service` | cross_community | 6 |
| `Update_session_title → Get_settings` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Knowledge | 15 calls |
| Rag | 13 calls |
| Session | 10 calls |
| Endpoints | 6 calls |
| Memory | 5 calls |
| Report | 4 calls |
| Auth | 4 calls |
| Settings | 4 calls |

## How to Explore

1. `gitnexus_context({name: "build_session_service"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
