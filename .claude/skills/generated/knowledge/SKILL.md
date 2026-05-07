---
name: knowledge
description: "Skill for the Knowledge area of CarbonRag. 106 symbols across 11 files."
---

# Knowledge

106 symbols | 11 files | Cohesion: 79%

## When to Use

- Working with code in `backend/`
- Understanding how test_knowledge_store_supports_items_tasks_chunks_and_session_attachments, test_knowledge_task_runner_processes_queued_item, get_knowledge_task_runner work
- Modifying knowledge-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/knowledge/store.py` | list_chunks, list_tasks, list_tasks_for_user, list_admin_tasks, save_workflow_run (+43) |
| `backend/app/knowledge/service.py` | __init__, bootstrap_shared_library, sync_shared_private_samples, list_admin_items, list_shared_items (+17) |
| `backend/app/knowledge/parsers.py` | parse_document, _read_text_file, _read_csv_file, _read_xlsx_file, _read_xls_file (+3) |
| `backend/app/knowledge/chunker.py` | chunk_knowledge_text, chunk_text_to_knowledge_chunks, _split_segments, _merge_segments, _slice_long_segment (+3) |
| `backend/app/knowledge/extractor.py` | extract_text_from_source, _read_text_with_fallbacks, _extract_csv_text, _extract_docx_text, _extract_xlsx_text (+2) |
| `backend/app/knowledge/runner.py` | enqueue, submit, get_knowledge_task_runner, start, _run (+1) |
| `backend/app/session/service.py` | _get_default_knowledge_service, _get_knowledge_service |
| `backend/app/knowledge/schemas.py` | KnowledgeItemSummary, KnowledgeItemDetail |
| `backend/tests/test_knowledge_store.py` | test_knowledge_store_supports_items_tasks_chunks_and_session_attachments |
| `backend/tests/test_knowledge_runner.py` | test_knowledge_task_runner_processes_queued_item |

## Entry Points

Start here when exploring this area:

- **`test_knowledge_store_supports_items_tasks_chunks_and_session_attachments`** (Function) — `backend/tests/test_knowledge_store.py:13`
- **`test_knowledge_task_runner_processes_queued_item`** (Function) — `backend/tests/test_knowledge_runner.py:21`
- **`get_knowledge_task_runner`** (Function) — `backend/app/knowledge/runner.py:101`
- **`test_extract_text_from_old_doc_raises_clear_error`** (Function) — `backend/tests/test_knowledge_extractor.py:103`
- **`extract_text_from_source`** (Function) — `backend/app/knowledge/extractor.py:14`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KnowledgeStore` | Class | `backend/app/knowledge/store.py` | 31 |
| `BaseKnowledgeStore` | Class | `backend/app/knowledge/store.py` | 890 |
| `KnowledgeItemSummary` | Class | `backend/app/knowledge/schemas.py` | 61 |
| `KnowledgeItemDetail` | Class | `backend/app/knowledge/schemas.py` | 109 |
| `test_knowledge_store_supports_items_tasks_chunks_and_session_attachments` | Function | `backend/tests/test_knowledge_store.py` | 13 |
| `test_knowledge_task_runner_processes_queued_item` | Function | `backend/tests/test_knowledge_runner.py` | 21 |
| `get_knowledge_task_runner` | Function | `backend/app/knowledge/runner.py` | 101 |
| `test_extract_text_from_old_doc_raises_clear_error` | Function | `backend/tests/test_knowledge_extractor.py` | 103 |
| `extract_text_from_source` | Function | `backend/app/knowledge/extractor.py` | 14 |
| `parse_document` | Function | `backend/app/knowledge/parsers.py` | 18 |
| `chunk_knowledge_text` | Function | `backend/app/knowledge/chunker.py` | 12 |
| `chunk_text_to_knowledge_chunks` | Function | `backend/app/knowledge/chunker.py` | 41 |
| `chunk_utcnow` | Function | `backend/app/knowledge/chunker.py` | 178 |
| `get_knowledge_service` | Function | `backend/app/knowledge/service.py` | 615 |
| `list_chunks` | Method | `backend/app/knowledge/store.py` | 306 |
| `list_tasks` | Method | `backend/app/knowledge/store.py` | 421 |
| `list_tasks_for_user` | Method | `backend/app/knowledge/store.py` | 454 |
| `list_admin_tasks` | Method | `backend/app/knowledge/store.py` | 464 |
| `save_workflow_run` | Method | `backend/app/knowledge/store.py` | 544 |
| `save_workflow_node` | Method | `backend/app/knowledge/store.py` | 593 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Trigger_scan → Get_settings` | cross_community | 7 |
| `Trigger_scan → Load_local_chat_provider_override` | cross_community | 7 |
| `Claim_next_task → _placeholder` | cross_community | 6 |
| `Claim_next_task → Connect_postgres` | cross_community | 6 |
| `Save_workflow_run → _placeholder` | intra_community | 5 |
| `Save_workflow_run → Connect_postgres` | cross_community | 5 |
| `Save_workflow_run → _parse_json_list` | intra_community | 5 |
| `Save_workflow_run → _parse_json_object` | intra_community | 5 |
| `Requeue_task → _placeholder` | cross_community | 5 |
| `Requeue_task → Connect_postgres` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 6 calls |
| Endpoints | 3 calls |
| Rag | 3 calls |
| Retrieval | 3 calls |
| Adapters | 2 calls |

## How to Explore

1. `gitnexus_context({name: "test_knowledge_store_supports_items_tasks_chunks_and_session_attachments"})` — see callers and callees
2. `gitnexus_query({query: "knowledge"})` — find related execution flows
3. Read key files listed above for implementation details
