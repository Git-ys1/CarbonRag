---
name: adminplaceholderpage
description: "Skill for the AdminPlaceholderPage area of CarbonRag. 19 symbols across 3 files."
---

# AdminPlaceholderPage

19 symbols | 3 files | Cohesion: 91%

## When to Use

- Working with code in `frontend/`
- Understanding how listAdminKnowledgeItems, listAdminUsers, updateAdminUser work
- Modifying adminplaceholderpage-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/pages/AdminPlaceholderPage/index.tsx` | AdminPlaceholderPage, render, loadAdminWorkspace, handleUpdateUser, handleResetPassword (+7) |
| `frontend/src/services/admin.ts` | listAdminUsers, updateAdminUser, resetAdminUserPassword, getAdminFeedbackOverview, updateAdminPrivateSample (+1) |
| `frontend/src/services/knowledge.ts` | listAdminKnowledgeItems |

## Entry Points

Start here when exploring this area:

- **`listAdminKnowledgeItems`** (Function) — `frontend/src/services/knowledge.ts:157`
- **`listAdminUsers`** (Function) — `frontend/src/services/admin.ts:13`
- **`updateAdminUser`** (Function) — `frontend/src/services/admin.ts:18`
- **`resetAdminUserPassword`** (Function) — `frontend/src/services/admin.ts:23`
- **`getAdminFeedbackOverview`** (Function) — `frontend/src/services/admin.ts:28`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `listAdminKnowledgeItems` | Function | `frontend/src/services/knowledge.ts` | 157 |
| `listAdminUsers` | Function | `frontend/src/services/admin.ts` | 13 |
| `updateAdminUser` | Function | `frontend/src/services/admin.ts` | 18 |
| `resetAdminUserPassword` | Function | `frontend/src/services/admin.ts` | 23 |
| `getAdminFeedbackOverview` | Function | `frontend/src/services/admin.ts` | 28 |
| `updateAdminPrivateSample` | Function | `frontend/src/services/admin.ts` | 38 |
| `getAdminSystemStatus` | Function | `frontend/src/services/admin.ts` | 53 |
| `AdminPlaceholderPage` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 41 |
| `render` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 60 |
| `loadAdminWorkspace` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 300 |
| `handleUpdateUser` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 323 |
| `handleResetPassword` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 341 |
| `handleUpdateKnowledgeItem` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 363 |
| `handleRetryTask` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 391 |
| `handleTriggerKnowledgeRefresh` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 403 |
| `refreshUsers` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 418 |
| `refreshSystemStatus` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 424 |
| `formatTimestamp` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 741 |
| `extractDetailMessage` | Function | `frontend/src/pages/AdminPlaceholderPage/index.tsx` | 756 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Render → GetAdminSystemStatus` | intra_community | 5 |
| `HandleTriggerKnowledgeRefresh → IsNotFoundError` | cross_community | 5 |
| `HandleTriggerKnowledgeRefresh → ListPrivateSamples` | cross_community | 5 |
| `LoadAdminWorkspace → IsNotFoundError` | cross_community | 5 |
| `AdminPlaceholderPage → IsNotFoundError` | cross_community | 5 |
| `AdminPlaceholderPage → ListPrivateSamples` | cross_community | 5 |
| `Render → ListAdminUsers` | intra_community | 4 |
| `HandleTriggerKnowledgeRefresh → MapRemoteKnowledgeTask` | cross_community | 4 |
| `HandleRetryTask → IsNotFoundError` | cross_community | 4 |
| `LoadAdminWorkspace → ListKnowledgeRefreshTasks` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 6 calls |

## How to Explore

1. `gitnexus_context({name: "listAdminKnowledgeItems"})` — see callers and callees
2. `gitnexus_query({query: "adminplaceholderpage"})` — find related execution flows
3. Read key files listed above for implementation details
