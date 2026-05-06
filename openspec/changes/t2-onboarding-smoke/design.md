## Context

CarbonRag V1.2.5 established #2/#3 fork-and-PR onboarding, but this #2 seat needs a real smoke pass from the public upstream repository. The local workspace starts empty, the authenticated GitHub account is `tbx2835066135`, and the contributor display name for this repo is `tbx`.

## Goals / Non-Goals

**Goals:**

- Prove that #2 can start from `Git-ys1/CarbonRag`, create a correct fork, and work on `t2/v1.2/onboarding-smoke`.
- Record OpenSpec validation, dependency bootstrap, and local frontend/backend smoke checks in a reviewable document.
- Fix the minimal cloud-clone bootstrap defects found during #2 validation.
- Create a PR to `Git-ys1/CarbonRag:main` using the standard template.

**Non-Goals:**

- No product feature implementation.
- No API, database, auth, deployment, or model/provider changes.
- No archive step before #1 reviews the PR.

## Decisions

- Keep the smoke evidence in `docs/governance/` because this is collaboration workflow evidence, not product documentation.
- Use `t2-onboarding-smoke` as the OpenSpec change id to make the PR searchable and easy to associate with #2 onboarding.
- Update `快速上手.md` with a single index row so the smoke report is discoverable without changing #1-only announcements.
- Treat the private sample path correction as an M5 contract fix: the manifest file paths are relative to `data/private_sample/corpus/`, so shared knowledge bootstrap must resolve against that corpus root.
- Keep tests deterministic by using fake provider responses when a test is validating session memory or SSE sequencing, not external model availability.

## Risks / Trade-offs

- [Risk] Local dependency installation or tests may reveal unrelated environment failures. -> Record exact command results in the smoke report and do not widen this PR into a bug-fix branch.
- [Risk] The PR could be mistaken for a product change. -> Keep the affected module and risk flags docs-only/M8 in both the report and PR template.
- [Risk] Local runtime files are generated during validation. -> Verify ignored/untracked files before commit and keep `.env`, `.venv`, `node_modules`, build outputs, and caches out of Git.
- [Risk] The branch now includes a code fix found by onboarding. -> Keep the code change to one path resolution line and back it with the previously failing private/mixed retrieval tests plus full backend pytest.
