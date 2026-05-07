## Context

The current knowledge task flow covers uploads and shared repo samples. The RAG layer already has unified contracts, parser providers, optional Docling/MinerU adapters, vector boundaries, retrieval traces, and workflow checkpoints. This change adds the missing policy collection and governance layer while keeping crawling out of the read-time retrieval path.

## Goals / Non-Goals

**Goals:**

- Introduce a disabled-by-default crawler boundary for official public policy sources.
- Stage crawled content before parsing or indexing.
- Normalize policy metadata such as issuing authority, document number, dates, region, industry, tags, clause anchors, and source URL.
- Let policy web chunks retrieve as existing `public_policy` evidence.
- Keep Scrapy, Scrapyd, OFDRW, Docling, and MinerU optional.

**Non-Goals:**

- No arbitrary URL crawling, login crawling, browser automation, or live network crawl in tests.
- No Scrapyd daemon deployment.
- No mandatory Docling, MinerU, OFDRW, or Scrapy install.
- No change to `/ask`, calc, report, session, or existing retrieval defaults.

## Decisions

- Use a new `CrawlerProvider` protocol with `FakeCrawlerProvider` for offline tests and a safe `ScrapyCrawlerProvider` boundary that reports unavailable unless Scrapy is installed and explicitly enabled.
- Run real Scrapy crawling through a short-lived subprocess runner so FastAPI does not own or restart Twisted's reactor.
- Enforce official domain allowlists before a crawl request can run. The first allowlist covers national government, NDRC, MEE, MIIT, and Beijing government/agency domains.
- Stage crawler output as local files or normalized records before knowledge indexing. Staging keeps crawler side effects out of retrieval and lets workflows resume from a known artifact.
- Parse HTML locally with a small stdlib extractor, parse PDF through `ParserRegistry` preferring Docling with existing fallback, and treat OFD as a conversion step through an optional `OfdrwConverterAdapter`.
- Store policy metadata on chunks through a `metadata`/`metadata_json` extension while preserving existing scalar fields and evidence source behavior.
- Add policy-specific workflow nodes (`crawl_source`, `stage_crawled_document`, `normalize_policy_metadata`) alongside existing ingest nodes.
- Add a `KnowledgeService.create_policy_item_from_crawled_document` entrypoint for offline crawler results. It stages content, creates or refreshes a shared `public_policy_web` item, and enqueues `crawl_ingest` without exposing live crawling as a default read path.
- Let `PublicPolicyRetriever` append indexed `public_policy_web` runtime chunks to the existing checked-in public policy corpus, preserving the outward `public_policy` evidence type.
- Harden the lightweight HTML parser with conservative boilerplate filtering and visible metadata extraction before introducing heavier parser dependencies.
- Wrap parser registry output for PDF/OFD policy documents so optional Docling/MinerU/default parser metadata is preserved while the policy ingestion layer retains public policy source context.

## Risks / Trade-offs

- Optional crawler/parser dependencies may not be installed → adapters must report unavailable and tests must use fakes.
- Official site HTML varies widely → first metadata extraction is heuristic and must preserve unknown/null fields instead of failing.
- Adding chunk metadata storage touches runtime DB schema → use additive `metadata_json` columns and default empty objects.
- Public policy web source type could break existing retrieval literals → keep chunk evidence mapped to `public_policy`.
- Scrapy may not be installed in CI → keep real crawler smoke tests skipped unless the optional dependency is present.
- Runtime policy chunks are loaded through the same BM25 public retriever cache, so ingestion must clear public/mixed retriever caches after successful indexing.
- HTML boilerplate filtering can accidentally remove content on unusual official pages → keep the filter conservative and prefer explicit semantic tags/classes over broad text deletion.
