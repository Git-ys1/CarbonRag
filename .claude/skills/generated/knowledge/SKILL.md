---
name: knowledge
description: "Skill for the Knowledge area of CarbonRag. 118 symbols across 14 files."
---

# Knowledge

118 symbols | 14 files | Cohesion: 77%

## When to Use

- Working with code in `backend/`
- Understanding how test_knowledge_ingest_success_records_completed_workflow_and_governance, test_knowledge_ingest_parse_failure_marks_workflow_failed, test_knowledge_store_supports_items_tasks_chunks_and_session_attachments work
- Modifying knowledge-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/knowledge/store.py` | get_item, get_visible_item, get_item_by_source, upsert_item, list_chunks (+46) |
| `backend/app/knowledge/service.py` | discover_pending_sources, refresh_all_sources, sync_uploaded_files, __init__, bootstrap_shared_library (+17) |
| `backend/app/knowledge/parsers.py` | parse_document, _read_text_file, _read_csv_file, _read_xlsx_file, _read_xls_file (+3) |
| `backend/app/knowledge/chunker.py` | chunk_knowledge_text, chunk_text_to_knowledge_chunks, _split_segments, _merge_segments, _slice_long_segment (+3) |
| `backend/app/knowledge/runner.py` | run_once, enqueue, submit, get_knowledge_task_runner, start (+2) |
| `backend/app/knowledge/extractor.py` | extract_text_from_source, _read_text_with_fallbacks, _extract_csv_text, _extract_docx_text, _extract_xlsx_text (+2) |
| `backend/tests/test_rag_workflow_governance.py` | _create_upload, test_knowledge_ingest_success_records_completed_workflow_and_governance, test_knowledge_ingest_parse_failure_marks_workflow_failed |
| `backend/tests/test_knowledge_service.py` | _create_session_and_upload, test_knowledge_service_ingests_uploaded_text_file, test_knowledge_service_marks_unsupported_doc_as_parse_failed |
| `backend/app/session/adapters/sqlite_store.py` | create_uploaded_file, _row_to_uploaded_file |
| `backend/app/session/service.py` | _get_default_knowledge_service, _get_knowledge_service |

## Entry Points

Start here when exploring this area:

- **`test_knowledge_ingest_success_records_completed_workflow_and_governance`** (Function) — `backend/tests/test_rag_workflow_governance.py:72`
- **`test_knowledge_ingest_parse_failure_marks_workflow_failed`** (Function) — `backend/tests/test_rag_workflow_governance.py:119`
- **`test_knowledge_store_supports_items_tasks_chunks_and_session_attachments`** (Function) — `backend/tests/test_knowledge_store.py:13`
- **`test_knowledge_service_ingests_uploaded_text_file`** (Function) — `backend/tests/test_knowledge_service.py:44`
- **`test_knowledge_service_marks_unsupported_doc_as_parse_failed`** (Function) — `backend/tests/test_knowledge_service.py:74`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KnowledgeStore` | Class | `backend/app/knowledge/store.py` | 31 |
| `BaseKnowledgeStore` | Class | `backend/app/knowledge/store.py` | 890 |
| `KnowledgeItemSummary` | Class | `backend/app/knowledge/schemas.py` | 61 |
| `KnowledgeItemDetail` | Class | `backend/app/knowledge/schemas.py` | 109 |
| `test_knowledge_ingest_success_records_completed_workflow_and_governance` | Function | `backend/tests/test_rag_workflow_governance.py` | 72 |
| `test_knowledge_ingest_parse_failure_marks_workflow_failed` | Function | `backend/tests/test_rag_workflow_governance.py` | 119 |
| `test_knowledge_store_supports_items_tasks_chunks_and_session_attachments` | Function | `backend/tests/test_knowledge_store.py` | 13 |
| `test_knowledge_service_ingests_uploaded_text_file` | Function | `backend/tests/test_knowledge_service.py` | 44 |
| `test_knowledge_service_marks_unsupported_doc_as_parse_failed` | Function | `backend/tests/test_knowledge_service.py` | 74 |
| `test_knowledge_task_runner_processes_queued_item` | Function | `backend/tests/test_knowledge_runner.py` | 21 |
| `test_extract_text_from_old_doc_raises_clear_error` | Function | `backend/tests/test_knowledge_extractor.py` | 103 |
| `extract_text_from_source` | Function | `backend/app/knowledge/extractor.py` | 14 |
| `get_knowledge_task_runner` | Function | `backend/app/knowledge/runner.py` | 101 |
| `parse_document` | Function | `backend/app/knowledge/parsers.py` | 18 |
| `chunk_knowledge_text` | Function | `backend/app/knowledge/chunker.py` | 12 |
| `chunk_text_to_knowledge_chunks` | Function | `backend/app/knowledge/chunker.py` | 41 |
| `chunk_utcnow` | Function | `backend/app/knowledge/chunker.py` | 178 |
| `get_knowledge_service` | Function | `backend/app/knowledge/service.py` | 615 |
| `get_item` | Method | `backend/app/knowledge/store.py` | 53 |
| `get_visible_item` | Method | `backend/app/knowledge/store.py` | 59 |

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
| Adapters | 5 calls |
| Rag | 5 calls |
| Tests | 4 calls |
| Retrieval | 3 calls |
| Carbon | 1 calls |
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_knowledge_ingest_success_records_completed_workflow_and_governance"})` — see callers and callees
2. `gitnexus_query({query: "knowledge"})` — find related execution flows
3. Read key files listed above for implementation details
