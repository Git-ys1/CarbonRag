---
name: auth
description: "Skill for the Auth area of CarbonRag. 32 symbols across 6 files."
---

# Auth

32 symbols | 6 files | Cohesion: 84%

## When to Use

- Working with code in `backend/`
- Understanding how test_register_admin_with_seed_password_recovers_missing_seed_admin, test_register_admin_with_seed_password_recovers_existing_broken_admin, login work
- Modifying auth-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/auth/service.py` | _connect, _utcnow, _hash_token, _row_to_user, _fetch_user_by_username (+14) |
| `backend/app/api/v1/endpoints/auth.py` | _set_auth_cookie, login, change_password, register, logout |
| `backend/app/auth/schemas.py` | RegisterRequest, LoginRequest, AuthUserEnvelope, LoginResponse |
| `backend/tests/test_auth_routes.py` | test_register_admin_with_seed_password_recovers_missing_seed_admin, test_register_admin_with_seed_password_recovers_existing_broken_admin |
| `backend/app/main.py` | bootstrap_identity_runtime |
| `backend/app/auth/dependencies.py` | _load_user_from_cookie |

## Entry Points

Start here when exploring this area:

- **`test_register_admin_with_seed_password_recovers_missing_seed_admin`** (Function) — `backend/tests/test_auth_routes.py:80`
- **`test_register_admin_with_seed_password_recovers_existing_broken_admin`** (Function) — `backend/tests/test_auth_routes.py:109`
- **`login`** (Function) — `backend/app/api/v1/endpoints/auth.py:51`
- **`change_password`** (Function) — `backend/app/api/v1/endpoints/auth.py:85`
- **`bootstrap_identity_runtime`** (Function) — `backend/app/main.py:30`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `RegisterRequest` | Class | `backend/app/auth/schemas.py` | 19 |
| `LoginRequest` | Class | `backend/app/auth/schemas.py` | 48 |
| `AuthUserEnvelope` | Class | `backend/app/auth/schemas.py` | 69 |
| `LoginResponse` | Class | `backend/app/auth/schemas.py` | 73 |
| `test_register_admin_with_seed_password_recovers_missing_seed_admin` | Function | `backend/tests/test_auth_routes.py` | 80 |
| `test_register_admin_with_seed_password_recovers_existing_broken_admin` | Function | `backend/tests/test_auth_routes.py` | 109 |
| `login` | Function | `backend/app/api/v1/endpoints/auth.py` | 51 |
| `change_password` | Function | `backend/app/api/v1/endpoints/auth.py` | 85 |
| `bootstrap_identity_runtime` | Function | `backend/app/main.py` | 30 |
| `get_auth_service` | Function | `backend/app/auth/service.py` | 682 |
| `register` | Function | `backend/app/api/v1/endpoints/auth.py` | 38 |
| `logout` | Function | `backend/app/api/v1/endpoints/auth.py` | 68 |
| `ensure_seed_admin_and_backfill` | Method | `backend/app/auth/service.py` | 141 |
| `recover_seed_admin` | Method | `backend/app/auth/service.py` | 215 |
| `register` | Method | `backend/app/auth/service.py` | 293 |
| `login` | Method | `backend/app/auth/service.py` | 370 |
| `get_user_from_token` | Method | `backend/app/auth/service.py` | 463 |
| `logout` | Method | `backend/app/auth/service.py` | 525 |
| `change_password` | Method | `backend/app/auth/service.py` | 537 |
| `update_user` | Method | `backend/app/auth/service.py` | 580 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Register → Connect_postgres` | cross_community | 6 |
| `Change_password → Connect_postgres` | cross_community | 5 |
| `Login → Connect_postgres` | cross_community | 5 |
| `Register → _utcnow` | cross_community | 5 |
| `Register → _row_to_user` | cross_community | 4 |
| `Logout → Connect_postgres` | cross_community | 4 |
| `Change_password → _utcnow` | intra_community | 3 |
| `Change_password → _row_to_user` | intra_community | 3 |
| `Change_password → _hash_token` | intra_community | 3 |
| `Change_password → Get_settings` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 4 calls |
| Carbon | 2 calls |

## How to Explore

1. `gitnexus_context({name: "test_register_admin_with_seed_password_recovers_missing_seed_admin"})` — see callers and callees
2. `gitnexus_query({query: "auth"})` — find related execution flows
3. Read key files listed above for implementation details
