---
name: tools
description: "Skill for the Tools area of CarbonRag. 18 symbols across 11 files."
---

# Tools

18 symbols | 11 files | Cohesion: 100%

## When to Use

- Working with code in `backend/`
- Understanding how test_policy_retrieve_tool_is_registered_in_default_registry, test_default_registry_contains_all_stub_tools, test_registry_rejects_duplicate_registration work
- Modifying tools-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/ai_runtime/tools/registry.py` | register, get, list_tool_names, invoke, build_default_registry |
| `backend/tests/test_ai_runtime_registry.py` | test_default_registry_contains_all_stub_tools, test_registry_rejects_duplicate_registration, test_registry_raises_for_unknown_tool |
| `backend/app/ai_runtime/tools/base.py` | invoke, BaseTool |
| `backend/tests/test_policy_retrieve_tool.py` | test_policy_retrieve_tool_is_registered_in_default_registry |
| `backend/app/ai_runtime/tools/report_draft_stub.py` | ReportDraftStubTool |
| `backend/app/ai_runtime/tools/policy_retrieve.py` | PolicyRetrieveTool |
| `backend/app/ai_runtime/tools/mixed_retrieve.py` | MixedRetrieveTool |
| `backend/app/ai_runtime/tools/enterprise_retrieve_stub.py` | EnterpriseRetrieveStubTool |
| `backend/app/ai_runtime/tools/enterprise_retrieve.py` | EnterpriseRetrieveTool |
| `backend/app/ai_runtime/tools/carbon_factor_lookup_stub.py` | CarbonFactorLookupStubTool |

## Entry Points

Start here when exploring this area:

- **`test_policy_retrieve_tool_is_registered_in_default_registry`** (Function) — `backend/tests/test_policy_retrieve_tool.py:31`
- **`test_default_registry_contains_all_stub_tools`** (Function) — `backend/tests/test_ai_runtime_registry.py:6`
- **`test_registry_rejects_duplicate_registration`** (Function) — `backend/tests/test_ai_runtime_registry.py:19`
- **`test_registry_raises_for_unknown_tool`** (Function) — `backend/tests/test_ai_runtime_registry.py:27`
- **`build_default_registry`** (Function) — `backend/app/ai_runtime/tools/registry.py:33`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ReportDraftStubTool` | Class | `backend/app/ai_runtime/tools/report_draft_stub.py` | 6 |
| `PolicyRetrieveTool` | Class | `backend/app/ai_runtime/tools/policy_retrieve.py` | 7 |
| `MixedRetrieveTool` | Class | `backend/app/ai_runtime/tools/mixed_retrieve.py` | 7 |
| `EnterpriseRetrieveStubTool` | Class | `backend/app/ai_runtime/tools/enterprise_retrieve_stub.py` | 6 |
| `EnterpriseRetrieveTool` | Class | `backend/app/ai_runtime/tools/enterprise_retrieve.py` | 7 |
| `CarbonFactorLookupStubTool` | Class | `backend/app/ai_runtime/tools/carbon_factor_lookup_stub.py` | 6 |
| `CarbonCalcStubTool` | Class | `backend/app/ai_runtime/tools/carbon_calc_stub.py` | 6 |
| `BaseTool` | Class | `backend/app/ai_runtime/tools/base.py` | 14 |
| `test_policy_retrieve_tool_is_registered_in_default_registry` | Function | `backend/tests/test_policy_retrieve_tool.py` | 31 |
| `test_default_registry_contains_all_stub_tools` | Function | `backend/tests/test_ai_runtime_registry.py` | 6 |
| `test_registry_rejects_duplicate_registration` | Function | `backend/tests/test_ai_runtime_registry.py` | 19 |
| `test_registry_raises_for_unknown_tool` | Function | `backend/tests/test_ai_runtime_registry.py` | 27 |
| `build_default_registry` | Function | `backend/app/ai_runtime/tools/registry.py` | 33 |
| `register` | Method | `backend/app/ai_runtime/tools/registry.py` | 13 |
| `get` | Method | `backend/app/ai_runtime/tools/registry.py` | 19 |
| `list_tool_names` | Method | `backend/app/ai_runtime/tools/registry.py` | 25 |
| `invoke` | Method | `backend/app/ai_runtime/tools/registry.py` | 28 |
| `invoke` | Method | `backend/app/ai_runtime/tools/base.py` | 21 |

## How to Explore

1. `gitnexus_context({name: "test_policy_retrieve_tool_is_registered_in_default_registry"})` — see callers and callees
2. `gitnexus_query({query: "tools"})` — find related execution flows
3. Read key files listed above for implementation details
