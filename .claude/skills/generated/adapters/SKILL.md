---
name: adapters
description: "Skill for the Adapters area of CarbonRag. 48 symbols across 5 files."
---

# Adapters

48 symbols | 5 files | Cohesion: 92%

## When to Use

- Working with code in `backend/`
- Understanding how test_postgres_session_store_persists_message_and_file, test_sqlite_session_store_persists_after_reopen, test_sqlite_session_store_lists_sessions_by_updated_at_desc work
- Modifying adapters-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/session/adapters/postgres_store.py` | _connect, create_session, list_sessions, get_session, update_session_title (+18) |
| `backend/app/session/adapters/sqlite_store.py` | _connect, create_session, list_sessions, get_session, update_session_title (+16) |
| `backend/tests/test_session_store.py` | test_sqlite_session_store_persists_after_reopen, test_sqlite_session_store_lists_sessions_by_updated_at_desc |
| `backend/tests/test_postgres_runtime_mode.py` | test_postgres_session_store_persists_message_and_file |
| `backend/app/session/store.py` | SessionStore |

## Entry Points

Start here when exploring this area:

- **`test_postgres_session_store_persists_message_and_file`** (Function) — `backend/tests/test_postgres_runtime_mode.py:627`
- **`test_sqlite_session_store_persists_after_reopen`** (Function) — `backend/tests/test_session_store.py:4`
- **`test_sqlite_session_store_lists_sessions_by_updated_at_desc`** (Function) — `backend/tests/test_session_store.py:41`
- **`SessionStore`** (Class) — `backend/app/session/store.py:13`
- **`SQLiteSessionStore`** (Class) — `backend/app/session/adapters/sqlite_store.py:18`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SessionStore` | Class | `backend/app/session/store.py` | 13 |
| `SQLiteSessionStore` | Class | `backend/app/session/adapters/sqlite_store.py` | 18 |
| `PostgreSQLSessionStore` | Class | `backend/app/session/adapters/postgres_store.py` | 17 |
| `test_postgres_session_store_persists_message_and_file` | Function | `backend/tests/test_postgres_runtime_mode.py` | 627 |
| `test_sqlite_session_store_persists_after_reopen` | Function | `backend/tests/test_session_store.py` | 4 |
| `test_sqlite_session_store_lists_sessions_by_updated_at_desc` | Function | `backend/tests/test_session_store.py` | 41 |
| `create_session` | Method | `backend/app/session/adapters/postgres_store.py` | 25 |
| `list_sessions` | Method | `backend/app/session/adapters/postgres_store.py` | 45 |
| `get_session` | Method | `backend/app/session/adapters/postgres_store.py` | 87 |
| `update_session_title` | Method | `backend/app/session/adapters/postgres_store.py` | 176 |
| `update_session_runtime_state` | Method | `backend/app/session/adapters/postgres_store.py` | 196 |
| `append_message` | Method | `backend/app/session/adapters/postgres_store.py` | 228 |
| `update_message` | Method | `backend/app/session/adapters/postgres_store.py` | 276 |
| `list_recent_messages` | Method | `backend/app/session/adapters/postgres_store.py` | 316 |
| `session_exists` | Method | `backend/app/session/adapters/postgres_store.py` | 334 |
| `create_uploaded_file` | Method | `backend/app/session/adapters/postgres_store.py` | 344 |
| `replace_attached_private_samples` | Method | `backend/app/session/adapters/postgres_store.py` | 382 |
| `replace_attached_knowledge_items` | Method | `backend/app/session/adapters/postgres_store.py` | 402 |
| `list_attached_private_sample_ids` | Method | `backend/app/session/adapters/postgres_store.py` | 426 |
| `list_attached_knowledge_item_ids` | Method | `backend/app/session/adapters/postgres_store.py` | 429 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get_session → Connect_postgres` | cross_community | 4 |
| `Get_session → _connect` | intra_community | 3 |
| `Get_session → _row_to_session_summary` | intra_community | 3 |
| `Get_session → _row_to_session_summary` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 4 calls |
| Knowledge | 2 calls |
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_postgres_session_store_persists_message_and_file"})` — see callers and callees
2. `gitnexus_query({query: "adapters"})` — find related execution flows
3. Read key files listed above for implementation details
