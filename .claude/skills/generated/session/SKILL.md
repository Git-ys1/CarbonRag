---
name: session
description: "Skill for the Session area of CarbonRag. 26 symbols across 5 files."
---

# Session

26 symbols | 5 files | Cohesion: 63%

## When to Use

- Working with code in `backend/`
- Understanding how get_active_stream_registry, build_sse_event, ask_in_session_stream work
- Modifying session-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/session/service.py` | utcnow, require_session, begin_exchange, finalize_exchange, record_system_message (+6) |
| `backend/app/session/streaming.py` | subscribe, get, create, _cleanup, get_active_stream_registry (+2) |
| `backend/app/api/v1/endpoints/sessions.py` | build_sse_event, ask_in_session_stream, event_stream, resolve_final_message_status, run_stream_worker |
| `backend/app/session/schemas.py` | SessionSummary, SessionDetail |
| `backend/app/api/v1/endpoints/private_samples.py` | replace_attached_private_samples |

## Entry Points

Start here when exploring this area:

- **`get_active_stream_registry`** (Function) — `backend/app/session/streaming.py:138`
- **`build_sse_event`** (Function) — `backend/app/api/v1/endpoints/sessions.py:109`
- **`ask_in_session_stream`** (Function) — `backend/app/api/v1/endpoints/sessions.py:570`
- **`event_stream`** (Function) — `backend/app/api/v1/endpoints/sessions.py:621`
- **`utcnow`** (Function) — `backend/app/session/service.py:16`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SessionSummary` | Class | `backend/app/session/schemas.py` | 40 |
| `SessionDetail` | Class | `backend/app/session/schemas.py` | 51 |
| `get_active_stream_registry` | Function | `backend/app/session/streaming.py` | 138 |
| `build_sse_event` | Function | `backend/app/api/v1/endpoints/sessions.py` | 109 |
| `ask_in_session_stream` | Function | `backend/app/api/v1/endpoints/sessions.py` | 570 |
| `event_stream` | Function | `backend/app/api/v1/endpoints/sessions.py` | 621 |
| `utcnow` | Function | `backend/app/session/service.py` | 16 |
| `replace_attached_private_samples` | Function | `backend/app/api/v1/endpoints/private_samples.py` | 19 |
| `is_retryable_provider_error` | Function | `backend/app/session/streaming.py` | 13 |
| `get_retry_delay` | Function | `backend/app/session/streaming.py` | 25 |
| `resolve_final_message_status` | Function | `backend/app/api/v1/endpoints/sessions.py` | 113 |
| `run_stream_worker` | Function | `backend/app/api/v1/endpoints/sessions.py` | 202 |
| `subscribe` | Method | `backend/app/session/streaming.py` | 69 |
| `get` | Method | `backend/app/session/streaming.py` | 95 |
| `create` | Method | `backend/app/session/streaming.py` | 100 |
| `require_session` | Method | `backend/app/session/service.py` | 58 |
| `begin_exchange` | Method | `backend/app/session/service.py` | 133 |
| `finalize_exchange` | Method | `backend/app/session/service.py` | 159 |
| `record_system_message` | Method | `backend/app/session/service.py` | 257 |
| `record_uploaded_file` | Method | `backend/app/session/service.py` | 267 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Ask_in_session_stream → Get_settings` | cross_community | 6 |
| `Ask_in_session_stream → Build_memory_store` | cross_community | 6 |
| `Ask_in_session_stream → Get_memory_service` | cross_community | 6 |
| `Upload_file → Get_settings` | cross_community | 6 |
| `Upload_file → Build_memory_store` | cross_community | 6 |
| `Upload_file → Get_memory_service` | cross_community | 6 |
| `Replace_attached_private_samples → Get_settings` | cross_community | 6 |
| `Replace_attached_private_samples → Build_memory_store` | cross_community | 6 |
| `Replace_attached_private_samples → Get_memory_service` | cross_community | 6 |
| `Update_session_title → Get_settings` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 9 calls |
| Endpoints | 5 calls |
| Settings | 3 calls |

## How to Explore

1. `gitnexus_context({name: "get_active_stream_registry"})` — see callers and callees
2. `gitnexus_query({query: "session"})` — find related execution flows
3. Read key files listed above for implementation details
