---
name: retrieval
description: "Skill for the Retrieval area of CarbonRag. 29 symbols across 12 files."
---

# Retrieval

29 symbols | 12 files | Cohesion: 80%

## When to Use

- Working with code in `backend/`
- Understanding how test_vector_backend_current_does_not_connect_pgvector, get_public_policy_retriever, get_private_sample_retriever work
- Modifying retrieval-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/retrieval/private_chunker.py` | _normalize_paragraphs, _split_large_paragraph, _chunk_markdown, _chunk_csv, chunk_private_sample_document |
| `backend/app/retrieval/public_retriever.py` | get_public_policy_retriever, _tokenize, __init__, search |
| `backend/app/rag/vector_store.py` | healthcheck, __init__, build_vector_store_adapter |
| `backend/tests/test_public_retriever.py` | test_public_policy_documents_can_be_loaded, test_public_policy_document_can_be_chunked, test_public_retriever_returns_hits_for_dual_carbon_question |
| `backend/app/retrieval/public_corpus_loader.py` | resolve_public_corpus_dir, _parse_frontmatter, load_public_policy_documents |
| `backend/app/retrieval/public_chunker.py` | _normalize_paragraphs, _split_large_paragraph, chunk_public_policy_document |
| `backend/app/retrieval/mixed_retriever.py` | __init__, get_mixed_scope_retriever |
| `backend/app/retrieval/knowledge_schemas.py` | KnowledgeItemSummary, KnowledgeItemDetail |
| `backend/tests/test_pgvector_adapter.py` | test_vector_backend_current_does_not_connect_pgvector |
| `backend/app/retrieval/private_retriever.py` | get_private_sample_retriever |

## Entry Points

Start here when exploring this area:

- **`test_vector_backend_current_does_not_connect_pgvector`** (Function) — `backend/tests/test_pgvector_adapter.py:106`
- **`get_public_policy_retriever`** (Function) — `backend/app/retrieval/public_retriever.py:72`
- **`get_private_sample_retriever`** (Function) — `backend/app/retrieval/private_retriever.py:107`
- **`get_mixed_scope_retriever`** (Function) — `backend/app/retrieval/mixed_retriever.py:70`
- **`build_vector_store_adapter`** (Function) — `backend/app/rag/vector_store.py:661`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KnowledgeItemSummary` | Class | `backend/app/retrieval/knowledge_schemas.py` | 44 |
| `KnowledgeItemDetail` | Class | `backend/app/retrieval/knowledge_schemas.py` | 85 |
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
| `search` | Method | `backend/app/retrieval/public_retriever.py` | 27 |
| `_normalize_paragraphs` | Function | `backend/app/retrieval/private_chunker.py` | 12 |
| `_split_large_paragraph` | Function | `backend/app/retrieval/private_chunker.py` | 21 |
| `_chunk_markdown` | Function | `backend/app/retrieval/private_chunker.py` | 43 |
| `_chunk_csv` | Function | `backend/app/retrieval/private_chunker.py` | 87 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Providers | 2 calls |
| Settings | 1 calls |
| Carbon | 1 calls |
| Knowledge | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_vector_backend_current_does_not_connect_pgvector"})` — see callers and callees
2. `gitnexus_query({query: "retrieval"})` — find related execution flows
3. Read key files listed above for implementation details
