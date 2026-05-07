---
name: report
description: "Skill for the Report area of CarbonRag. 21 symbols across 7 files."
---

# Report

21 symbols | 7 files | Cohesion: 82%

## When to Use

- Working with code in `backend/`
- Understanding how get_report_template, utcnow, parse_report_generation_payload work
- Modifying report-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/report/service.py` | utcnow, create_report, update_report, _resolve_selected_messages, _resolve_carbon_result (+3) |
| `backend/app/report/storage.py` | _connect, create_report, get_report, update_report, list_session_reports (+1) |
| `backend/app/report/renderer.py` | parse_report_generation_payload, render_markdown_report |
| `backend/app/report/composer.py` | collect_message_citations, _from_ask_citation |
| `backend/app/report/templates.py` | get_report_template |
| `backend/app/api/v1/endpoints/reports.py` | update_report |
| `backend/tests/test_report_storage.py` | test_report_storage_persists_and_reload_report |

## Entry Points

Start here when exploring this area:

- **`get_report_template`** (Function) — `backend/app/report/templates.py:51`
- **`utcnow`** (Function) — `backend/app/report/service.py:47`
- **`parse_report_generation_payload`** (Function) — `backend/app/report/renderer.py:10`
- **`render_markdown_report`** (Function) — `backend/app/report/renderer.py:43`
- **`update_report`** (Function) — `backend/app/api/v1/endpoints/reports.py:48`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_report_template` | Function | `backend/app/report/templates.py` | 51 |
| `utcnow` | Function | `backend/app/report/service.py` | 47 |
| `parse_report_generation_payload` | Function | `backend/app/report/renderer.py` | 10 |
| `render_markdown_report` | Function | `backend/app/report/renderer.py` | 43 |
| `update_report` | Function | `backend/app/api/v1/endpoints/reports.py` | 48 |
| `test_report_storage_persists_and_reload_report` | Function | `backend/tests/test_report_storage.py` | 8 |
| `create_report` | Method | `backend/app/report/service.py` | 65 |
| `update_report` | Method | `backend/app/report/service.py` | 159 |
| `create_report` | Method | `backend/app/report/storage.py` | 36 |
| `get_report` | Method | `backend/app/report/storage.py` | 124 |
| `update_report` | Method | `backend/app/report/storage.py` | 164 |
| `list_session_reports` | Method | `backend/app/report/storage.py` | 206 |
| `collect_message_citations` | Method | `backend/app/report/composer.py` | 14 |
| `_resolve_selected_messages` | Method | `backend/app/report/service.py` | 177 |
| `_resolve_carbon_result` | Method | `backend/app/report/service.py` | 198 |
| `_pick_default_message` | Method | `backend/app/report/service.py` | 225 |
| `_validate_sources` | Method | `backend/app/report/service.py` | 258 |
| `_build_sources` | Method | `backend/app/report/service.py` | 300 |
| `_connect` | Method | `backend/app/report/storage.py` | 28 |
| `_row_to_report_detail` | Method | `backend/app/report/storage.py` | 262 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Generate_report_alias → _pick_default_message` | cross_community | 5 |
| `Generate_report_alias → _resolve_carbon_result` | cross_community | 4 |
| `Generate_report_alias → _validate_sources` | cross_community | 4 |
| `Generate_report_alias → _build_sources` | cross_community | 4 |
| `Update_report → Connect_postgres` | cross_community | 4 |
| `Update_report → Utcnow` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Adapters | 1 calls |
| Tests | 1 calls |
| Carbon | 1 calls |
| Providers | 1 calls |
| Endpoints | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_report_template"})` — see callers and callees
2. `gitnexus_query({query: "report"})` — find related execution flows
3. Read key files listed above for implementation details
