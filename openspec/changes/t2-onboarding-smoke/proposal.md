## Why

#2 needs a real fork-and-PR onboarding pass from the cloud repository, not a copied local snapshot. The smoke run also exposed cloud-clone bootstrap failures that #1's local environment did not surface, so this change records the onboarding evidence and fixes the minimal defects required for a clean #2 validation pass.

## What Changes

- Add a V1.2.6 #2 onboarding smoke report under governance docs.
- Record the verified fork, remotes, branch, OpenSpec change id, validation commands, local frontend/backend smoke checks, and PR target.
- Fix shared private sample source resolution so repo sample documents are loaded from `data/private_sample/corpus/**`.
- Make provider-dependent tests use explicit fake providers/streams where they are validating session or SSE behavior rather than real cloud model connectivity.
- Add this report to the Chinese quick-start index so later seats can find the #2 smoke example.
- Keep the runtime behavior change limited to restoring the existing M5 private sample indexing contract.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `governance`: Add a requirement that new-seat onboarding smoke runs are recorded as reviewable governance evidence.

## Impact

- Affected modules: M5 Knowledge / File / RAG and M8 Spec / Governance / Project Docs.
- Affected files: shared private sample knowledge bootstrap, provider-isolated tests, governance docs, quick-start index, and OpenSpec change artifacts.
- No business API, database, frontend route, auth, deployment, or model/provider behavior changes.
