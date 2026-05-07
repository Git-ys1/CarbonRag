---
name: carbon
description: "Skill for the Carbon area of CarbonRag. 57 symbols across 26 files."
---

# Carbon

57 symbols | 26 files | Cohesion: 87%

## When to Use

- Working with code in `backend/`
- Understanding how test_settings_read_database_url_and_upload_dir, test_bootstrap_runtime_database_creates_sqlite_schema, test_bootstrap_runtime_database_executes_postgres_schema work
- Modifying carbon-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/carbon/factor_loader.py` | resolve_factor_file, resolve_v2_factor_file, resolve_v2_factor_files, __init__, get_factor_loader (+7) |
| `backend/app/carbon/service.py` | __init__, _persist, _persist_inventory_sqlite, _persist_inventory_postgres, _persist_inventory_common (+1) |
| `backend/app/carbon/engine.py` | _round_value, calculate, _build_source_summary, _build_scope_summary |
| `backend/app/runtime_db/bootstrap.py` | get_runtime_backend_kind, bootstrap_runtime_database, main |
| `backend/app/memory/store.py` | resolve_memory_backend, __init__, get_memory_store |
| `backend/app/knowledge/store.py` | __init__, build_knowledge_store, get_default_knowledge_store |
| `backend/tests/test_runtime_db_bootstrap.py` | test_bootstrap_runtime_database_creates_sqlite_schema, test_bootstrap_runtime_database_executes_postgres_schema |
| `backend/app/settings/storage.py` | __init__, get_settings_storage |
| `backend/app/private_samples/overrides.py` | _connect, update_private_sample_override |
| `backend/app/files/storage.py` | resolve_upload_root, __init__ |

## Entry Points

Start here when exploring this area:

- **`test_settings_read_database_url_and_upload_dir`** (Function) — `backend/tests/test_runtime_settings_and_store.py:4`
- **`test_bootstrap_runtime_database_creates_sqlite_schema`** (Function) — `backend/tests/test_runtime_db_bootstrap.py:34`
- **`test_bootstrap_runtime_database_executes_postgres_schema`** (Function) — `backend/tests/test_runtime_db_bootstrap.py:66`
- **`test_default_ask_params_do_not_enable_experimental_workflow_modes`** (Function) — `backend/tests/test_rag_workflow_governance.py:199`
- **`get_settings_storage`** (Function) — `backend/app/settings/storage.py:318`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_settings_read_database_url_and_upload_dir` | Function | `backend/tests/test_runtime_settings_and_store.py` | 4 |
| `test_bootstrap_runtime_database_creates_sqlite_schema` | Function | `backend/tests/test_runtime_db_bootstrap.py` | 34 |
| `test_bootstrap_runtime_database_executes_postgres_schema` | Function | `backend/tests/test_runtime_db_bootstrap.py` | 66 |
| `test_default_ask_params_do_not_enable_experimental_workflow_modes` | Function | `backend/tests/test_rag_workflow_governance.py` | 199 |
| `get_settings_storage` | Function | `backend/app/settings/storage.py` | 318 |
| `ensure_postgres_schema` | Function | `backend/app/runtime_db/schema.py` | 1114 |
| `get_runtime_backend_kind` | Function | `backend/app/runtime_db/bootstrap.py` | 10 |
| `bootstrap_runtime_database` | Function | `backend/app/runtime_db/bootstrap.py` | 14 |
| `main` | Function | `backend/app/runtime_db/bootstrap.py` | 36 |
| `build_rag_query_params` | Function | `backend/app/rag/service.py` | 648 |
| `get_parser_registry` | Function | `backend/app/rag/parser.py` | 786 |
| `update_private_sample_override` | Function | `backend/app/private_samples/overrides.py` | 53 |
| `resolve_memory_backend` | Function | `backend/app/memory/store.py` | 15 |
| `get_memory_store` | Function | `backend/app/memory/store.py` | 390 |
| `resolve_upload_root` | Function | `backend/app/files/storage.py` | 7 |
| `build_knowledge_store` | Function | `backend/app/knowledge/store.py` | 898 |
| `get_default_knowledge_store` | Function | `backend/app/knowledge/store.py` | 927 |
| `get_settings` | Function | `backend/app/core/config.py` | 62 |
| `resolve_factor_file` | Function | `backend/app/carbon/factor_loader.py` | 10 |
| `resolve_v2_factor_file` | Function | `backend/app/carbon/factor_loader.py` | 20 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Trigger_knowledge_refresh_task → Get_settings` | cross_community | 10 |
| `Get_admin_system_status → Get_settings` | cross_community | 9 |
| `Update_admin_private_sample → Get_settings` | cross_community | 9 |
| `List_private_samples → Get_settings` | cross_community | 8 |
| `List_admin_private_samples → Get_settings` | cross_community | 8 |
| `List_knowledge_items → Get_settings` | cross_community | 8 |
| `List_knowledge_tasks → Get_settings` | cross_community | 8 |
| `List_admin_knowledge_items → Get_settings` | cross_community | 7 |
| `Trigger_scan → Get_settings` | cross_community | 7 |
| `Ask_in_session_stream → Get_settings` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 5 calls |
| Endpoints | 4 calls |
| Auth | 2 calls |
| Runtime_db | 1 calls |
| Providers | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_settings_read_database_url_and_upload_dir"})` — see callers and callees
2. `gitnexus_query({query: "carbon"})` — find related execution flows
3. Read key files listed above for implementation details
