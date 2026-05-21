## MODIFIED Requirements

### Requirement: Knowledge/RAG exposes a product-grade knowledge base spine

CarbonRag SHALL expose active crawler maintenance and folder-like KB governance as observable, permission-aware RAG operations.

#### Scenario: Admin activity triggers controlled crawler maintenance

- **WHEN** an admin or super admin opens the management console or restores a management relay
- **THEN** CarbonRag may run active crawler maintenance with a cooldown and single-running-task guard
- **AND** the global unattended crawler auto-publish setting remains disabled.

#### Scenario: Active crawler maintenance is observable

- **WHEN** active crawler maintenance starts, skips, succeeds, partially succeeds, or fails
- **THEN** CarbonRag records a maintenance run with trigger source, actor role, stage, source count, candidate count, published count, skipped count, failed count, target KB, warnings, and errors
- **AND** the admin console can show current status, last run, last success, last failure, cooldown, and target KB.

#### Scenario: Automatic crawler KB is system managed

- **WHEN** crawler candidates pass extraction, quality, quick pipeline, and search smoke gates
- **THEN** CarbonRag publishes them to the system-managed shared automatic crawler KB
- **AND** ordinary users can retrieve from that KB but cannot rename, delete, or manually overwrite it.

#### Scenario: Knowledge bases behave like folders

- **WHEN** a user opens the knowledge base workbench
- **THEN** CarbonRag shows each KB as a folder with owner, visibility, system/shared/private markers, document count, chunk count, indexed chunk count, last ingestion time, and health state.

#### Scenario: Document deletion is scoped to one document

- **WHEN** an authorized user deletes one RAG document
- **THEN** CarbonRag removes that document, its chunks, and its vector rows by `doc_id`
- **AND** documents and chunks belonging to the same KB but different `doc_id` values remain intact.
