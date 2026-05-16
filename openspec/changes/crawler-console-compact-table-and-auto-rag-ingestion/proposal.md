# Change: crawler-console-compact-table-and-auto-rag-ingestion

## Why

V1.7.2/V1.7.3 made crawler candidates publishable to the RAG-Pro KB quick pipeline, but the admin console still presents candidates and runs as long engineering lists. Once real sources produce more than a few candidates, reviewers cannot page, filter, inspect, or batch publish reliably.

## What Changes

- Convert crawler candidates and runs to paginated table APIs and table UI.
- Add a candidate detail drawer with overview, artifact preview entry, RAG status, quality diagnostics, and raw metadata.
- Add batch publish-to-RAG and explicit per-run "crawl and auto ingest" controls.
- Present the system crawler KB as "自动爬虫知识库" and expose its document/chunk status.
- Keep global scheduled publish and global auto-publish disabled.

## Out Of Scope

- No new crawler sources.
- No Crawlab runtime or distributed scheduler.
- No RAG algorithm changes.
- No super-admin or management relay changes.
