---
name: askpage
description: "Skill for the AskPage area of CarbonRag. 53 symbols across 4 files."
---

# AskPage

53 symbols | 4 files | Cohesion: 76%

## When to Use

- Working with code in `frontend/`
- Understanding how AskPage, openCitationPanel, getSession work
- Modifying askpage-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/pages/AskPage/index.tsx` | AskPage, openCitationPanel, CitationGroup, groupCitationsBySource, summarizeCitations (+43) |
| `frontend/src/services/sessions.ts` | getSession, replaceAttachedPrivateSamples |
| `frontend/src/services/knowledge.ts` | isNotFoundError, replaceAttachedKnowledgeItems |
| `frontend/src/services/files.ts` | uploadSessionFile |

## Entry Points

Start here when exploring this area:

- **`AskPage`** (Function) — `frontend/src/pages/AskPage/index.tsx:78`
- **`openCitationPanel`** (Function) — `frontend/src/pages/AskPage/index.tsx:452`
- **`getSession`** (Function) — `frontend/src/services/sessions.ts:54`
- **`replaceAttachedPrivateSamples`** (Function) — `frontend/src/services/sessions.ts:64`
- **`replaceAttachedKnowledgeItems`** (Function) — `frontend/src/services/knowledge.ts:327`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `AskPage` | Function | `frontend/src/pages/AskPage/index.tsx` | 78 |
| `openCitationPanel` | Function | `frontend/src/pages/AskPage/index.tsx` | 452 |
| `getSession` | Function | `frontend/src/services/sessions.ts` | 54 |
| `replaceAttachedPrivateSamples` | Function | `frontend/src/services/sessions.ts` | 64 |
| `replaceAttachedKnowledgeItems` | Function | `frontend/src/services/knowledge.ts` | 327 |
| `uploadSessionFile` | Function | `frontend/src/services/files.ts` | 4 |
| `loadSessionDetail` | Function | `frontend/src/pages/AskPage/index.tsx` | 193 |
| `handleSaveAttachedSamples` | Function | `frontend/src/pages/AskPage/index.tsx` | 211 |
| `handleUploadChange` | Function | `frontend/src/pages/AskPage/index.tsx` | 432 |
| `onMessageStart` | Function | `frontend/src/pages/AskPage/index.tsx` | 290 |
| `onStatus` | Function | `frontend/src/pages/AskPage/index.tsx` | 308 |
| `onThinkingDelta` | Function | `frontend/src/pages/AskPage/index.tsx` | 323 |
| `onAnswerDelta` | Function | `frontend/src/pages/AskPage/index.tsx` | 339 |
| `onError` | Function | `frontend/src/pages/AskPage/index.tsx` | 378 |
| `updateStreamDraftState` | Function | `frontend/src/pages/AskPage/index.tsx` | 481 |
| `handleSubmit` | Function | `frontend/src/pages/AskPage/index.tsx` | 230 |
| `handleComposerKeyDown` | Function | `frontend/src/pages/AskPage/index.tsx` | 457 |
| `replaceStreamDraft` | Function | `frontend/src/pages/AskPage/index.tsx` | 476 |
| `commitDraftToActiveSession` | Function | `frontend/src/pages/AskPage/index.tsx` | 499 |
| `syncActiveSessionSummaryFromList` | Function | `frontend/src/pages/AskPage/index.tsx` | 527 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `MyKnowledgePage → IsNotFoundError` | cross_community | 6 |
| `MyKnowledgePage → GetSession` | cross_community | 6 |
| `RagLabPage → IsNotFoundError` | cross_community | 5 |
| `HandleTriggerKnowledgeRefresh → IsNotFoundError` | cross_community | 5 |
| `LoadAdminWorkspace → IsNotFoundError` | cross_community | 5 |
| `AdminPlaceholderPage → IsNotFoundError` | cross_community | 5 |
| `HandleRetryTask → IsNotFoundError` | cross_community | 4 |
| `CarbonCalcPage → GetSession` | cross_community | 4 |
| `OnMetadata → UpdateStreamDraft` | cross_community | 3 |
| `OnDone → UpdateStreamDraft` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Components | 2 calls |
| Services | 2 calls |
| Router | 1 calls |
| CarbonCalcPage | 1 calls |
| Hooks | 1 calls |

## How to Explore

1. `gitnexus_context({name: "AskPage"})` — see callers and callees
2. `gitnexus_query({query: "askpage"})` — find related execution flows
3. Read key files listed above for implementation details
