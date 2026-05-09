# Tasks

## 1. Parser Contract Enhancement

- [x] 1.1 Inspect current parser, knowledge ingest, and chunking call paths with GitNexus impact before editing.
- [x] 1.2 Extend default parser support for structured blocks across PDF, DOCX, Excel/CSV, Markdown, HTML, TXT, and PPTX where available.
- [x] 1.3 Preserve parser metadata including parser name/version, source file, parse success/error, block count, and page/slide/table hints.

## 2. Chunk Compatibility

- [x] 2.1 Add helper behavior to derive block-aware `ParsedDocument.text` without breaking existing chunking.
- [x] 2.2 Keep existing `chunk_knowledge_text` and public/private retrieval output shape unchanged.
- [x] 2.3 Ensure unsupported or optional-missing formats return clear provider-level failure metadata.

## 3. Tests

- [x] 3.1 Add parser tests for text/markdown/html/csv/xlsx/docx/pdf structured blocks.
- [x] 3.2 Add PPTX optional dependency test or graceful skip when unavailable.
- [x] 3.3 Add regression coverage that existing knowledge ingest and `/ask` defaults are not changed.

## 4. Validation

- [x] 4.1 Run targeted parser and knowledge tests.
- [x] 4.2 Run backend full pytest if targeted tests pass.
- [x] 4.3 Run frontend typecheck/build for RAG Lab compatibility if backend changes touch response shape.
- [x] 4.4 Run `openspec validate ragpdf-parser-chunker-adapter --strict` and `openspec validate --all`.
- [x] 4.5 Run `git diff --check` and `gitnexus detect_changes`.

## 5. Closed-Loop Verification

- [x] 5.1 Add a local verification script that builds ragPdfSystem-inspired document fixtures, ingests them through existing knowledge tasks, and retrieves evidence through the existing RAG engine.
- [x] 5.2 Keep the script isolated from #1's active session-file-reading workbench by using temporary runtime storage and existing service contracts only.
- [x] 5.3 Add tests that the verification report shows indexed items, generated chunks, retrieval hits, references, and safe parser metadata.
- [x] 5.4 Run targeted closed-loop tests plus OpenSpec validation.
