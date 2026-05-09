## ADDED Requirements

### Requirement: Default parser preserves multi-format document structure
CarbonRag SHALL parse supported knowledge files into `ParsedDocument` objects with structured `DocumentBlock` records where document structure is available.

#### Scenario: PDF parsing records page blocks
- **WHEN** a text-based PDF is parsed by the default parser
- **THEN** CarbonRag returns blocks with page metadata for extracted page text

#### Scenario: Office and tabular files keep structural hints
- **WHEN** DOCX, Excel, CSV, or PPTX files are parsed by the default parser
- **THEN** CarbonRag keeps paragraph, table, sheet, row, or slide context in block metadata where available

#### Scenario: HTML parsing removes unsafe boilerplate
- **WHEN** an HTML knowledge file is parsed by the default parser
- **THEN** CarbonRag extracts readable body text without script/style content

### Requirement: Page-aware parser output remains ingestion-compatible
CarbonRag SHALL keep existing knowledge ingestion and retrieval behavior compatible while adding parser block metadata.

#### Scenario: Existing upload ingest continues to index chunks
- **WHEN** an uploaded supported file is processed through the knowledge task runner
- **THEN** CarbonRag still parses, chunks, stores, and retrieves the item through the existing task flow

#### Scenario: Local closed-loop verification proves ingest to retrieval
- **WHEN** the ragPdfSystem parser/chunker adapter verification is run locally
- **THEN** it creates controlled document fixtures in temporary runtime storage
- **AND** ingests them through the existing knowledge task flow
- **AND** retrieves at least one evidence chunk through the existing RAG engine without changing `/ask` defaults

#### Scenario: Parser metadata is safe when optional dependencies are absent
- **WHEN** a parser path needs an optional dependency that is not installed
- **THEN** CarbonRag records a clear parse error instead of failing application startup
