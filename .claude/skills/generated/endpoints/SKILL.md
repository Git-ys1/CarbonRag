---
name: endpoints
description: "Skill for the Endpoints area of CarbonRag. 45 symbols across 16 files."
---

# Endpoints

45 symbols | 16 files | Cohesion: 65%

## When to Use

- Working with code in `backend/`
- Understanding how get_report_service, list_sessions, create_report work
- Modifying endpoints-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/api/v1/endpoints/sessions.py` | list_sessions, create_session, update_session_title, empty_source_summary, build_stream_status_payload (+2) |
| `backend/app/api/v1/endpoints/admin.py` | list_admin_private_samples, list_admin_knowledge_items, _clear_private_retrieval_caches, scan_admin_knowledge_tasks, rebuild_admin_knowledge_tasks (+1) |
| `backend/app/report/service.py` | get_report, list_session_reports, list_session_carbon_results, get_report_service, __init__ |
| `backend/app/api/v1/endpoints/reports.py` | create_report, generate_report_alias, get_report, list_session_reports, list_session_carbon_results |
| `backend/app/api/v1/endpoints/knowledge.py` | _sync_user_knowledge, list_knowledge_items, list_knowledge_tasks, _get_bound_session_service, replace_session_knowledge_items |
| `backend/app/session/service.py` | list_sessions, list_private_sample_catalog, get_session_service |
| `backend/app/api/v1/endpoints/me.py` | list_my_reports, list_my_feedback, _fetch_rows |
| `backend/app/private_samples/catalog.py` | list_attachable_private_sample_catalog, list_admin_private_sample_catalog, refresh_private_sample_catalog |
| `backend/app/files/storage.py` | get_file_storage |
| `backend/app/files/service.py` | __init__ |

## Entry Points

Start here when exploring this area:

- **`get_report_service`** (Function) — `backend/app/report/service.py:341`
- **`list_sessions`** (Function) — `backend/app/api/v1/endpoints/sessions.py:451`
- **`create_report`** (Function) — `backend/app/api/v1/endpoints/reports.py:12`
- **`generate_report_alias`** (Function) — `backend/app/api/v1/endpoints/reports.py:29`
- **`get_report`** (Function) — `backend/app/api/v1/endpoints/reports.py:37`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_report_service` | Function | `backend/app/report/service.py` | 341 |
| `list_sessions` | Function | `backend/app/api/v1/endpoints/sessions.py` | 451 |
| `create_report` | Function | `backend/app/api/v1/endpoints/reports.py` | 12 |
| `generate_report_alias` | Function | `backend/app/api/v1/endpoints/reports.py` | 29 |
| `get_report` | Function | `backend/app/api/v1/endpoints/reports.py` | 37 |
| `list_session_reports` | Function | `backend/app/api/v1/endpoints/reports.py` | 68 |
| `list_session_carbon_results` | Function | `backend/app/api/v1/endpoints/reports.py` | 79 |
| `list_my_reports` | Function | `backend/app/api/v1/endpoints/me.py` | 31 |
| `get_session_service` | Function | `backend/app/session/service.py` | 402 |
| `list_attachable_private_sample_catalog` | Function | `backend/app/private_samples/catalog.py` | 86 |
| `get_file_storage` | Function | `backend/app/files/storage.py` | 31 |
| `get_carbon_service` | Function | `backend/app/carbon/service.py` | 661 |
| `create_session` | Function | `backend/app/api/v1/endpoints/sessions.py` | 443 |
| `update_session_title` | Function | `backend/app/api/v1/endpoints/sessions.py` | 467 |
| `list_private_samples` | Function | `backend/app/api/v1/endpoints/private_samples.py` | 12 |
| `calculate_carbon` | Function | `backend/app/api/v1/endpoints/calc_carbon.py` | 12 |
| `list_admin_private_sample_catalog` | Function | `backend/app/private_samples/catalog.py` | 111 |
| `refresh_private_sample_catalog` | Function | `backend/app/private_samples/catalog.py` | 141 |
| `list_knowledge_items` | Function | `backend/app/api/v1/endpoints/knowledge.py` | 33 |
| `list_knowledge_tasks` | Function | `backend/app/api/v1/endpoints/knowledge.py` | 74 |

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
| Tests | 4 calls |
| Retrieval | 3 calls |
| Report | 1 calls |
| Admin | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_report_service"})` — see callers and callees
2. `gitnexus_query({query: "endpoints"})` — find related execution flows
3. Read key files listed above for implementation details
