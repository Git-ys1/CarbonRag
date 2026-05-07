---
name: knowledge
description: "Skill for the Knowledge area of CarbonRag. 114 symbols across 16 files."
---

# Knowledge

114 symbols | 16 files | Cohesion: 80%

## When to Use

- Working with code in `backend/`
- Understanding how test_knowledge_store_supports_items_tasks_chunks_and_session_attachments, test_knowledge_task_runner_processes_queued_item, resolve_private_corpus_dir work
- Modifying knowledge-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/knowledge/store.py` | list_chunks, list_tasks, list_tasks_for_user, list_admin_tasks, save_workflow_run (+43) |
| `backend/app/knowledge/service.py` | __init__, bootstrap_shared_library, sync_shared_private_samples, create_personal_item_from_upload, _compute_file_hash (+14) |
| `backend/app/knowledge/parsers.py` | parse_document, _read_text_file, _read_csv_file, _read_xlsx_file, _read_xls_file (+3) |
| `backend/app/knowledge/chunker.py` | chunk_knowledge_text, chunk_text_to_knowledge_chunks, _split_segments, _merge_segments, _slice_long_segment (+3) |
| `backend/app/knowledge/extractor.py` | extract_text_from_source, _read_text_with_fallbacks, _extract_csv_text, _extract_docx_text, _extract_xlsx_text (+2) |
| `backend/app/retrieval/private_corpus_loader.py` | resolve_private_corpus_dir, _parse_frontmatter, load_private_sample_manifest, load_private_sample_catalog, _load_csv_as_text (+1) |
| `backend/app/knowledge/runner.py` | enqueue, submit, get_knowledge_task_runner, start, _run (+1) |
| `backend/app/private_samples/catalog.py` | _ensure_shared_knowledge_items_loaded, _compute_sha256 |
| `backend/app/session/service.py` | _get_default_knowledge_service, _get_knowledge_service |
| `backend/app/knowledge/schemas.py` | KnowledgeItemSummary, KnowledgeItemDetail |

## Entry Points

Start here when exploring this area:

- **`test_knowledge_store_supports_items_tasks_chunks_and_session_attachments`** (Function) — `backend/tests/test_knowledge_store.py:13`
- **`test_knowledge_task_runner_processes_queued_item`** (Function) — `backend/tests/test_knowledge_runner.py:21`
- **`resolve_private_corpus_dir`** (Function) — `backend/app/retrieval/private_corpus_loader.py:21`
- **`load_private_sample_manifest`** (Function) — `backend/app/retrieval/private_corpus_loader.py:46`
- **`load_private_sample_catalog`** (Function) — `backend/app/retrieval/private_corpus_loader.py:53`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KnowledgeStore` | Class | `backend/app/knowledge/store.py` | 31 |
| `BaseKnowledgeStore` | Class | `backend/app/knowledge/store.py` | 890 |
| `KnowledgeItemSummary` | Class | `backend/app/knowledge/schemas.py` | 61 |
| `KnowledgeItemDetail` | Class | `backend/app/knowledge/schemas.py` | 109 |
| `test_knowledge_store_supports_items_tasks_chunks_and_session_attachments` | Function | `backend/tests/test_knowledge_store.py` | 13 |
| `test_knowledge_task_runner_processes_queued_item` | Function | `backend/tests/test_knowledge_runner.py` | 21 |
| `resolve_private_corpus_dir` | Function | `backend/app/retrieval/private_corpus_loader.py` | 21 |
| `load_private_sample_manifest` | Function | `backend/app/retrieval/private_corpus_loader.py` | 46 |
| `load_private_sample_catalog` | Function | `backend/app/retrieval/private_corpus_loader.py` | 53 |
| `load_private_sample_documents` | Function | `backend/app/retrieval/private_corpus_loader.py` | 81 |
| `load_private_sample_override_map` | Function | `backend/app/private_samples/overrides.py` | 21 |
| `test_extract_text_from_old_doc_raises_clear_error` | Function | `backend/tests/test_knowledge_extractor.py` | 103 |
| `extract_text_from_source` | Function | `backend/app/knowledge/extractor.py` | 14 |
| `get_knowledge_task_runner` | Function | `backend/app/knowledge/runner.py` | 101 |
| `parse_document` | Function | `backend/app/knowledge/parsers.py` | 18 |
| `chunk_knowledge_text` | Function | `backend/app/knowledge/chunker.py` | 12 |
| `chunk_text_to_knowledge_chunks` | Function | `backend/app/knowledge/chunker.py` | 41 |
| `chunk_utcnow` | Function | `backend/app/knowledge/chunker.py` | 178 |
| `get_knowledge_service` | Function | `backend/app/knowledge/service.py` | 615 |
| `list_chunks` | Method | `backend/app/knowledge/store.py` | 306 |

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
| Tests | 6 calls |
| Endpoints | 3 calls |
| Rag | 3 calls |
| Adapters | 2 calls |
| Carbon | 2 calls |
| Settings | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_knowledge_store_supports_items_tasks_chunks_and_session_attachments"})` — see callers and callees
2. `gitnexus_query({query: "knowledge"})` — find related execution flows
3. Read key files listed above for implementation details
