---
name: rag
description: "Skill for the Rag area of CarbonRag. 210 symbols across 18 files."
---

# Rag

210 symbols | 18 files | Cohesion: 87%

## When to Use

- Working with code in `backend/`
- Understanding how build_chunk, build_service, test_rag_engine_returns_structured_bm25_fallback_when_disabled work
- Modifying rag-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/rag/parser.py` | supports, parse, score, _failed_document, _metadata (+32) |
| `backend/app/rag/graph.py` | extract_entities, extract_relations, build_summary, build, candidates_by_chunk_id (+27) |
| `backend/app/rag/vector_store.py` | healthcheck, upsert_chunks, search, delete_by_document, _connect (+25) |
| `backend/app/rag/service.py` | retrieve, _initial_fallback_reason, _private_allowed_ids, _resolve_query_embedding, _retrieve_with_experimental_strategy (+16) |
| `backend/app/rag/workflow.py` | workflow_utcnow, node, start_run, start_node, complete_node (+7) |
| `backend/tests/test_rag_contracts_and_adapters.py` | test_retrieval_strategy_and_path_are_explicit, test_lightweight_parser_provider_wraps_existing_parser, search, test_disabled_vector_store_adapter_is_safe_by_default, test_fake_vector_store_adapter_search_returns_fixed_chunks (+5) |
| `backend/tests/test_rag_engine.py` | build_chunk, build_service, test_rag_engine_returns_structured_bm25_fallback_when_disabled, test_rag_engine_uses_embedding_provider_for_available_vector_retrieval, test_rag_engine_reranks_through_ai_runtime_provider (+4) |
| `backend/tests/test_pgvector_adapter.py` | test_rag_engine_pgvector_unavailable_falls_back_to_current, _chunk_record, _embedding, test_pgvector_adapter_initialization_failure_is_safe, test_pgvector_adapter_search_returns_unified_result_structure (+4) |
| `backend/app/rag/contracts.py` | model_post_init, hash_content, model_post_init, from_retrieved_chunk, _rough_token_count (+4) |
| `backend/app/rag/retriever_strategy.py` | retrieve, _merge_chunks, _chunk_source_metadata, _normalize_score, retrieve (+4) |

## Entry Points

Start here when exploring this area:

- **`build_chunk`** (Function) — `backend/tests/test_rag_engine.py:20`
- **`build_service`** (Function) — `backend/tests/test_rag_engine.py:108`
- **`test_rag_engine_returns_structured_bm25_fallback_when_disabled`** (Function) — `backend/tests/test_rag_engine.py:132`
- **`test_rag_engine_uses_embedding_provider_for_available_vector_retrieval`** (Function) — `backend/tests/test_rag_engine.py:179`
- **`test_rag_engine_reranks_through_ai_runtime_provider`** (Function) — `backend/tests/test_rag_engine.py:209`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `DefaultParserProvider` | Class | `backend/app/rag/parser.py` | 48 |
| `LightweightParserProvider` | Class | `backend/app/rag/parser.py` | 166 |
| `RuntimeGraphStoreAdapter` | Class | `backend/app/rag/graph.py` | 196 |
| `FakeGraphStoreAdapter` | Class | `backend/app/rag/graph.py` | 248 |
| `build_chunk` | Function | `backend/tests/test_rag_engine.py` | 20 |
| `build_service` | Function | `backend/tests/test_rag_engine.py` | 108 |
| `test_rag_engine_returns_structured_bm25_fallback_when_disabled` | Function | `backend/tests/test_rag_engine.py` | 132 |
| `test_rag_engine_uses_embedding_provider_for_available_vector_retrieval` | Function | `backend/tests/test_rag_engine.py` | 179 |
| `test_rag_engine_reranks_through_ai_runtime_provider` | Function | `backend/tests/test_rag_engine.py` | 209 |
| `test_rag_engine_reports_zero_hit_metadata` | Function | `backend/tests/test_rag_engine.py` | 245 |
| `test_rag_engine_experimental_hybrid_returns_source_metadata` | Function | `backend/tests/test_rag_engine.py` | 271 |
| `test_rag_engine_experimental_vector_unavailable_falls_back_to_bm25` | Function | `backend/tests/test_rag_engine.py` | 317 |
| `test_rag_engine_graph_unavailable_falls_back_to_existing_retrieval` | Function | `backend/tests/test_rag_engine.py` | 342 |
| `test_retrieval_strategy_and_path_are_explicit` | Function | `backend/tests/test_rag_contracts_and_adapters.py` | 272 |
| `test_rag_engine_pgvector_unavailable_falls_back_to_current` | Function | `backend/tests/test_pgvector_adapter.py` | 170 |
| `plan_retrieval_strategy` | Function | `backend/app/rag/strategy.py` | 16 |
| `build_retrieval_path` | Function | `backend/app/rag/strategy.py` | 34 |
| `get_rag_engine_service` | Function | `backend/app/rag/service.py` | 677 |
| `retrieve_rag_evidence` | Function | `backend/app/api/v1/endpoints/rag.py` | 75 |
| `test_pgvector_adapter_initialization_failure_is_safe` | Function | `backend/tests/test_pgvector_adapter.py` | 91 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _uses_pgvector_backend` | cross_community | 7 |
| `Main → _chunk_source_metadata` | cross_community | 7 |
| `Trigger_scan → Get_settings` | cross_community | 7 |
| `Trigger_scan → Load_local_chat_provider_override` | cross_community | 7 |
| `Main → _private_allowed_ids` | cross_community | 6 |
| `Main → _source_type_filter` | cross_community | 6 |
| `Retrieve_rag_evidence → _uses_pgvector_backend` | intra_community | 5 |
| `Retrieve_rag_evidence → _chunk_source_metadata` | cross_community | 5 |
| `Main → _initial_fallback_reason` | cross_community | 5 |
| `Main → _vector_store_health` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Knowledge | 4 calls |
| Tests | 3 calls |

## How to Explore

1. `gitnexus_context({name: "build_chunk"})` — see callers and callees
2. `gitnexus_query({query: "rag"})` — find related execution flows
3. Read key files listed above for implementation details
