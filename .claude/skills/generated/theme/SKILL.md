---
name: theme
description: "Skill for the Theme area of CarbonRag. 20 symbols across 5 files."
---

# Theme

20 symbols | 5 files | Cohesion: 88%

## When to Use

- Working with code in `frontend/`
- Understanding how buildCssVariables, writeStoredThemeMode, writeStoredThemePreset work
- Modifying theme-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/theme/provider.tsx` | resolveSystemTheme, ThemeProvider, update, listener, handleStorage (+3) |
| `frontend/src/theme/tokens.ts` | buildCssVariables, buildThemeVariant, getScale, withAlpha, shadow |
| `frontend/src/theme/storage.ts` | writeStoredThemeMode, writeStoredThemePreset, readStoredThemeMode, readStoredThemePreset, isThemePresetId |
| `frontend/src/theme/presets/index.ts` | getThemePreset |
| `frontend/src/theme/antd-map.ts` | mapThemeToAntd |

## Entry Points

Start here when exploring this area:

- **`buildCssVariables`** (Function) — `frontend/src/theme/tokens.ts:196`
- **`writeStoredThemeMode`** (Function) — `frontend/src/theme/storage.ts:24`
- **`writeStoredThemePreset`** (Function) — `frontend/src/theme/storage.ts:31`
- **`ThemeProvider`** (Function) — `frontend/src/theme/provider.tsx:38`
- **`update`** (Function) — `frontend/src/theme/provider.tsx:48`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `buildCssVariables` | Function | `frontend/src/theme/tokens.ts` | 196 |
| `writeStoredThemeMode` | Function | `frontend/src/theme/storage.ts` | 24 |
| `writeStoredThemePreset` | Function | `frontend/src/theme/storage.ts` | 31 |
| `ThemeProvider` | Function | `frontend/src/theme/provider.tsx` | 38 |
| `update` | Function | `frontend/src/theme/provider.tsx` | 48 |
| `listener` | Function | `frontend/src/theme/provider.tsx` | 50 |
| `buildThemeVariant` | Function | `frontend/src/theme/tokens.ts` | 104 |
| `getScale` | Function | `frontend/src/theme/tokens.ts` | 246 |
| `withAlpha` | Function | `frontend/src/theme/tokens.ts` | 254 |
| `shadow` | Function | `frontend/src/theme/tokens.ts` | 265 |
| `readStoredThemeMode` | Function | `frontend/src/theme/storage.ts` | 5 |
| `readStoredThemePreset` | Function | `frontend/src/theme/storage.ts` | 16 |
| `handleStorage` | Function | `frontend/src/theme/provider.tsx` | 60 |
| `getThemePreset` | Function | `frontend/src/theme/presets/index.ts` | 32 |
| `activePreset` | Function | `frontend/src/theme/provider.tsx` | 74 |
| `quickPresets` | Function | `frontend/src/theme/provider.tsx` | 76 |
| `mapThemeToAntd` | Function | `frontend/src/theme/antd-map.ts` | 4 |
| `themeConfig` | Function | `frontend/src/theme/provider.tsx` | 102 |
| `resolveSystemTheme` | Function | `frontend/src/theme/provider.tsx` | 31 |
| `isThemePresetId` | Function | `frontend/src/theme/storage.ts` | 38 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `App → IsThemePresetId` | cross_community | 4 |
| `App → ReadStoredThemeMode` | cross_community | 3 |
| `App → ResolveSystemTheme` | cross_community | 3 |
| `App → Update` | cross_community | 3 |
| `HandleStorage → IsThemePresetId` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "buildCssVariables"})` — see callers and callees
2. `gitnexus_query({query: "theme"})` — find related execution flows
3. Read key files listed above for implementation details
