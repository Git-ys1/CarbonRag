---
name: raglabpage
description: "Skill for the RagLabPage area of CarbonRag. 21 symbols across 2 files."
---

# RagLabPage

21 symbols | 2 files | Cohesion: 80%

## When to Use

- Working with code in `frontend/`
- Understanding how RagLabPage, patchForm, retrieveRagEvidence work
- Modifying raglabpage-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/pages/RagLabPage/index.tsx` | RagLabPage, patchForm, StatusStatistic, BooleanTag, VectorHealthTag (+15) |
| `frontend/src/services/rag.ts` | retrieveRagEvidence |

## Entry Points

Start here when exploring this area:

- **`RagLabPage`** (Function) — `frontend/src/pages/RagLabPage/index.tsx:82`
- **`patchForm`** (Function) — `frontend/src/pages/RagLabPage/index.tsx:153`
- **`retrieveRagEvidence`** (Function) — `frontend/src/services/rag.ts:3`
- **`loadKnowledgeItems`** (Function) — `frontend/src/pages/RagLabPage/index.tsx:105`
- **`handleRetrieve`** (Function) — `frontend/src/pages/RagLabPage/index.tsx:118`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `RagLabPage` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 82 |
| `patchForm` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 153 |
| `retrieveRagEvidence` | Function | `frontend/src/services/rag.ts` | 3 |
| `loadKnowledgeItems` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 105 |
| `handleRetrieve` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 118 |
| `StatusStatistic` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 584 |
| `BooleanTag` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 595 |
| `VectorHealthTag` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 599 |
| `ErrorDetail` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 604 |
| `RetrievalModeTag` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 617 |
| `buildRequestPreview` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 826 |
| `resolveBackendBaseUrl` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 838 |
| `resolveRetrieverMode` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 849 |
| `buildZeroHitMessage` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 860 |
| `extractRagLabError` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 874 |
| `extractBackendMessage` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 899 |
| `formatBackendDetail` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 924 |
| `EvidenceChunkCard` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 631 |
| `GraphMetadataPanel` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 678 |
| `formatScore` | Function | `frontend/src/pages/RagLabPage/index.tsx` | 811 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `RagLabPage → IsNotFoundError` | cross_community | 5 |
| `RagLabPage → ListPrivateSamples` | cross_community | 4 |
| `RagLabPage → ExtractBackendMessage` | cross_community | 4 |
| `RagLabPage → FormatBackendDetail` | cross_community | 4 |
| `HandleRetrieve → ExtractBackendMessage` | intra_community | 3 |
| `HandleRetrieve → FormatBackendDetail` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 1 calls |

## How to Explore

1. `gitnexus_context({name: "RagLabPage"})` — see callers and callees
2. `gitnexus_query({query: "raglabpage"})` — find related execution flows
3. Read key files listed above for implementation details
