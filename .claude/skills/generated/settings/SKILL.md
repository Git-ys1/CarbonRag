---
name: settings
description: "Skill for the Settings area of CarbonRag. 39 symbols across 6 files."
---

# Settings

39 symbols | 6 files | Cohesion: 72%

## When to Use

- Working with code in `backend/`
- Understanding how utcnow_iso, get_settings_service, get_settings work
- Modifying settings-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/settings/service.py` | utcnow_iso, get_user_settings, update_user_settings, list_provider_profiles, update_provider_profile (+11) |
| `backend/app/settings/storage.py` | _connect, get_user_settings, upsert_user_settings, list_provider_profiles, get_provider_profile (+4) |
| `backend/app/api/v1/endpoints/settings.py` | get_settings, patch_settings, list_provider_profiles, update_provider_profile, delete_provider_profile (+3) |
| `backend/app/settings/crypto.py` | _build_fernet, encrypt_secret, decrypt_secret |
| `backend/app/ai_runtime/config.py` | load_local_chat_provider_override, get_ai_runtime_config |
| `backend/app/memory/service.py` | _generate_summary |

## Entry Points

Start here when exploring this area:

- **`utcnow_iso`** (Function) — `backend/app/settings/service.py:34`
- **`get_settings_service`** (Function) — `backend/app/settings/service.py:348`
- **`get_settings`** (Function) — `backend/app/api/v1/endpoints/settings.py:20`
- **`patch_settings`** (Function) — `backend/app/api/v1/endpoints/settings.py:25`
- **`list_provider_profiles`** (Function) — `backend/app/api/v1/endpoints/settings.py:33`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `utcnow_iso` | Function | `backend/app/settings/service.py` | 34 |
| `get_settings_service` | Function | `backend/app/settings/service.py` | 348 |
| `get_settings` | Function | `backend/app/api/v1/endpoints/settings.py` | 20 |
| `patch_settings` | Function | `backend/app/api/v1/endpoints/settings.py` | 25 |
| `list_provider_profiles` | Function | `backend/app/api/v1/endpoints/settings.py` | 33 |
| `update_provider_profile` | Function | `backend/app/api/v1/endpoints/settings.py` | 49 |
| `delete_provider_profile` | Function | `backend/app/api/v1/endpoints/settings.py` | 68 |
| `discover_models` | Function | `backend/app/api/v1/endpoints/settings.py` | 88 |
| `build_chat_provider_from_resolved` | Function | `backend/app/settings/service.py` | 295 |
| `encrypt_secret` | Function | `backend/app/settings/crypto.py` | 14 |
| `decrypt_secret` | Function | `backend/app/settings/crypto.py` | 20 |
| `create_provider_profile` | Function | `backend/app/api/v1/endpoints/settings.py` | 38 |
| `discover_models_for_connection` | Function | `backend/app/settings/service.py` | 247 |
| `load_local_chat_provider_override` | Function | `backend/app/ai_runtime/config.py` | 46 |
| `get_ai_runtime_config` | Function | `backend/app/ai_runtime/config.py` | 59 |
| `test_provider_connection` | Function | `backend/app/api/v1/endpoints/settings.py` | 79 |
| `get_user_settings` | Method | `backend/app/settings/service.py` | 69 |
| `update_user_settings` | Method | `backend/app/settings/service.py` | 84 |
| `list_provider_profiles` | Method | `backend/app/settings/service.py` | 103 |
| `update_provider_profile` | Method | `backend/app/settings/service.py` | 128 |

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
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "utcnow_iso"})` — see callers and callees
2. `gitnexus_query({query: "settings"})` — find related execution flows
3. Read key files listed above for implementation details
