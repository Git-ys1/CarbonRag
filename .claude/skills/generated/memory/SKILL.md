---
name: memory
description: "Skill for the Memory area of CarbonRag. 29 symbols across 3 files."
---

# Memory

29 symbols | 3 files | Cohesion: 88%

## When to Use

- Working with code in `backend/`
- Understanding how utcnow, get_memory_service, list_memory_notes work
- Modifying memory-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/memory/service.py` | list_notes, get_session_memory_state, build_session_context, _maybe_compact, _generate_extractive_summary (+12) |
| `backend/app/memory/store.py` | update_note, delete_note, get_note, get_session_memory_snapshot, count_compacted_messages (+3) |
| `backend/app/api/v1/endpoints/memory.py` | list_memory_notes, create_memory_note, update_memory_note, delete_memory_note |

## Entry Points

Start here when exploring this area:

- **`utcnow`** (Function) — `backend/app/memory/service.py:21`
- **`get_memory_service`** (Function) — `backend/app/memory/service.py:329`
- **`list_memory_notes`** (Function) — `backend/app/api/v1/endpoints/memory.py:11`
- **`create_memory_note`** (Function) — `backend/app/api/v1/endpoints/memory.py:16`
- **`update_memory_note`** (Function) — `backend/app/api/v1/endpoints/memory.py:24`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `utcnow` | Function | `backend/app/memory/service.py` | 21 |
| `get_memory_service` | Function | `backend/app/memory/service.py` | 329 |
| `list_memory_notes` | Function | `backend/app/api/v1/endpoints/memory.py` | 11 |
| `create_memory_note` | Function | `backend/app/api/v1/endpoints/memory.py` | 16 |
| `update_memory_note` | Function | `backend/app/api/v1/endpoints/memory.py` | 24 |
| `delete_memory_note` | Function | `backend/app/api/v1/endpoints/memory.py` | 40 |
| `list_notes` | Method | `backend/app/memory/service.py` | 32 |
| `get_session_memory_state` | Method | `backend/app/memory/service.py` | 59 |
| `build_session_context` | Method | `backend/app/memory/service.py` | 65 |
| `estimate_text_tokens` | Method | `backend/app/memory/service.py` | 319 |
| `create_note` | Method | `backend/app/memory/service.py` | 36 |
| `update_note` | Method | `backend/app/memory/service.py` | 46 |
| `delete_note` | Method | `backend/app/memory/service.py` | 56 |
| `update_note` | Method | `backend/app/memory/store.py` | 98 |
| `delete_note` | Method | `backend/app/memory/store.py` | 147 |
| `get_note` | Method | `backend/app/memory/store.py` | 163 |
| `get_session_memory_snapshot` | Method | `backend/app/memory/store.py` | 180 |
| `count_compacted_messages` | Method | `backend/app/memory/store.py` | 247 |
| `update_session_memory` | Method | `backend/app/memory/store.py` | 278 |
| `_maybe_compact` | Method | `backend/app/memory/service.py` | 106 |

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
| Settings | 1 calls |
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "utcnow"})` — see callers and callees
2. `gitnexus_query({query: "memory"})` — find related execution flows
3. Read key files listed above for implementation details
