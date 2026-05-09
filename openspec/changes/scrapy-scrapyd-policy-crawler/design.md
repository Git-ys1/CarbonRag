## Context

Current CarbonRag policy ingestion already has:

- official URL allowlist validation;
- `FakeCrawlerProvider` for offline tests;
- `ScrapyCrawlerProvider` for optional local Scrapy execution;
- `PolicyCrawlerScheduler` and Admin APIs;
- runtime tables for sources, runs, and pending-review candidates;
- publish/reject gates before `public_policy_web` indexing.

The missing operational pieces are a clear provider selection boundary and an optional Scrapyd remote execution adapter. Directly copying Scrapy/Scrapyd code is unnecessary and increases maintenance risk; both projects are intended to be consumed as Python packages or daemon APIs.

## Goals / Non-Goals

**Goals:**

- Make local Scrapy the explicit default policy crawler backend when policy crawling is enabled.
- Add a `ScrapydCrawlerProvider` interface and implementation that talks to Scrapyd HTTP APIs.
- Surface local/remote backend availability in Admin UI.
- Keep all crawler output review-gated.
- Add tests with fake/mocked Scrapyd responses; no CI dependence on a live daemon.

**Non-Goals:**

- No distributed crawler cluster.
- No browser automation.
- No arbitrary URL crawler.
- No Scrapyd deployment automation in this round.
- No direct copy of upstream project source code.
- No changes to default `/ask` retrieval.

## Decisions

### Decision 1: Use Adapters, Not Vendor Copies

CarbonRag SHALL not vendor Scrapy or Scrapyd source. The local path uses the existing `scrapy` package through `ScrapyCrawlerProvider`; the remote path uses Scrapyd's HTTP API through a new provider boundary.

Rationale:
- Keeps upstream security fixes and package ownership intact.
- Avoids copying unrelated framework code.
- Keeps licensing simple: dependencies remain external BSD-3-Clause projects.

### Decision 2: Local Scrapy Remains Safer Default

The default backend is `local_scrapy`. Scrapyd is only used when explicitly configured.

Rationale:
- Local development and CI should not require a long-running daemon.
- Production operators can choose Scrapyd when they need isolated worker processes.

### Decision 3: Scrapyd Is Health-Checked Before Scheduling

`ScrapydCrawlerProvider.describe()` SHALL report endpoint reachability and project/spider availability where possible. A failed healthcheck returns `unavailable` and never blocks app startup.

Rationale:
- Admin UI needs clear operational status.
- Runtime outages must not break chat, RAG, or carbon flows.

### Decision 4: Both Backends Share Policy Safety Guards

Before any crawl is scheduled or run, CarbonRag SHALL apply:

- official allowlist validation;
- `robots=true`;
- max depth/page limits;
- download delay;
- per-domain concurrency limit;
- timeout;
- user-agent;
- pending-review staging.

Rationale:
- Backend choice must not loosen public-site etiquette or trust boundaries.

### Decision 5: Admin UI Shows Backend and Review Status

Admin crawler UI SHALL show:

- active backend;
- local Scrapy availability;
- Scrapyd availability and endpoint label;
- run status and external job id where present;
- pending/published/rejected candidates;
- publish/reject actions.

Rationale:
- Operators need to distinguish "crawler unavailable", "remote daemon unavailable", "run failed", and "candidate awaiting review".

## Risks / Trade-offs

- [Risk] Scrapyd can be unsafe if exposed publicly without access controls. Mitigation: CarbonRag only calls configured internal endpoints; no credentials in repo; Admin APIs remain protected.
- [Risk] Remote daemon state can drift from CarbonRag runtime state. Mitigation: store external job id and poll status; never index without local pending candidate and admin publish.
- [Risk] Official sites may block crawlers. Mitigation: strict rate limits and clear run failure records.
- [Risk] User may expect "direct copy". Mitigation: use dependencies/adapters, not vendored framework source.
