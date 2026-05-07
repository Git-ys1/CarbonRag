---
name: memory
description: "Skill for the Memory area of CarbonRag. 38 symbols across 5 files."
---

# Memory

38 symbols | 5 files | Cohesion: 92%

## When to Use

- Working with code in `backend/`
- Understanding how test_memory_store_sqlite_can_read_write_notes_with_fallback_path, patch_fake_postgres, test_memory_store_postgres_initializes_without_sqlite_path work
- Modifying memory-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/memory/service.py` | list_notes, get_session_memory_state, build_session_context, _maybe_compact, _generate_extractive_summary (+12) |
| `backend/app/memory/store.py` | list_notes, create_note, update_note, delete_note, get_note (+7) |
| `backend/tests/test_memory_store_postgres.py` | patch_fake_postgres, test_memory_store_postgres_initializes_without_sqlite_path, test_build_memory_store_defaults_to_postgres_with_database_url, test_memory_store_postgres_can_read_write_notes |
| `backend/app/api/v1/endpoints/memory.py` | list_memory_notes, create_memory_note, update_memory_note, delete_memory_note |
| `backend/tests/test_memory_store_sqlite.py` | test_memory_store_sqlite_can_read_write_notes_with_fallback_path |

## Entry Points

Start here when exploring this area:

- **`test_memory_store_sqlite_can_read_write_notes_with_fallback_path`** (Function) — `backend/tests/test_memory_store_sqlite.py:26`
- **`patch_fake_postgres`** (Function) — `backend/tests/test_memory_store_postgres.py:110`
- **`test_memory_store_postgres_initializes_without_sqlite_path`** (Function) — `backend/tests/test_memory_store_postgres.py:116`
- **`test_build_memory_store_defaults_to_postgres_with_database_url`** (Function) — `backend/tests/test_memory_store_postgres.py:131`
- **`test_memory_store_postgres_can_read_write_notes`** (Function) — `backend/tests/test_memory_store_postgres.py:145`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_memory_store_sqlite_can_read_write_notes_with_fallback_path` | Function | `backend/tests/test_memory_store_sqlite.py` | 26 |
| `patch_fake_postgres` | Function | `backend/tests/test_memory_store_postgres.py` | 110 |
| `test_memory_store_postgres_initializes_without_sqlite_path` | Function | `backend/tests/test_memory_store_postgres.py` | 116 |
| `test_build_memory_store_defaults_to_postgres_with_database_url` | Function | `backend/tests/test_memory_store_postgres.py` | 131 |
| `test_memory_store_postgres_can_read_write_notes` | Function | `backend/tests/test_memory_store_postgres.py` | 145 |
| `utcnow` | Function | `backend/app/memory/service.py` | 21 |
| `get_memory_service` | Function | `backend/app/memory/service.py` | 329 |
| `list_memory_notes` | Function | `backend/app/api/v1/endpoints/memory.py` | 11 |
| `create_memory_note` | Function | `backend/app/api/v1/endpoints/memory.py` | 16 |
| `update_memory_note` | Function | `backend/app/api/v1/endpoints/memory.py` | 24 |
| `delete_memory_note` | Function | `backend/app/api/v1/endpoints/memory.py` | 40 |
| `list_notes` | Method | `backend/app/memory/store.py` | 53 |
| `create_note` | Method | `backend/app/memory/store.py` | 58 |
| `update_note` | Method | `backend/app/memory/store.py` | 98 |
| `delete_note` | Method | `backend/app/memory/store.py` | 147 |
| `get_note` | Method | `backend/app/memory/store.py` | 163 |
| `get_session_memory_snapshot` | Method | `backend/app/memory/store.py` | 180 |
| `count_compacted_messages` | Method | `backend/app/memory/store.py` | 247 |
| `update_session_memory` | Method | `backend/app/memory/store.py` | 278 |
| `list_notes` | Method | `backend/app/memory/service.py` | 32 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Ask_in_session_stream → Get_memory_service` | cross_community | 6 |
| `Upload_file → Get_memory_service` | cross_community | 6 |
| `Replace_attached_private_samples → Get_memory_service` | cross_community | 6 |
| `Update_session_title → Get_memory_service` | cross_community | 6 |
| `List_session_knowledge_items → Get_memory_service` | cross_community | 6 |
| `Build_chat_request → Get_memory_service` | cross_community | 6 |
| `Replace_attached_private_samples → Get_memory_service` | cross_community | 6 |
| `Emit_terminal_stream_error → Get_memory_service` | cross_community | 5 |
| `Record_system_message → Get_memory_service` | cross_community | 5 |
| `Record_uploaded_file → Get_memory_service` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 2 calls |
| Settings | 1 calls |
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_memory_store_sqlite_can_read_write_notes_with_fallback_path"})` — see callers and callees
2. `gitnexus_query({query: "memory"})` — find related execution flows
3. Read key files listed above for implementation details
