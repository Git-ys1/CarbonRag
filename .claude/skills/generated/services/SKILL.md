---
name: services
description: "Skill for the Services area of CarbonRag. 71 symbols across 13 files."
---

# Services

71 symbols | 13 files | Cohesion: 87%

## When to Use

- Working with code in `frontend/`
- Understanding how listPrivateSamples, listAttachableKnowledgeItems, listAdminKnowledgeItems work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/services/knowledge.ts` | tryRemote, mapUploadedFileToKnowledgeItem, mapRemoteKnowledgeTask, pickKnowledgeTask, loadCurrentUserSessionData (+13) |
| `frontend/src/services/sessions.ts` | submitSessionAskRequest, submitSessionAskStreamRequest, buildApiUrl, emitReconnectNotice, emitSyntheticStreamEvents (+9) |
| `frontend/src/services/sse.ts` | createSseParserState, consumeSseTextChunk, flushSseState, processSseLine, flushCompletedEvent |
| `frontend/src/services/settings.ts` | getSettings, listProviderProfiles, createProviderProfile, updateProviderProfile, deleteProviderProfile |
| `frontend/src/pages/AdminPlaceholderPage/index.tsx` | AdminPlaceholderPage, loadAdminWorkspace, handleTriggerKnowledgeRefresh, formatTimestamp |
| `frontend/src/app/SettingsContext.tsx` | refresh, createAccountProviderProfileInternal, updateAccountProviderProfileInternal, deleteAccountProviderProfileInternal |
| `frontend/src/services/reports.ts` | listSessionReports, listSessionCarbonResults, createReport, updateReport |
| `frontend/src/pages/ReportPage/index.tsx` | loadSessionWorkspace, handleGenerate, handleSave, extractDetailMessage |
| `frontend/src/services/auth.ts` | registerAccount, loginAccount, logoutAccount, changePassword |
| `frontend/src/app/AuthContext.tsx` | register, login, logout, handleChangePassword |

## Entry Points

Start here when exploring this area:

- **`listPrivateSamples`** (Function) — `frontend/src/services/privateSamples.ts:3`
- **`listAttachableKnowledgeItems`** (Function) — `frontend/src/services/knowledge.ts:144`
- **`listAdminKnowledgeItems`** (Function) — `frontend/src/services/knowledge.ts:157`
- **`listKnowledgeTasks`** (Function) — `frontend/src/services/knowledge.ts:169`
- **`triggerKnowledgeScan`** (Function) — `frontend/src/services/knowledge.ts:194`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `listPrivateSamples` | Function | `frontend/src/services/privateSamples.ts` | 3 |
| `listAttachableKnowledgeItems` | Function | `frontend/src/services/knowledge.ts` | 144 |
| `listAdminKnowledgeItems` | Function | `frontend/src/services/knowledge.ts` | 157 |
| `listKnowledgeTasks` | Function | `frontend/src/services/knowledge.ts` | 169 |
| `triggerKnowledgeScan` | Function | `frontend/src/services/knowledge.ts` | 194 |
| `triggerKnowledgeRebuild` | Function | `frontend/src/services/knowledge.ts` | 212 |
| `retryKnowledgeTask` | Function | `frontend/src/services/knowledge.ts` | 230 |
| `listAdminKnowledgeTasks` | Function | `frontend/src/services/knowledge.ts` | 248 |
| `listMyUploads` | Function | `frontend/src/services/knowledge.ts` | 260 |
| `listMyReports` | Function | `frontend/src/services/knowledge.ts` | 278 |
| `listMyFeedback` | Function | `frontend/src/services/knowledge.ts` | 298 |
| `loadMyKnowledgeWorkspace` | Function | `frontend/src/services/knowledge.ts` | 310 |
| `getAdminFeedbackOverview` | Function | `frontend/src/services/admin.ts` | 28 |
| `listKnowledgeRefreshTasks` | Function | `frontend/src/services/admin.ts` | 43 |
| `triggerKnowledgeRefresh` | Function | `frontend/src/services/admin.ts` | 48 |
| `loadKnowledgeCatalog` | Function | `frontend/src/pages/AskPage/index.tsx` | 179 |
| `AdminPlaceholderPage` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 41 |
| `loadAdminWorkspace` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 300 |
| `handleTriggerKnowledgeRefresh` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 403 |
| `createSseParserState` | Function | `frontend/src/services/sse.ts` | 11 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `MyKnowledgePage → IsNotFoundError` | cross_community | 6 |
| `MyKnowledgePage → ListSessions` | cross_community | 6 |
| `MyKnowledgePage → GetSession` | cross_community | 6 |
| `RagLabPage → IsNotFoundError` | cross_community | 5 |
| `HandleTriggerKnowledgeRefresh → IsNotFoundError` | cross_community | 5 |
| `HandleTriggerKnowledgeRefresh → ListPrivateSamples` | intra_community | 5 |
| `LoadAdminWorkspace → IsNotFoundError` | cross_community | 5 |
| `MyKnowledgePage → MapUploadedFileToKnowledgeItem` | cross_community | 5 |
| `MyKnowledgePage → ListPrivateSamples` | cross_community | 5 |
| `MyKnowledgePage → ListSessionReports` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| AdminPlaceholderPage | 4 calls |
| CarbonCalcPage | 2 calls |
| AskPage | 1 calls |
| Layouts | 1 calls |
| ReportPage | 1 calls |

## How to Explore

1. `gitnexus_context({name: "listPrivateSamples"})` — see callers and callees
2. `gitnexus_query({query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
