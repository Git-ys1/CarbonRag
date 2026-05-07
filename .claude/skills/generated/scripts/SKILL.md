---
name: scripts
description: "Skill for the Scripts area of CarbonRag. 15 symbols across 2 files."
---

# Scripts

15 symbols | 2 files | Cohesion: 90%

## When to Use

- Working with code in `scripts/`
- Understanding how run_eval, test_rag_eval_empty_dataset_returns_clear_status, test_rag_eval_runs_single_case_and_reports_metrics work
- Modifying scripts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/rag_eval.py` | run_eval, _evaluate_variant, _metrics_from_case_results, _empty_metrics, _hit_positions (+6) |
| `backend/tests/test_rag_eval_script.py` | test_rag_eval_empty_dataset_returns_clear_status, test_rag_eval_runs_single_case_and_reports_metrics, test_rag_eval_loads_cases_from_json, test_rag_eval_markdown_contains_required_metrics |

## Entry Points

Start here when exploring this area:

- **`run_eval`** (Function) — `scripts/rag_eval.py:54`
- **`test_rag_eval_empty_dataset_returns_clear_status`** (Function) — `backend/tests/test_rag_eval_script.py:12`
- **`test_rag_eval_runs_single_case_and_reports_metrics`** (Function) — `backend/tests/test_rag_eval_script.py:51`
- **`load_eval_cases`** (Function) — `scripts/rag_eval.py:47`
- **`format_markdown`** (Function) — `scripts/rag_eval.py:90`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `run_eval` | Function | `scripts/rag_eval.py` | 54 |
| `test_rag_eval_empty_dataset_returns_clear_status` | Function | `backend/tests/test_rag_eval_script.py` | 12 |
| `test_rag_eval_runs_single_case_and_reports_metrics` | Function | `backend/tests/test_rag_eval_script.py` | 51 |
| `load_eval_cases` | Function | `scripts/rag_eval.py` | 47 |
| `format_markdown` | Function | `scripts/rag_eval.py` | 90 |
| `main` | Function | `scripts/rag_eval.py` | 121 |
| `test_rag_eval_loads_cases_from_json` | Function | `backend/tests/test_rag_eval_script.py` | 20 |
| `test_rag_eval_markdown_contains_required_metrics` | Function | `backend/tests/test_rag_eval_script.py` | 75 |
| `_evaluate_variant` | Function | `scripts/rag_eval.py` | 145 |
| `_metrics_from_case_results` | Function | `scripts/rag_eval.py` | 193 |
| `_empty_metrics` | Function | `scripts/rag_eval.py` | 213 |
| `_hit_positions` | Function | `scripts/rag_eval.py` | 227 |
| `_matches_expected` | Function | `scripts/rag_eval.py` | 235 |
| `_has_hit_at` | Function | `scripts/rag_eval.py` | 251 |
| `_case_from_payload` | Function | `scripts/rag_eval.py` | 256 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _uses_pgvector_backend` | cross_community | 7 |
| `Main → _chunk_source_metadata` | cross_community | 7 |
| `Main → _private_allowed_ids` | cross_community | 6 |
| `Main → _source_type_filter` | cross_community | 6 |
| `Main → _initial_fallback_reason` | cross_community | 5 |
| `Main → _vector_store_health` | cross_community | 5 |
| `Main → _matches_expected` | cross_community | 5 |
| `Main → _empty_metrics` | cross_community | 5 |
| `Main → _has_hit_at` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Rag | 1 calls |

## How to Explore

1. `gitnexus_context({name: "run_eval"})` — see callers and callees
2. `gitnexus_query({query: "scripts"})` — find related execution flows
3. Read key files listed above for implementation details
