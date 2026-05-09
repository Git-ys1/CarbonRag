## Why

CarbonRag already has a ParserProvider boundary, but the default lightweight parser still flattens most documents into plain text. The local `ragPdfSystem` reference project has mature multi-format parsing and page-aware chunking ideas that can improve CarbonRag knowledge ingestion without importing its full stack.

## What Changes

- Enhance the default parsing path for PDF, DOCX, Excel/CSV, Markdown, HTML, TXT, and PPTX where dependencies are already lightweight or optional.
- Preserve page, slide, table, and source metadata in `ParsedDocument.blocks` so later chunking and citations can keep better evidence context.
- Add page-aware chunk helpers that map parsed blocks into existing CarbonRag `ChunkRecord`/knowledge chunk behavior without changing `/ask` defaults.
- Add parser/chunker tests using local fixtures and mocks only.
- Do not migrate ragPdfSystem's Vue frontend, Milvus, Celery, MinIO, local database, virtualenv, sample data, or secrets.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `knowledge-rag`: Default parser providers SHALL support multi-format structured document extraction and page-aware block metadata while keeping existing knowledge ingestion behavior compatible.

## Impact

- Affected modules: M5 Knowledge / File / RAG.
- Apply-stage areas: `backend/app/rag/parser.py`, `backend/app/knowledge/parsers.py`, knowledge chunk/block adapter tests, and parser regression tests.
- Dependencies: reuse existing backend dependencies where possible; `python-pptx`, `beautifulsoup4`, and `pdfplumber` may be optional additions only if needed for supported parsing.
- Default `/ask`, RAG Lab, retrieval-only, calc, report, and session flows remain unchanged.
