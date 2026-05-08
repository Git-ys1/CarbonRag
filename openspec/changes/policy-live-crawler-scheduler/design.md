## Context

`policy-knowledge-three-stage-ingestion` created the policy collection/parsing/governance pipeline, and `policy-ingestion-showcase-readiness` made a synthetic source demonstrable in the product. The remaining gap is a safe live-source intake lane: official public pages can be crawled, but crawler results must not immediately become trusted policy evidence.

#1 approved this change with strict constraints:

- no default automatic public crawling;
- only allowlisted official domains;
- robots, rate limit, timeout, user-agent, failure fallback, and logs must be present;
- crawl output must enter `pending_review`;
- candidates must not affect `/ask` or RAG retrieval until admin publication;
- runtime schema changes must cover SQLite and PostgreSQL bootstrap paths.

## Goals / Non-Goals

**Goals:**
- Add live policy crawler sources and run tracking.
- Let admins manually run an allowlisted source.
- Stage crawler output as review candidates.
- Publish a candidate into the existing `public_policy_web` + `crawl_ingest` path.
- Reject a candidate without indexing it.
- Show status and controls in Admin UI.
- Preserve default `/ask`, RAG Lab, retrieval-only, calc, report, and session behavior.

**Non-Goals:**
- No default automatic public crawling.
- No Scrapyd.
- No distributed scheduler.
- No browser automation.
- No arbitrary user URL crawling.
- No forced Scrapy dependency.
- No changes to normal chat or carbon flows.

## Decisions

### Decision 1: Manual By Default, Scheduled Only By Explicit Configuration

The scheduler boundary will be created at application startup so status is visible, but it will not start recurring live crawls unless an explicit configuration enables scheduled mode. Admin manual trigger is the primary V1.3.4 path.

Rationale:
- #1 explicitly blocked default automatic public crawling.
- Manual operation is safer for official-site etiquette and reviewer confidence.
- The same scheduler object can later run recurring crawls when policy and deployment constraints are approved.

### Decision 2: Candidates Are The Trust Boundary

Crawler results become `policy_crawl_candidates` with `status=pending_review`. The publish action is the only path that creates or refreshes a `public_policy_web` knowledge item and enqueues `crawl_ingest`.

Rationale:
- Scraped public content is not equivalent to curated evidence.
- Human review is needed for metadata quality, source authenticity, and crawler mistakes.
- Existing retrieval contracts remain stable because only published items are indexed.

### Decision 3: Runtime Tables Instead Of A New Migration System

The project currently bootstraps runtime schema through code-managed SQLite/PostgreSQL statements. This change adds crawler tables to the same bootstrap layer and uses additive `CREATE TABLE IF NOT EXISTS` statements.

Rationale:
- Avoids introducing a migration framework in V1.3.4.
- Keeps local development and CI stable.
- Additive tables are compatible with existing databases.

### Decision 4: Reuse Existing ScrapyCrawlerProvider

The live crawler control plane will wrap the existing `ScrapyCrawlerProvider` rather than replacing crawler implementation. Requests use conservative defaults:

- `obey_robots=true`;
- `max_depth=1`;
- `max_pages=20`;
- `download_delay_seconds=2.0`;
- `concurrent_requests_per_domain=1`;
- timeout configured per run;
- official allowlist validation before fetching.

Rationale:
- The current provider already has optional dependency fallback.
- Conservative settings reduce site load.
- Tests can use fake providers without network access.

### Decision 5: Admin UI Is A Control Surface, Not A Retrieval Surface

Admin UI will show source status, scheduler availability, runs, and pending candidates. It may let admins publish or reject candidates, but normal chat and RAG defaults are not changed.

Rationale:
- Live crawling is operationally sensitive.
- Public retrieval must remain predictable and review-gated.

## Risks / Trade-offs

- [Risk] A reviewer may expect automatic crawling because the feature name mentions scheduler. Mitigation: UI and docs say recurring public crawling is disabled unless explicitly configured.
- [Risk] Optional Scrapy may be missing. Mitigation: scheduler status is `unavailable`, startup succeeds, and tests cover this path.
- [Risk] Official sites may block or change pages. Mitigation: candidates capture errors/status, and no result is trusted until review.
- [Risk] Additional runtime tables may drift between SQLite and PostgreSQL. Mitigation: add both schema paths and dedicated tests around bootstrap/persistence.
