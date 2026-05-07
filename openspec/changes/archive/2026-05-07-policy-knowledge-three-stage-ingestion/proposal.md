## Why

CarbonRag already supports user uploads, optional parser providers, workflow checkpoints, and RAG retrieval, but public policy knowledge still lacks a controlled web ingestion boundary. A three-stage policy ingestion flow lets the project collect official policy sources, parse documents through existing providers, and normalize governance metadata without changing `/ask` or retrieval defaults.

## What Changes

- Add a disabled-by-default policy crawler boundary for official-domain public policy collection.
- Add normalized `CrawledDocument` and policy governance metadata contracts.
- Route policy HTML/PDF/OFD parsing through lightweight HTML extraction, existing optional Docling/MinerU parser providers, and an optional OFD converter adapter.
- Add policy ingest workflow/task names for staged crawl ingestion without making Scrapy, Scrapyd, OFDRW, Docling, or MinerU mandatory dependencies.
- Preserve existing RAG behavior by mapping indexed public policy web chunks to the existing `public_policy` evidence source type.

## Capabilities

### New Capabilities

### Modified Capabilities

- `knowledge-rag`: Add controlled official policy web ingestion, policy document parsing routing, policy governance metadata, and policy ingest workflow checkpoints.

## Impact

- Affected modules: M5 Knowledge / File / RAG and M8 OpenSpec / governance docs.
- Affected code: knowledge schemas, chunking, optional parser/crawler adapters, workflow model, and tests.
- Dependencies: no new required runtime dependency; Scrapy/Scrapyd/OFDRW remain optional or stubbed for later.
- APIs: no removal or breaking response change; `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults must remain compatible.
