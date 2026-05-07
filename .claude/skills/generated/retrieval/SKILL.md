---
name: retrieval
description: "Skill for the Retrieval area of CarbonRag. 40 symbols across 17 files."
---

# Retrieval

40 symbols | 17 files | Cohesion: 77%

## When to Use

- Working with code in `backend/`
- Understanding how resolve_private_corpus_dir, load_private_sample_manifest, load_private_sample_catalog work
- Modifying retrieval-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/retrieval/private_corpus_loader.py` | resolve_private_corpus_dir, _parse_frontmatter, load_private_sample_manifest, load_private_sample_catalog, _load_csv_as_text (+1) |
| `backend/app/retrieval/private_chunker.py` | _normalize_paragraphs, _split_large_paragraph, _chunk_markdown, _chunk_csv, chunk_private_sample_document |
| `backend/app/retrieval/public_retriever.py` | get_public_policy_retriever, _tokenize, __init__, search |
| `backend/app/rag/vector_store.py` | healthcheck, __init__, build_vector_store_adapter |
| `backend/tests/test_public_retriever.py` | test_public_policy_documents_can_be_loaded, test_public_policy_document_can_be_chunked, test_public_retriever_returns_hits_for_dual_carbon_question |
| `backend/app/retrieval/public_corpus_loader.py` | resolve_public_corpus_dir, _parse_frontmatter, load_public_policy_documents |
| `backend/app/retrieval/public_chunker.py` | _normalize_paragraphs, _split_large_paragraph, chunk_public_policy_document |
| `backend/app/private_samples/catalog.py` | _ensure_shared_knowledge_items_loaded, _compute_sha256 |
| `backend/app/retrieval/mixed_retriever.py` | __init__, get_mixed_scope_retriever |
| `backend/app/retrieval/knowledge_schemas.py` | KnowledgeItemSummary, KnowledgeItemDetail |

## Entry Points

Start here when exploring this area:

- **`resolve_private_corpus_dir`** (Function) — `backend/app/retrieval/private_corpus_loader.py:21`
- **`load_private_sample_manifest`** (Function) — `backend/app/retrieval/private_corpus_loader.py:46`
- **`load_private_sample_catalog`** (Function) — `backend/app/retrieval/private_corpus_loader.py:53`
- **`load_private_sample_documents`** (Function) — `backend/app/retrieval/private_corpus_loader.py:81`
- **`load_private_sample_override_map`** (Function) — `backend/app/private_samples/overrides.py:21`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KnowledgeItemSummary` | Class | `backend/app/retrieval/knowledge_schemas.py` | 44 |
| `KnowledgeItemDetail` | Class | `backend/app/retrieval/knowledge_schemas.py` | 85 |
| `resolve_private_corpus_dir` | Function | `backend/app/retrieval/private_corpus_loader.py` | 21 |
| `load_private_sample_manifest` | Function | `backend/app/retrieval/private_corpus_loader.py` | 46 |
| `load_private_sample_catalog` | Function | `backend/app/retrieval/private_corpus_loader.py` | 53 |
| `load_private_sample_documents` | Function | `backend/app/retrieval/private_corpus_loader.py` | 81 |
| `load_private_sample_override_map` | Function | `backend/app/private_samples/overrides.py` | 21 |
| `test_vector_backend_current_does_not_connect_pgvector` | Function | `backend/tests/test_pgvector_adapter.py` | 106 |
| `get_public_policy_retriever` | Function | `backend/app/retrieval/public_retriever.py` | 72 |
| `get_private_sample_retriever` | Function | `backend/app/retrieval/private_retriever.py` | 107 |
| `get_mixed_scope_retriever` | Function | `backend/app/retrieval/mixed_retriever.py` | 70 |
| `build_vector_store_adapter` | Function | `backend/app/rag/vector_store.py` | 661 |
| `chunk_private_sample_document` | Function | `backend/app/retrieval/private_chunker.py` | 129 |
| `test_public_policy_documents_can_be_loaded` | Function | `backend/tests/test_public_retriever.py` | 5 |
| `resolve_public_corpus_dir` | Function | `backend/app/retrieval/public_corpus_loader.py` | 15 |
| `load_public_policy_documents` | Function | `backend/app/retrieval/public_corpus_loader.py` | 40 |
| `test_public_policy_document_can_be_chunked` | Function | `backend/tests/test_public_retriever.py` | 18 |
| `chunk_public_policy_document` | Function | `backend/app/retrieval/public_chunker.py` | 40 |
| `test_public_retriever_returns_hits_for_dual_carbon_question` | Function | `backend/tests/test_public_retriever.py` | 32 |
| `healthcheck` | Method | `backend/app/rag/vector_store.py` | 43 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Trigger_knowledge_refresh_task → Get_settings` | cross_community | 10 |
| `Trigger_knowledge_refresh_task → Load_local_chat_provider_override` | cross_community | 10 |
| `Get_admin_system_status → Get_settings` | cross_community | 9 |
| `Get_admin_system_status → Load_local_chat_provider_override` | cross_community | 9 |
| `Update_admin_private_sample → Get_settings` | cross_community | 9 |
| `Update_admin_private_sample → Load_local_chat_provider_override` | cross_community | 9 |
| `List_private_samples → Get_settings` | cross_community | 8 |
| `List_private_samples → Load_local_chat_provider_override` | cross_community | 8 |
| `List_admin_private_samples → Get_settings` | cross_community | 8 |
| `List_admin_private_samples → Load_local_chat_provider_override` | cross_community | 8 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Carbon | 3 calls |
| Settings | 2 calls |
| Providers | 2 calls |

## How to Explore

1. `gitnexus_context({name: "resolve_private_corpus_dir"})` — see callers and callees
2. `gitnexus_query({query: "retrieval"})` — find related execution flows
3. Read key files listed above for implementation details
