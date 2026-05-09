## Context

CarbonRag currently parses uploads through `app.knowledge.parsers.parse_document()` and wraps that behavior in `DefaultParserProvider`. This works for simple documents, but it loses page/slide/table structure before chunking. The reference `ragPdfSystem` project demonstrates useful patterns for PDF page extraction, DOCX table handling, spreadsheet rendering, HTML cleanup, and recursive text splitting, but its surrounding stack is incompatible with CarbonRag because it uses Vue, Milvus, Celery, MinIO, and DashScope-specific services.

## Goals / Non-Goals

**Goals:**

- Improve CarbonRag's default parser output to include structured `DocumentBlock` records for supported file types.
- Keep the existing ParserProvider, ParsedDocument, DocumentBlock, and ChunkRecord contracts.
- Preserve current ingest, retrieval, and `/ask` behavior while making metadata richer for future citations.
- Use small, testable adapters inspired by ragPdfSystem rather than wholesale copying.

**Non-Goals:**

- Do not migrate ragPdfSystem's frontend, vector database, async queue, object storage, local DB, virtualenv, or sample files.
- Do not make OCR, Docling, MinerU, OFDRW, Milvus, or Celery mandatory.
- Do not change the default RAG answer path or public/private retrieval isolation.

## Decisions

- Enhance `DefaultParserProvider` and `app.knowledge.parsers` instead of creating a parallel parser model. This keeps existing ingest code and tests stable.
- Represent document structure as `DocumentBlock` objects with `block_type`, `page`, `section`, `order_index`, and metadata. This aligns with the V1.3 unified RAG schema.
- Keep parsing synchronous because current upload and policy ingest tasks are synchronous.
- For PDF, prefer existing `pypdf` extraction and add page metadata; optional `pdfplumber` can be used later for complex pages.
- For DOCX/Excel/CSV/HTML/PPTX, render table or slide boundaries into blocks while retaining text suitable for BM25 retrieval.
- Keep chunk size behavior compatible with existing `chunk_knowledge_text`; page-aware chunking is exposed through block metadata first, not a full replacement of retrieval storage.

## Risks / Trade-offs

- Richer parsing can expose dependency gaps on developer machines -> keep optional imports safe and return structured parse errors.
- Page-aware blocks do not automatically guarantee page-aware retrieval snippets -> first preserve metadata and add tests; retrieval display can be enhanced later.
- ragPdfSystem has MIT text in README but the zip may not include a LICENSE file -> use it as a reference and rewrite/adapt small logic to CarbonRag style.
