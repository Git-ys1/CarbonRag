---
name: admin
description: "Skill for the Admin area of CarbonRag. 25 symbols across 2 files."
---

# Admin

25 symbols | 2 files | Cohesion: 74%

## When to Use

- Working with code in `backend/`
- Understanding how update_admin_private_sample, trigger_knowledge_refresh_task, update_admin_knowledge_item work
- Modifying admin-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/admin/service.py` | _utcnow, update_private_sample, update_knowledge_item, trigger_knowledge_scan, trigger_knowledge_rebuild (+12) |
| `backend/app/api/v1/endpoints/admin.py` | update_admin_private_sample, trigger_knowledge_refresh_task, update_admin_knowledge_item, list_admin_users, update_admin_user (+3) |

## Entry Points

Start here when exploring this area:

- **`update_admin_private_sample`** (Function) — `backend/app/api/v1/endpoints/admin.py:89`
- **`trigger_knowledge_refresh_task`** (Function) — `backend/app/api/v1/endpoints/admin.py:116`
- **`update_admin_knowledge_item`** (Function) — `backend/app/api/v1/endpoints/admin.py:146`
- **`get_admin_service`** (Function) — `backend/app/admin/service.py:452`
- **`list_admin_users`** (Function) — `backend/app/api/v1/endpoints/admin.py:38`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `update_admin_private_sample` | Function | `backend/app/api/v1/endpoints/admin.py` | 89 |
| `trigger_knowledge_refresh_task` | Function | `backend/app/api/v1/endpoints/admin.py` | 116 |
| `update_admin_knowledge_item` | Function | `backend/app/api/v1/endpoints/admin.py` | 146 |
| `get_admin_service` | Function | `backend/app/admin/service.py` | 452 |
| `list_admin_users` | Function | `backend/app/api/v1/endpoints/admin.py` | 38 |
| `update_admin_user` | Function | `backend/app/api/v1/endpoints/admin.py` | 46 |
| `reset_admin_user_password` | Function | `backend/app/api/v1/endpoints/admin.py` | 60 |
| `list_knowledge_refresh_tasks` | Function | `backend/app/api/v1/endpoints/admin.py` | 108 |
| `get_admin_feedback_overview` | Function | `backend/app/api/v1/endpoints/admin.py` | 73 |
| `update_private_sample` | Method | `backend/app/admin/service.py` | 168 |
| `update_knowledge_item` | Method | `backend/app/admin/service.py` | 207 |
| `trigger_knowledge_scan` | Method | `backend/app/admin/service.py` | 234 |
| `trigger_knowledge_rebuild` | Method | `backend/app/admin/service.py` | 244 |
| `retry_knowledge_task` | Method | `backend/app/admin/service.py` | 251 |
| `trigger_knowledge_refresh` | Method | `backend/app/admin/service.py` | 265 |
| `list_users` | Method | `backend/app/admin/service.py` | 67 |
| `update_user` | Method | `backend/app/admin/service.py` | 91 |
| `reset_password` | Method | `backend/app/admin/service.py` | 94 |
| `list_knowledge_refresh_tasks` | Method | `backend/app/admin/service.py` | 262 |
| `get_feedback_overview` | Method | `backend/app/admin/service.py` | 97 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Trigger_knowledge_refresh_task → Get_settings` | cross_community | 10 |
| `Trigger_knowledge_refresh_task → Load_local_chat_provider_override` | cross_community | 10 |
| `Update_admin_private_sample → Get_settings` | cross_community | 9 |
| `Update_admin_private_sample → Load_local_chat_provider_override` | cross_community | 9 |
| `Trigger_knowledge_refresh_task → _compute_sha256` | cross_community | 7 |
| `Update_admin_private_sample → _compute_sha256` | cross_community | 6 |
| `Update_admin_user → Connect_postgres` | cross_community | 5 |
| `List_admin_users → Connect_postgres` | cross_community | 5 |
| `Get_admin_system_status → Connect_postgres` | cross_community | 4 |
| `Get_admin_feedback_overview → Connect_postgres` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Endpoints | 4 calls |

## How to Explore

1. `gitnexus_context({name: "update_admin_private_sample"})` — see callers and callees
2. `gitnexus_query({query: "admin"})` — find related execution flows
3. Read key files listed above for implementation details
