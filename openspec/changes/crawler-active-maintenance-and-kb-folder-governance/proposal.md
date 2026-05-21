# Change: crawler-active-maintenance-and-kb-folder-governance

## Why

V1.7.7 made crawler candidates easier to review and publish, but the crawler still behaves like a manually triggered admin tool. Admins cannot clearly see whether active maintenance ran, what it indexed, why it skipped items, or how the automatic crawler KB is governed. Knowledge bases also need a folder-like identity with document-level lifecycle actions before later sharing/forwarding work can be built safely.

## What Changes

- Add active crawler maintenance records and status APIs, triggered when admin or super admin users are active.
- Keep global unattended crawler auto-publish disabled; active maintenance is scoped, cooled down, observable, and gated by existing extraction/RAG quality checks.
- Show crawler maintenance status and history in the admin console.
- Add KB folder governance fields, KB overview, document delete, and document index rebuild APIs.
- Treat the automatic crawler KB as a system-managed shared KB: searchable by users, managed by admins, protected from ordinary edits.

## Out Of Scope

- No RAG ranking or embedding algorithm changes.
- No Crawlab/Celery/RabbitMQ/MinIO integration.
- No full KB sharing/forwarding product flow.
- No global unattended crawler publishing.
