import sqlite3

CORE_TABLES = (
    "users",
    "auth_sessions",
    "sessions",
    "messages",
    "user_settings",
    "user_provider_profiles",
    "memory_notes",
    "files",
    "file_parse_results",
    "session_knowledge_items",
    "session_private_samples",
    "knowledge_items",
    "knowledge_chunks",
    "rag_knowledge_bases",
    "rag_documents",
    "rag_chunks",
    "rag_test_qa_runs",
    "rag_eval_runs",
    "rag_eval_cases",
    "knowledge_graph_nodes",
    "knowledge_graph_edges",
    "knowledge_tasks",
    "workflow_runs",
    "workflow_nodes",
    "execution_checkpoints",
    "feedback_entries",
    "carbon_calculations",
    "carbon_factor_sources",
    "carbon_factor_records",
    "carbon_factor_catalog_entries",
    "carbon_factor_aliases",
    "carbon_factor_import_jobs",
    "carbon_inventories",
    "carbon_activity_items",
    "carbon_calculation_lines",
    "carbon_factor_snapshots",
    "carbon_evidence_references",
    "carbon_inventory_summaries",
    "reports",
    "report_sources",
    "report_files",
    "private_sample_catalog_overrides",
    "knowledge_refresh_tasks",
    "policy_crawl_sources",
    "policy_crawl_runs",
    "policy_crawl_candidates",
)

OWNER_TABLES = (
    "sessions",
    "user_settings",
    "user_provider_profiles",
    "files",
    "memory_notes",
    "knowledge_items",
    "rag_knowledge_bases",
    "rag_documents",
    "feedback_entries",
    "carbon_calculations",
    "carbon_inventories",
    "reports",
    "report_files",
)

SQLITE_SCHEMA_SCRIPT = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT UNIQUE,
    avatar_url TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    password_must_change INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    auth_session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    pinned_at TEXT,
    knowledge_scope_last_used TEXT,
    source_summary_json TEXT,
    session_summary TEXT,
    summary_message_seq_upto INTEGER,
    summary_updated_at TEXT,
    summary_estimated_tokens INTEGER NOT NULL DEFAULT 0,
    compaction_status TEXT NOT NULL DEFAULT 'idle',
    last_compaction_error TEXT,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    thinking_content TEXT,
    status TEXT,
    trace_id TEXT,
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_settings (
    owner_user_id TEXT PRIMARY KEY,
    appearance_json TEXT NOT NULL DEFAULT '{}',
    chat_json TEXT NOT NULL DEFAULT '{}',
    data_privacy_json TEXT NOT NULL DEFAULT '{}',
    advanced_json TEXT NOT NULL DEFAULT '{}',
    active_provider_ref TEXT NOT NULL DEFAULT 'builtin:carbonrag-cloud',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_provider_profiles (
    profile_id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    base_url TEXT,
    model_name TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    api_key_encrypted TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memory_notes (
    memory_note_id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS files (
    file_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_filename TEXT,
    file_ext TEXT,
    size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    sha256 TEXT,
    parse_status TEXT NOT NULL DEFAULT 'uploaded',
    parser_name TEXT,
    parser_version TEXT,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER,
    sheet_count INTEGER,
    slide_count INTEGER,
    error_message TEXT,
    updated_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS file_parse_results (
    file_id TEXT PRIMARY KEY,
    extracted_markdown TEXT,
    extracted_text TEXT,
    extracted_json_path TEXT,
    extracted_json TEXT,
    summary TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    parser_name TEXT,
    parser_version TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_knowledge_items (
    attachment_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    knowledge_item_id TEXT NOT NULL,
    attached_at TEXT NOT NULL,
    UNIQUE (session_id, knowledge_item_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_private_samples (
    attachment_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    attached_at TEXT NOT NULL,
    UNIQUE (session_id, doc_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    knowledge_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_item_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    library_scope TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    file_id TEXT,
    tenant_id TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    created_by TEXT,
    source TEXT,
    source_url TEXT,
    sample_type TEXT,
    business_topic TEXT,
    title TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    ingest_status TEXT NOT NULL,
    index_status TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    session_attachable INTEGER NOT NULL DEFAULT 1,
    source_hash TEXT,
    source_mtime TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_indexed_at TEXT,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_item_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    tenant_id TEXT,
    owner_user_id TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    created_by TEXT,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    library_scope TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    issued_at TEXT,
    region TEXT,
    doc_type TEXT,
    sample_type TEXT,
    business_topic TEXT,
    snippet TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE (knowledge_item_id, chunk_id),
    FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(knowledge_item_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rag_knowledge_bases (
    kb_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    name TEXT NOT NULL,
    description TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    retrieval_mode TEXT NOT NULL DEFAULT 'hybrid',
    embedding_model TEXT NOT NULL DEFAULT 'BAAI/bge-m3',
    chunk_size INTEGER NOT NULL DEFAULT 512,
    chunk_overlap INTEGER NOT NULL DEFAULT 64,
    parent_chunk_size INTEGER,
    rerank_top_n INTEGER NOT NULL DEFAULT 5,
    retrieval_top_k INTEGER NOT NULL DEFAULT 20,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rag_documents (
    doc_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL UNIQUE,
    kb_id TEXT NOT NULL,
    owner_user_id TEXT,
    knowledge_item_id TEXT,
    file_id TEXT,
    filename TEXT,
    file_type TEXT,
    file_size INTEGER,
    file_path TEXT,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    chunk_method TEXT NOT NULL DEFAULT 'recursive',
    parse_progress INTEGER NOT NULL DEFAULT 0,
    chunk_progress INTEGER NOT NULL DEFAULT 0,
    error_stage TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded',
    parse_status TEXT NOT NULL DEFAULT 'uploaded',
    chunk_status TEXT NOT NULL DEFAULT 'pending',
    index_status TEXT NOT NULL DEFAULT 'pending',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    indexed_chunk_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (kb_id) REFERENCES rag_knowledge_bases(kb_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(knowledge_item_id) ON DELETE SET NULL,
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    rag_chunk_id TEXT NOT NULL UNIQUE,
    kb_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    owner_user_id TEXT,
    knowledge_chunk_id TEXT,
    parent_chunk_id TEXT,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_estimate INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    questions_json TEXT NOT NULL DEFAULT '[]',
    milvus_id TEXT,
    page_number INTEGER,
    sheet_name TEXT,
    slide_number INTEGER,
    section_title TEXT,
    status TEXT NOT NULL DEFAULT 'chunked',
    vector_status TEXT NOT NULL DEFAULT 'pending',
    dense_vector_json TEXT,
    sparse_vector_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (kb_id) REFERENCES rag_knowledge_bases(kb_id) ON DELETE CASCADE,
    FOREIGN KEY (doc_id) REFERENCES rag_documents(doc_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rag_test_qa_runs (
    run_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    kb_id TEXT NOT NULL,
    owner_user_id TEXT,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    trace_json TEXT NOT NULL DEFAULT '{}',
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES rag_knowledge_bases(kb_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rag_eval_runs (
    run_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    kb_id TEXT,
    owner_user_id TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    passed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES rag_knowledge_bases(kb_id) ON DELETE SET NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rag_eval_cases (
    case_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    kb_id TEXT,
    question TEXT NOT NULL,
    expected_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    hit INTEGER NOT NULL DEFAULT 0,
    reciprocal_rank REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, case_id),
    FOREIGN KEY (run_id) REFERENCES rag_eval_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
    node_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    source_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    edge_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    workflow_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL UNIQUE,
    workflow_type TEXT NOT NULL,
    status TEXT NOT NULL,
    current_node TEXT,
    knowledge_item_id TEXT,
    tenant_id TEXT,
    owner_user_id TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(knowledge_item_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS workflow_nodes (
    node_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    status TEXT NOT NULL,
    input_ref TEXT,
    output_ref TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (workflow_id, node_id),
    FOREIGN KEY (workflow_id) REFERENCES workflow_runs(workflow_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS execution_checkpoints (
    checkpoint_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id TEXT NOT NULL UNIQUE,
    workflow_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    status TEXT,
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflow_runs(workflow_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_tasks (
    task_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    knowledge_item_id TEXT,
    owner_user_id TEXT,
    requested_by_user_id TEXT,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    error_detail TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(knowledge_item_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (requested_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS feedback_entries (
    feedback_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    target_type TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    session_id TEXT,
    rating TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_calculations (
    calculation_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL UNIQUE,
    inventory_id TEXT,
    owner_user_id TEXT,
    session_id TEXT,
    period_label TEXT,
    electricity_kwh REAL NOT NULL,
    natural_gas_m3 REAL NOT NULL,
    diesel_l REAL NOT NULL,
    total_emission_kgco2e REAL NOT NULL,
    breakdown_json TEXT NOT NULL,
    citations_json TEXT NOT NULL,
    factor_snapshot_json TEXT NOT NULL DEFAULT '[]',
    unit_conversion_trace_json TEXT NOT NULL DEFAULT '[]',
    formula_trace_json TEXT NOT NULL DEFAULT '[]',
    source_summary_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    activity_items_raw_json TEXT NOT NULL DEFAULT '[]',
    scope_summary_json TEXT NOT NULL DEFAULT '{}',
    activity_count INTEGER NOT NULL DEFAULT 0,
    official_factor_count INTEGER NOT NULL DEFAULT 0,
    fallback_factor_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_factor_sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_url TEXT,
    license TEXT,
    published_year INTEGER,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS carbon_factor_records (
    factor_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_id TEXT NOT NULL UNIQUE,
    source_id TEXT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    industry TEXT,
    scope TEXT NOT NULL,
    region TEXT,
    region_level TEXT,
    region_code TEXT,
    region_name TEXT,
    year INTEGER,
    effective_year INTEGER,
    gas TEXT,
    method_type TEXT,
    factor_value REAL NOT NULL,
    factor_unit TEXT NOT NULL,
    activity_unit TEXT NOT NULL,
    co2e_unit TEXT NOT NULL DEFAULT 'kgCO2e',
    quality TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    version TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES carbon_factor_sources(source_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_factor_catalog_entries (
    entry_id TEXT PRIMARY KEY,
    source_platform TEXT NOT NULL,
    source_url TEXT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    industry TEXT,
    region TEXT,
    year INTEGER,
    factor_unit TEXT,
    activity_unit TEXT,
    value_status TEXT NOT NULL,
    raw_value TEXT,
    factor_value REAL,
    source_title TEXT,
    publisher TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    is_calculation_ready INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS carbon_factor_aliases (
    alias_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_id TEXT NOT NULL UNIQUE,
    factor_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'zh-CN',
    FOREIGN KEY (factor_id) REFERENCES carbon_factor_records(factor_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS carbon_factor_import_jobs (
    job_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    source_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_inventories (
    inventory_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    session_id TEXT,
    organization_id TEXT,
    facility_id TEXT,
    period_start TEXT,
    period_end TEXT,
    inventory_standard TEXT NOT NULL,
    calculation_method TEXT NOT NULL,
    trace_id TEXT NOT NULL UNIQUE,
    activity_items_raw_json TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    total_kgco2e REAL NOT NULL,
    scope_summary_json TEXT NOT NULL,
    activity_count INTEGER NOT NULL DEFAULT 0,
    official_factor_count INTEGER NOT NULL DEFAULT 0,
    fallback_factor_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_activity_items (
    activity_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_item_id TEXT NOT NULL UNIQUE,
    inventory_id TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    scope TEXT NOT NULL,
    activity_category TEXT NOT NULL,
    activity_name TEXT NOT NULL,
    activity_value REAL NOT NULL,
    activity_unit TEXT NOT NULL,
    region TEXT,
    province TEXT,
    year INTEGER,
    data_quality TEXT NOT NULL,
    evidence_reference TEXT,
    source_document_id TEXT,
    entry_method TEXT NOT NULL,
    requested_factor_id TEXT,
    raw_payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inventory_id) REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS carbon_calculation_lines (
    line_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id TEXT NOT NULL UNIQUE,
    inventory_id TEXT NOT NULL,
    activity_item_id TEXT,
    scope TEXT,
    activity_category TEXT,
    activity_name TEXT,
    emission_kgco2e REAL NOT NULL,
    factor_id TEXT NOT NULL,
    line_payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inventory_id) REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
    FOREIGN KEY (activity_item_id) REFERENCES carbon_activity_items(activity_item_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_factor_snapshots (
    snapshot_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_snapshot_id TEXT NOT NULL UNIQUE,
    inventory_id TEXT NOT NULL,
    factor_id TEXT NOT NULL,
    factor_version TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    factor_value REAL NOT NULL,
    factor_unit TEXT NOT NULL,
    activity_unit TEXT NOT NULL,
    result_unit TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inventory_id) REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS carbon_evidence_references (
    evidence_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL UNIQUE,
    inventory_id TEXT NOT NULL,
    activity_item_id TEXT NOT NULL,
    data_quality TEXT NOT NULL,
    evidence_reference TEXT,
    source_document_id TEXT,
    entry_method TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inventory_id) REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
    FOREIGN KEY (activity_item_id) REFERENCES carbon_activity_items(activity_item_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS carbon_inventory_summaries (
    summary_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id TEXT NOT NULL UNIQUE,
    scope_summary_json TEXT NOT NULL,
    activity_count INTEGER NOT NULL DEFAULT 0,
    official_factor_count INTEGER NOT NULL DEFAULT 0,
    fallback_factor_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (inventory_id) REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    report_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT,
    session_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    output_format TEXT NOT NULL,
    citations_json TEXT NOT NULL,
    source_summary_json TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS report_sources (
    source_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    label TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS report_files (
    file_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL UNIQUE,
    owner_user_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    format TEXT NOT NULL,
    template_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_devices (
    device_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    role_scope TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    device_name TEXT NOT NULL,
    mac_hint TEXT,
    device_public_key TEXT NOT NULL,
    fingerprint_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    last_seen_at TEXT,
    revoked_at TEXT,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS edge_relay_sessions (
    relay_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    relay_session_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    device_id TEXT NOT NULL,
    status TEXT NOT NULL,
    connected_at TEXT NOT NULL,
    last_heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    server_ack_status TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES admin_devices(device_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_access_requests (
    request_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    admin_user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    device_name TEXT,
    mac_hint TEXT,
    device_public_key TEXT NOT NULL,
    fingerprint_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    FOREIGN KEY (admin_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (decided_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS management_action_requests (
    action_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    action_request_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    device_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    ack_token_hash TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES admin_devices(device_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS management_audit_logs (
    audit_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id TEXT NOT NULL UNIQUE,
    actor_user_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    device_id TEXT,
    action_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    decision TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS private_sample_catalog_overrides (
    doc_id TEXT PRIMARY KEY,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    session_attachable INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    updated_by_user_id TEXT,
    FOREIGN KEY (updated_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS knowledge_refresh_tasks (
    task_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by_user_id TEXT,
    summary TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (requested_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS policy_crawl_sources (
    source_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    source_label TEXT NOT NULL,
    allowed_domain TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    schedule_interval_seconds INTEGER,
    last_run_id TEXT,
    last_run_status TEXT,
    last_run_at TEXT,
    next_run_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS policy_crawl_runs (
    run_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    source_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    triggered_by_user_id TEXT,
    status TEXT NOT NULL,
    provider_name TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    document_count INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    error_detail TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (source_id) REFERENCES policy_crawl_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (triggered_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS policy_crawl_candidates (
    candidate_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    content_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_name TEXT,
    fetched_at TEXT,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL,
    reviewed_by_user_id TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    knowledge_item_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (source_id, url, content_hash),
    FOREIGN KEY (run_id) REFERENCES policy_crawl_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES policy_crawl_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(knowledge_item_id) ON DELETE SET NULL
);
"""

SQLITE_INDEX_SCRIPT = """
CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash
    ON auth_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
    ON auth_sessions(user_id, expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_username
    ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_display_name
    ON users(display_name)
    WHERE display_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_session_seq
    ON messages(session_id, message_seq);
CREATE INDEX IF NOT EXISTS idx_user_provider_profiles_owner_updated_at
    ON user_provider_profiles(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_notes_owner_updated_at
    ON memory_notes(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_owner_session_seq
    ON files(owner_user_id, session_id, file_seq);
CREATE INDEX IF NOT EXISTS idx_sessions_owner_updated_at
    ON sessions(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_knowledge_items_session_seq
    ON session_knowledge_items(session_id, attachment_seq DESC);
CREATE INDEX IF NOT EXISTS idx_private_samples_session_seq
    ON session_private_samples(session_id, attachment_seq DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_owner_scope_updated_at
    ON knowledge_items(owner_user_id, library_scope, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_status
    ON knowledge_items(index_status, parse_status, ingest_status);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_item_order
    ON knowledge_chunks(knowledge_item_id, order_index ASC);
CREATE INDEX IF NOT EXISTS idx_rag_kb_owner_updated
    ON rag_knowledge_bases(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_documents_kb_status
    ON rag_documents(kb_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_kb_doc_order
    ON rag_chunks(kb_id, doc_id, chunk_index ASC);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_vector_status
    ON rag_chunks(kb_id, vector_status);
CREATE INDEX IF NOT EXISTS idx_rag_test_qa_kb_created
    ON rag_test_qa_runs(kb_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_eval_runs_kb_created
    ON rag_eval_runs(kb_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_eval_cases_run
    ON rag_eval_cases(run_id, case_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_owner_type
    ON knowledge_graph_nodes(owner_user_id, node_type);
CREATE INDEX IF NOT EXISTS idx_kg_edges_source_type
    ON knowledge_graph_edges(source_node_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_tasks_status_created_at
    ON knowledge_tasks(status, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_knowledge_tasks_item_created_at
    ON knowledge_tasks(knowledge_item_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_item_updated_at
    ON workflow_runs(knowledge_item_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow_status
    ON workflow_nodes(workflow_id, status);
CREATE INDEX IF NOT EXISTS idx_execution_checkpoints_workflow_created
    ON execution_checkpoints(workflow_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_entries_owner_trace
    ON feedback_entries(owner_user_id, trace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_carbon_calculations_owner_session_created_at
    ON carbon_calculations(owner_user_id, session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_carbon_factor_records_search
    ON carbon_factor_records(is_enabled, category, industry, region_code, year);
CREATE INDEX IF NOT EXISTS idx_carbon_factor_records_source
    ON carbon_factor_records(source_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_carbon_factor_catalog_entries_search
    ON carbon_factor_catalog_entries(industry, category, value_status, year, is_calculation_ready);
CREATE INDEX IF NOT EXISTS idx_carbon_factor_aliases_factor
    ON carbon_factor_aliases(factor_id, alias);
CREATE INDEX IF NOT EXISTS idx_carbon_factor_import_jobs_owner_created
    ON carbon_factor_import_jobs(owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_carbon_inventories_owner_session_created_at
    ON carbon_inventories(owner_user_id, session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_carbon_activity_items_inventory_order
    ON carbon_activity_items(inventory_id, order_index ASC);
CREATE INDEX IF NOT EXISTS idx_carbon_lines_inventory
    ON carbon_calculation_lines(inventory_id, line_seq ASC);
CREATE INDEX IF NOT EXISTS idx_carbon_factor_snapshots_inventory
    ON carbon_factor_snapshots(inventory_id, snapshot_seq ASC);
CREATE INDEX IF NOT EXISTS idx_carbon_evidence_inventory
    ON carbon_evidence_references(inventory_id, evidence_seq ASC);
CREATE INDEX IF NOT EXISTS idx_reports_owner_session_updated_at
    ON reports(owner_user_id, session_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_sources_report_order
    ON report_sources(report_id, order_index ASC);
CREATE INDEX IF NOT EXISTS idx_report_files_owner_report_created
    ON report_files(owner_user_id, report_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_files_owner_file
    ON report_files(owner_user_id, file_id);
CREATE INDEX IF NOT EXISTS idx_admin_devices_owner_active
    ON admin_devices(owner_user_id, is_active, role_scope);
CREATE INDEX IF NOT EXISTS idx_admin_devices_fingerprint
    ON admin_devices(fingerprint_hash);
CREATE INDEX IF NOT EXISTS idx_edge_relay_sessions_user_status
    ON edge_relay_sessions(user_id, status, expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_access_requests_status
    ON admin_access_requests(status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_access_requests_admin_device
    ON admin_access_requests(admin_user_id, device_id);
CREATE INDEX IF NOT EXISTS idx_management_action_requests_user_status
    ON management_action_requests(user_id, status, expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_management_audit_logs_actor_created
    ON management_audit_logs(actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_private_sample_catalog_overrides_enabled
    ON private_sample_catalog_overrides(is_enabled, session_attachable);
CREATE INDEX IF NOT EXISTS idx_knowledge_refresh_tasks_scope_created_at
    ON knowledge_refresh_tasks(scope, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_crawl_sources_enabled
    ON policy_crawl_sources(is_enabled, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_crawl_runs_source_started
    ON policy_crawl_runs(source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_crawl_candidates_status_created
    ON policy_crawl_candidates(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_crawl_candidates_source_status
    ON policy_crawl_candidates(source_id, status, updated_at DESC);
"""

POSTGRES_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT UNIQUE,
        avatar_url TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        password_must_change BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_login_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        auth_session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
        pinned_at TEXT,
        knowledge_scope_last_used TEXT,
        source_summary_json TEXT,
        session_summary TEXT,
        summary_message_seq_upto BIGINT,
        summary_updated_at TEXT,
        summary_estimated_tokens INTEGER NOT NULL DEFAULT 0,
        compaction_status TEXT NOT NULL DEFAULT 'idle',
        last_compaction_error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        message_seq BIGSERIAL PRIMARY KEY,
        message_id TEXT NOT NULL UNIQUE,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        thinking_content TEXT,
        status TEXT,
        trace_id TEXT,
        citations_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        owner_user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
        appearance_json TEXT NOT NULL DEFAULT '{}',
        chat_json TEXT NOT NULL DEFAULT '{}',
        data_privacy_json TEXT NOT NULL DEFAULT '{}',
        advanced_json TEXT NOT NULL DEFAULT '{}',
        active_provider_ref TEXT NOT NULL DEFAULT 'builtin:carbonrag-cloud',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_provider_profiles (
        profile_id TEXT PRIMARY KEY,
        owner_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        provider_type TEXT NOT NULL,
        display_name TEXT NOT NULL,
        base_url TEXT,
        model_name TEXT,
        config_json TEXT NOT NULL DEFAULT '{}',
        api_key_encrypted TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_notes (
        memory_note_id TEXT PRIMARY KEY,
        owner_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS files (
        file_seq BIGSERIAL PRIMARY KEY,
        file_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        stored_filename TEXT,
        file_ext TEXT,
        size BIGINT NOT NULL,
        mime_type TEXT NOT NULL,
        stored_at TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        sha256 TEXT,
        parse_status TEXT NOT NULL DEFAULT 'uploaded',
        parser_name TEXT,
        parser_version TEXT,
        ocr_used BOOLEAN NOT NULL DEFAULT FALSE,
        page_count INTEGER,
        sheet_count INTEGER,
        slide_count INTEGER,
        error_message TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS file_parse_results (
        file_id TEXT PRIMARY KEY REFERENCES files(file_id) ON DELETE CASCADE,
        extracted_markdown TEXT,
        extracted_text TEXT,
        extracted_json_path TEXT,
        extracted_json TEXT,
        summary TEXT,
        chunk_count INTEGER NOT NULL DEFAULT 0,
        parser_name TEXT,
        parser_version TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_knowledge_items (
        attachment_seq BIGSERIAL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        knowledge_item_id TEXT NOT NULL,
        attached_at TEXT NOT NULL,
        UNIQUE (session_id, knowledge_item_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_private_samples (
        attachment_seq BIGSERIAL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        doc_id TEXT NOT NULL,
        attached_at TEXT NOT NULL,
        UNIQUE (session_id, doc_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_items (
        knowledge_seq BIGSERIAL PRIMARY KEY,
        knowledge_item_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        library_scope TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_ref TEXT,
        file_id TEXT REFERENCES files(file_id) ON DELETE SET NULL,
        tenant_id TEXT,
        visibility TEXT NOT NULL DEFAULT 'private',
        created_by TEXT,
        source TEXT,
        source_url TEXT,
        sample_type TEXT,
        business_topic TEXT,
        title TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        parse_status TEXT NOT NULL,
        ingest_status TEXT NOT NULL,
        index_status TEXT NOT NULL,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        session_attachable BOOLEAN NOT NULL DEFAULT TRUE,
        source_hash TEXT,
        source_mtime TEXT,
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_indexed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_chunks (
        chunk_seq BIGSERIAL PRIMARY KEY,
        knowledge_item_id TEXT NOT NULL REFERENCES knowledge_items(knowledge_item_id) ON DELETE CASCADE,
        chunk_id TEXT NOT NULL,
        tenant_id TEXT,
        owner_user_id TEXT,
        visibility TEXT NOT NULL DEFAULT 'private',
        created_by TEXT,
        title TEXT NOT NULL,
        source_type TEXT NOT NULL,
        library_scope TEXT NOT NULL,
        source TEXT NOT NULL,
        source_url TEXT,
        issued_at TEXT,
        region TEXT,
        doc_type TEXT,
        sample_type TEXT,
        business_topic TEXT,
        snippet TEXT NOT NULL,
        order_index INTEGER NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT,
        UNIQUE (knowledge_item_id, chunk_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_knowledge_bases (
        kb_seq BIGSERIAL PRIMARY KEY,
        kb_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        description TEXT,
        visibility TEXT NOT NULL DEFAULT 'private',
        retrieval_mode TEXT NOT NULL DEFAULT 'hybrid',
        embedding_model TEXT NOT NULL DEFAULT 'BAAI/bge-m3',
        chunk_size INTEGER NOT NULL DEFAULT 512,
        chunk_overlap INTEGER NOT NULL DEFAULT 64,
        parent_chunk_size INTEGER,
        rerank_top_n INTEGER NOT NULL DEFAULT 5,
        retrieval_top_k INTEGER NOT NULL DEFAULT 20,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_documents (
        doc_seq BIGSERIAL PRIMARY KEY,
        doc_id TEXT NOT NULL UNIQUE,
        kb_id TEXT NOT NULL REFERENCES rag_knowledge_bases(kb_id) ON DELETE CASCADE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        knowledge_item_id TEXT REFERENCES knowledge_items(knowledge_item_id) ON DELETE SET NULL,
        file_id TEXT REFERENCES files(file_id) ON DELETE SET NULL,
        filename TEXT,
        file_type TEXT,
        file_size INTEGER,
        file_path TEXT,
        title TEXT NOT NULL,
        source_type TEXT NOT NULL,
        chunk_method TEXT NOT NULL DEFAULT 'recursive',
        parse_progress INTEGER NOT NULL DEFAULT 0,
        chunk_progress INTEGER NOT NULL DEFAULT 0,
        error_stage TEXT,
        status TEXT NOT NULL DEFAULT 'uploaded',
        parse_status TEXT NOT NULL DEFAULT 'uploaded',
        chunk_status TEXT NOT NULL DEFAULT 'pending',
        index_status TEXT NOT NULL DEFAULT 'pending',
        chunk_count INTEGER NOT NULL DEFAULT 0,
        indexed_chunk_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_chunks (
        chunk_seq BIGSERIAL PRIMARY KEY,
        rag_chunk_id TEXT NOT NULL UNIQUE,
        kb_id TEXT NOT NULL REFERENCES rag_knowledge_bases(kb_id) ON DELETE CASCADE,
        doc_id TEXT NOT NULL REFERENCES rag_documents(doc_id) ON DELETE CASCADE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        knowledge_chunk_id TEXT,
        parent_chunk_id TEXT,
        chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        token_estimate INTEGER NOT NULL DEFAULT 0,
        token_count INTEGER NOT NULL DEFAULT 0,
        keywords_json TEXT NOT NULL DEFAULT '[]',
        questions_json TEXT NOT NULL DEFAULT '[]',
        milvus_id TEXT,
        page_number INTEGER,
        sheet_name TEXT,
        slide_number INTEGER,
        section_title TEXT,
        status TEXT NOT NULL DEFAULT 'chunked',
        vector_status TEXT NOT NULL DEFAULT 'pending',
        dense_vector_json TEXT,
        sparse_vector_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_test_qa_runs (
        run_seq BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        kb_id TEXT NOT NULL REFERENCES rag_knowledge_bases(kb_id) ON DELETE CASCADE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        query TEXT NOT NULL,
        answer TEXT NOT NULL,
        trace_json TEXT NOT NULL DEFAULT '{}',
        citations_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_eval_runs (
        run_seq BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        kb_id TEXT REFERENCES rag_knowledge_bases(kb_id) ON DELETE SET NULL,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        metrics_json TEXT NOT NULL DEFAULT '{}',
        passed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_eval_cases (
        case_seq BIGSERIAL PRIMARY KEY,
        case_id TEXT NOT NULL,
        run_id TEXT NOT NULL REFERENCES rag_eval_runs(run_id) ON DELETE CASCADE,
        kb_id TEXT,
        question TEXT NOT NULL,
        expected_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NOT NULL DEFAULT '{}',
        hit BOOLEAN NOT NULL DEFAULT FALSE,
        reciprocal_rank REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        UNIQUE (run_id, case_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
        node_seq BIGSERIAL PRIMARY KEY,
        node_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        node_type TEXT NOT NULL,
        label TEXT NOT NULL,
        source_ref TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
        edge_seq BIGSERIAL PRIMARY KEY,
        edge_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        source_node_id TEXT NOT NULL,
        target_node_id TEXT NOT NULL,
        edge_type TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_runs (
        workflow_seq BIGSERIAL PRIMARY KEY,
        workflow_id TEXT NOT NULL UNIQUE,
        workflow_type TEXT NOT NULL,
        status TEXT NOT NULL,
        current_node TEXT,
        knowledge_item_id TEXT REFERENCES knowledge_items(knowledge_item_id) ON DELETE SET NULL,
        tenant_id TEXT,
        owner_user_id TEXT,
        visibility TEXT NOT NULL DEFAULT 'private',
        created_by TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        error_message TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_nodes (
        node_seq BIGSERIAL PRIMARY KEY,
        workflow_id TEXT NOT NULL REFERENCES workflow_runs(workflow_id) ON DELETE CASCADE,
        node_id TEXT NOT NULL,
        node_type TEXT NOT NULL,
        status TEXT NOT NULL,
        input_ref TEXT,
        output_ref TEXT,
        started_at TEXT,
        finished_at TEXT,
        error_message TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        depends_on_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE (workflow_id, node_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_checkpoints (
        checkpoint_seq BIGSERIAL PRIMARY KEY,
        checkpoint_id TEXT NOT NULL UNIQUE,
        workflow_id TEXT NOT NULL REFERENCES workflow_runs(workflow_id) ON DELETE CASCADE,
        node_id TEXT NOT NULL,
        status TEXT,
        state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_tasks (
        task_seq BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL UNIQUE,
        knowledge_item_id TEXT REFERENCES knowledge_items(knowledge_item_id) ON DELETE CASCADE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        requested_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        task_type TEXT NOT NULL,
        status TEXT NOT NULL,
        summary TEXT,
        error_detail TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback_entries (
        feedback_seq BIGSERIAL PRIMARY KEY,
        feedback_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        target_type TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        session_id TEXT,
        rating TEXT NOT NULL,
        comment TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_calculations (
        calculation_seq BIGSERIAL PRIMARY KEY,
        trace_id TEXT NOT NULL UNIQUE,
        inventory_id TEXT,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        session_id TEXT,
        period_label TEXT,
        electricity_kwh DOUBLE PRECISION NOT NULL,
        natural_gas_m3 DOUBLE PRECISION NOT NULL,
        diesel_l DOUBLE PRECISION NOT NULL,
        total_emission_kgco2e DOUBLE PRECISION NOT NULL,
        breakdown_json TEXT NOT NULL,
        citations_json TEXT NOT NULL,
        factor_snapshot_json TEXT NOT NULL DEFAULT '[]',
        unit_conversion_trace_json TEXT NOT NULL DEFAULT '[]',
        formula_trace_json TEXT NOT NULL DEFAULT '[]',
        source_summary_json TEXT NOT NULL DEFAULT '[]',
        warnings_json TEXT NOT NULL DEFAULT '[]',
        activity_items_raw_json TEXT NOT NULL DEFAULT '[]',
        scope_summary_json TEXT NOT NULL DEFAULT '{}',
        activity_count INTEGER NOT NULL DEFAULT 0,
        official_factor_count INTEGER NOT NULL DEFAULT 0,
        fallback_factor_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_factor_sources (
        source_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        publisher TEXT NOT NULL,
        source_url TEXT,
        license TEXT,
        published_year INTEGER,
        source_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_factor_records (
        factor_seq BIGSERIAL PRIMARY KEY,
        factor_id TEXT NOT NULL UNIQUE,
        source_id TEXT REFERENCES carbon_factor_sources(source_id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        industry TEXT,
        scope TEXT NOT NULL,
        region TEXT,
        region_level TEXT,
        region_code TEXT,
        region_name TEXT,
        year INTEGER,
        effective_year INTEGER,
        gas TEXT,
        method_type TEXT,
        factor_value DOUBLE PRECISION NOT NULL,
        factor_unit TEXT NOT NULL,
        activity_unit TEXT NOT NULL,
        co2e_unit TEXT NOT NULL DEFAULT 'kgCO2e',
        quality TEXT NOT NULL,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        version TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_factor_catalog_entries (
        entry_id TEXT PRIMARY KEY,
        source_platform TEXT NOT NULL,
        source_url TEXT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        industry TEXT,
        region TEXT,
        year INTEGER,
        factor_unit TEXT,
        activity_unit TEXT,
        value_status TEXT NOT NULL,
        raw_value TEXT,
        factor_value DOUBLE PRECISION,
        source_title TEXT,
        publisher TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        is_calculation_ready BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_factor_aliases (
        alias_seq BIGSERIAL PRIMARY KEY,
        alias_id TEXT NOT NULL UNIQUE,
        factor_id TEXT NOT NULL REFERENCES carbon_factor_records(factor_id) ON DELETE CASCADE,
        alias TEXT NOT NULL,
        locale TEXT NOT NULL DEFAULT 'zh-CN'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_factor_import_jobs (
        job_seq BIGSERIAL PRIMARY KEY,
        job_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        source_kind TEXT NOT NULL,
        status TEXT NOT NULL,
        summary_json TEXT NOT NULL DEFAULT '{}',
        error_message TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_inventories (
        inventory_seq BIGSERIAL PRIMARY KEY,
        inventory_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        session_id TEXT,
        organization_id TEXT,
        facility_id TEXT,
        period_start TEXT,
        period_end TEXT,
        inventory_standard TEXT NOT NULL,
        calculation_method TEXT NOT NULL,
        trace_id TEXT NOT NULL UNIQUE,
        activity_items_raw_json TEXT NOT NULL,
        raw_payload_json TEXT NOT NULL,
        total_kgco2e DOUBLE PRECISION NOT NULL,
        scope_summary_json TEXT NOT NULL,
        activity_count INTEGER NOT NULL DEFAULT 0,
        official_factor_count INTEGER NOT NULL DEFAULT 0,
        fallback_factor_count INTEGER NOT NULL DEFAULT 0,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_activity_items (
        activity_seq BIGSERIAL PRIMARY KEY,
        activity_item_id TEXT NOT NULL UNIQUE,
        inventory_id TEXT NOT NULL REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
        order_index INTEGER NOT NULL,
        scope TEXT NOT NULL,
        activity_category TEXT NOT NULL,
        activity_name TEXT NOT NULL,
        activity_value DOUBLE PRECISION NOT NULL,
        activity_unit TEXT NOT NULL,
        region TEXT,
        province TEXT,
        year INTEGER,
        data_quality TEXT NOT NULL,
        evidence_reference TEXT,
        source_document_id TEXT,
        entry_method TEXT NOT NULL,
        requested_factor_id TEXT,
        raw_payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_calculation_lines (
        line_seq BIGSERIAL PRIMARY KEY,
        line_id TEXT NOT NULL UNIQUE,
        inventory_id TEXT NOT NULL REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
        activity_item_id TEXT REFERENCES carbon_activity_items(activity_item_id) ON DELETE SET NULL,
        scope TEXT,
        activity_category TEXT,
        activity_name TEXT,
        emission_kgco2e DOUBLE PRECISION NOT NULL,
        factor_id TEXT NOT NULL,
        line_payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_factor_snapshots (
        snapshot_seq BIGSERIAL PRIMARY KEY,
        factor_snapshot_id TEXT NOT NULL UNIQUE,
        inventory_id TEXT NOT NULL REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
        factor_id TEXT NOT NULL,
        factor_version TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_url TEXT,
        factor_value DOUBLE PRECISION NOT NULL,
        factor_unit TEXT NOT NULL,
        activity_unit TEXT NOT NULL,
        result_unit TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_evidence_references (
        evidence_seq BIGSERIAL PRIMARY KEY,
        evidence_id TEXT NOT NULL UNIQUE,
        inventory_id TEXT NOT NULL REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
        activity_item_id TEXT NOT NULL REFERENCES carbon_activity_items(activity_item_id) ON DELETE CASCADE,
        data_quality TEXT NOT NULL,
        evidence_reference TEXT,
        source_document_id TEXT,
        entry_method TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS carbon_inventory_summaries (
        summary_seq BIGSERIAL PRIMARY KEY,
        inventory_id TEXT NOT NULL UNIQUE REFERENCES carbon_inventories(inventory_id) ON DELETE CASCADE,
        scope_summary_json TEXT NOT NULL,
        activity_count INTEGER NOT NULL DEFAULT 0,
        official_factor_count INTEGER NOT NULL DEFAULT 0,
        fallback_factor_count INTEGER NOT NULL DEFAULT 0,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_seq BIGSERIAL PRIMARY KEY,
        report_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        report_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        output_format TEXT NOT NULL,
        citations_json TEXT NOT NULL,
        source_summary_json TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS report_sources (
        source_seq BIGSERIAL PRIMARY KEY,
        report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
        source_type TEXT NOT NULL,
        source_ref TEXT NOT NULL,
        label TEXT NOT NULL,
        order_index INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS report_files (
        file_seq BIGSERIAL PRIMARY KEY,
        file_id TEXT NOT NULL UNIQUE,
        owner_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        format TEXT NOT NULL,
        template_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        content_type TEXT NOT NULL,
        file_size_bytes BIGINT NOT NULL,
        checksum_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_devices (
        device_seq BIGSERIAL PRIMARY KEY,
        device_id TEXT NOT NULL UNIQUE,
        role_scope TEXT NOT NULL,
        owner_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        device_name TEXT NOT NULL,
        mac_hint TEXT,
        device_public_key TEXT NOT NULL,
        fingerprint_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        approved_by TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        approved_at TEXT,
        created_at TEXT NOT NULL,
        last_seen_at TEXT,
        revoked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edge_relay_sessions (
        relay_seq BIGSERIAL PRIMARY KEY,
        relay_session_id TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        device_id TEXT NOT NULL REFERENCES admin_devices(device_id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        connected_at TEXT NOT NULL,
        last_heartbeat_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        server_ack_status TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_access_requests (
        request_seq BIGSERIAL PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        admin_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        device_id TEXT NOT NULL,
        device_name TEXT,
        mac_hint TEXT,
        device_public_key TEXT NOT NULL,
        fingerprint_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        decided_by TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        decided_at TEXT,
        decision_note TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS management_action_requests (
        action_seq BIGSERIAL PRIMARY KEY,
        action_request_id TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        device_id TEXT NOT NULL REFERENCES admin_devices(device_id) ON DELETE CASCADE,
        action_type TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        ack_token_hash TEXT,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        decided_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS management_audit_logs (
        audit_seq BIGSERIAL PRIMARY KEY,
        audit_id TEXT NOT NULL UNIQUE,
        actor_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        actor_role TEXT NOT NULL,
        device_id TEXT,
        action_type TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        decision TEXT NOT NULL,
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS private_sample_catalog_overrides (
        doc_id TEXT PRIMARY KEY,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        session_attachable BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at TEXT NOT NULL,
        updated_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_refresh_tasks (
        task_seq BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL UNIQUE,
        scope TEXT NOT NULL,
        status TEXT NOT NULL,
        requested_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        summary TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_crawl_sources (
        source_seq BIGSERIAL PRIMARY KEY,
        source_id TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        source_url TEXT NOT NULL UNIQUE,
        source_label TEXT NOT NULL,
        allowed_domain TEXT NOT NULL,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        schedule_interval_seconds INTEGER,
        last_run_id TEXT,
        last_run_status TEXT,
        last_run_at TEXT,
        next_run_at TEXT,
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_crawl_runs (
        run_seq BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        source_id TEXT NOT NULL REFERENCES policy_crawl_sources(source_id) ON DELETE CASCADE,
        trigger_type TEXT NOT NULL,
        triggered_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        status TEXT NOT NULL,
        provider_name TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        document_count INTEGER NOT NULL DEFAULT 0,
        candidate_count INTEGER NOT NULL DEFAULT 0,
        error_detail TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_crawl_candidates (
        candidate_seq BIGSERIAL PRIMARY KEY,
        candidate_id TEXT NOT NULL UNIQUE,
        run_id TEXT NOT NULL REFERENCES policy_crawl_runs(run_id) ON DELETE CASCADE,
        source_id TEXT NOT NULL REFERENCES policy_crawl_sources(source_id) ON DELETE CASCADE,
        url TEXT NOT NULL,
        title TEXT,
        content_type TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        source_name TEXT,
        fetched_at TEXT,
        storage_path TEXT NOT NULL,
        status TEXT NOT NULL,
        reviewed_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        reviewed_at TEXT,
        review_note TEXT,
        knowledge_item_id TEXT REFERENCES knowledge_items(knowledge_item_id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE (source_id, url, content_hash)
    )
    """,
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS pinned_at TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS stored_filename TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS file_ext TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS sha256 TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS parse_status TEXT NOT NULL DEFAULT 'uploaded'",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS parser_name TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS parser_version TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS ocr_used BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS page_count INTEGER",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS sheet_count INTEGER",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS slide_count INTEGER",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS error_message TEXT",
    "ALTER TABLE files ADD COLUMN IF NOT EXISTS updated_at TEXT",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS thinking_content TEXT",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS session_summary TEXT",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary_message_seq_upto BIGINT",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary_updated_at TEXT",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary_estimated_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS compaction_status TEXT NOT NULL DEFAULT 'idle'",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_compaction_error TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS tenant_id TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private'",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS created_by TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS source TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS source_url TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS sample_type TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS business_topic TEXT",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS tenant_id TEXT",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private'",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS created_by TEXT",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS updated_at TEXT",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE feedback_entries ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS inventory_id TEXT",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS factor_snapshot_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS unit_conversion_trace_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS formula_trace_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS source_summary_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS warnings_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS activity_items_raw_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS scope_summary_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS activity_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS official_factor_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE carbon_calculations ADD COLUMN IF NOT EXISTS fallback_factor_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE carbon_factor_records ADD COLUMN IF NOT EXISTS gas TEXT",
    "ALTER TABLE carbon_factor_records ADD COLUMN IF NOT EXISTS effective_year INTEGER",
    "ALTER TABLE carbon_factor_records ADD COLUMN IF NOT EXISTS method_type TEXT",
    "ALTER TABLE carbon_factor_records ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS owner_user_id TEXT",
    "ALTER TABLE rag_knowledge_bases ADD COLUMN IF NOT EXISTS embedding_model TEXT NOT NULL DEFAULT 'BAAI/bge-m3'",
    "ALTER TABLE rag_knowledge_bases ADD COLUMN IF NOT EXISTS chunk_size INTEGER NOT NULL DEFAULT 512",
    "ALTER TABLE rag_knowledge_bases ADD COLUMN IF NOT EXISTS chunk_overlap INTEGER NOT NULL DEFAULT 64",
    "ALTER TABLE rag_knowledge_bases ADD COLUMN IF NOT EXISTS parent_chunk_size INTEGER",
    "ALTER TABLE rag_knowledge_bases ADD COLUMN IF NOT EXISTS rerank_top_n INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE rag_knowledge_bases ADD COLUMN IF NOT EXISTS retrieval_top_k INTEGER NOT NULL DEFAULT 20",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS filename TEXT",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS file_type TEXT",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS file_size INTEGER",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS file_path TEXT",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS chunk_method TEXT NOT NULL DEFAULT 'recursive'",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS parse_progress INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS chunk_progress INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS error_stage TEXT",
    "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS token_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS keywords_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS questions_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS milvus_id TEXT",
    """
    CREATE TABLE IF NOT EXISTS rag_eval_runs (
        run_seq BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        kb_id TEXT REFERENCES rag_knowledge_bases(kb_id) ON DELETE SET NULL,
        owner_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
        metrics_json TEXT NOT NULL DEFAULT '{}',
        passed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_eval_cases (
        case_seq BIGSERIAL PRIMARY KEY,
        case_id TEXT NOT NULL,
        run_id TEXT NOT NULL REFERENCES rag_eval_runs(run_id) ON DELETE CASCADE,
        kb_id TEXT,
        question TEXT NOT NULL,
        expected_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NOT NULL DEFAULT '{}',
        hit BOOLEAN NOT NULL DEFAULT FALSE,
        reciprocal_rank REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        UNIQUE (run_id, case_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash ON auth_sessions(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id, expires_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_display_name ON users(display_name) WHERE display_name IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, message_seq)",
    "CREATE INDEX IF NOT EXISTS idx_user_provider_profiles_owner_updated_at ON user_provider_profiles(owner_user_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memory_notes_owner_updated_at ON memory_notes(owner_user_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_files_owner_session_seq ON files(owner_user_id, session_id, file_seq)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_owner_updated_at ON sessions(owner_user_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_knowledge_items_session_seq ON session_knowledge_items(session_id, attachment_seq DESC)",
    "CREATE INDEX IF NOT EXISTS idx_private_samples_session_seq ON session_private_samples(session_id, attachment_seq DESC)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_items_owner_scope_updated_at ON knowledge_items(owner_user_id, library_scope, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_items_status ON knowledge_items(index_status, parse_status, ingest_status)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_item_order ON knowledge_chunks(knowledge_item_id, order_index ASC)",
    "CREATE INDEX IF NOT EXISTS idx_rag_kb_owner_updated ON rag_knowledge_bases(owner_user_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_rag_documents_kb_status ON rag_documents(kb_id, status, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_kb_doc_order ON rag_chunks(kb_id, doc_id, chunk_index ASC)",
    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_vector_status ON rag_chunks(kb_id, vector_status)",
    "CREATE INDEX IF NOT EXISTS idx_rag_test_qa_kb_created ON rag_test_qa_runs(kb_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_rag_eval_runs_kb_created ON rag_eval_runs(kb_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_rag_eval_cases_run ON rag_eval_cases(run_id, case_id)",
    "CREATE INDEX IF NOT EXISTS idx_kg_nodes_owner_type ON knowledge_graph_nodes(owner_user_id, node_type)",
    "CREATE INDEX IF NOT EXISTS idx_kg_edges_source_type ON knowledge_graph_edges(source_node_id, edge_type)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_tasks_status_created_at ON knowledge_tasks(status, created_at ASC)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_tasks_item_created_at ON knowledge_tasks(knowledge_item_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_runs_item_updated_at ON workflow_runs(knowledge_item_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow_status ON workflow_nodes(workflow_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_execution_checkpoints_workflow_created ON execution_checkpoints(workflow_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_entries_owner_trace ON feedback_entries(owner_user_id, trace_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_calculations_owner_session_created_at ON carbon_calculations(owner_user_id, session_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_factor_records_search ON carbon_factor_records(is_enabled, category, industry, region_code, year)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_factor_records_source ON carbon_factor_records(source_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_factor_catalog_entries_search ON carbon_factor_catalog_entries(industry, category, value_status, year, is_calculation_ready)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_factor_aliases_factor ON carbon_factor_aliases(factor_id, alias)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_factor_import_jobs_owner_created ON carbon_factor_import_jobs(owner_user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_inventories_owner_session_created_at ON carbon_inventories(owner_user_id, session_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_activity_items_inventory_order ON carbon_activity_items(inventory_id, order_index ASC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_lines_inventory ON carbon_calculation_lines(inventory_id, line_seq ASC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_factor_snapshots_inventory ON carbon_factor_snapshots(inventory_id, snapshot_seq ASC)",
    "CREATE INDEX IF NOT EXISTS idx_carbon_evidence_inventory ON carbon_evidence_references(inventory_id, evidence_seq ASC)",
    "CREATE INDEX IF NOT EXISTS idx_reports_owner_session_updated_at ON reports(owner_user_id, session_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_report_sources_report_order ON report_sources(report_id, order_index ASC)",
    "CREATE INDEX IF NOT EXISTS idx_report_files_owner_report_created ON report_files(owner_user_id, report_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_report_files_owner_file ON report_files(owner_user_id, file_id)",
    "CREATE INDEX IF NOT EXISTS idx_admin_devices_owner_active ON admin_devices(owner_user_id, is_active, role_scope)",
    "CREATE INDEX IF NOT EXISTS idx_admin_devices_fingerprint ON admin_devices(fingerprint_hash)",
    "CREATE INDEX IF NOT EXISTS idx_edge_relay_sessions_user_status ON edge_relay_sessions(user_id, status, expires_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_admin_access_requests_status ON admin_access_requests(status, requested_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_admin_access_requests_admin_device ON admin_access_requests(admin_user_id, device_id)",
    "CREATE INDEX IF NOT EXISTS idx_management_action_requests_user_status ON management_action_requests(user_id, status, expires_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_management_audit_logs_actor_created ON management_audit_logs(actor_user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_private_sample_catalog_overrides_enabled ON private_sample_catalog_overrides(is_enabled, session_attachable)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_refresh_tasks_scope_created_at ON knowledge_refresh_tasks(scope, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_policy_crawl_sources_enabled ON policy_crawl_sources(is_enabled, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_policy_crawl_runs_source_started ON policy_crawl_runs(source_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_policy_crawl_candidates_status_created ON policy_crawl_candidates(status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_policy_crawl_candidates_source_status ON policy_crawl_candidates(source_id, status, updated_at DESC)",
)


def ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SQLITE_SCHEMA_SCRIPT)
    _ensure_sqlite_column(connection, "users", "display_name", "TEXT")
    _ensure_sqlite_column(connection, "users", "avatar_url", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "is_pinned", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "sessions", "pinned_at", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "knowledge_scope_last_used", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "source_summary_json", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "session_summary", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "summary_message_seq_upto", "INTEGER")
    _ensure_sqlite_column(connection, "sessions", "summary_updated_at", "TEXT")
    _ensure_sqlite_column(connection, "sessions", "summary_estimated_tokens", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "sessions", "compaction_status", "TEXT NOT NULL DEFAULT 'idle'")
    _ensure_sqlite_column(connection, "sessions", "last_compaction_error", "TEXT")
    _ensure_sqlite_column(connection, "messages", "thinking_content", "TEXT")
    _ensure_sqlite_column(connection, "files", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "files", "stored_filename", "TEXT")
    _ensure_sqlite_column(connection, "files", "file_ext", "TEXT")
    _ensure_sqlite_column(connection, "files", "sha256", "TEXT")
    _ensure_sqlite_column(connection, "files", "parse_status", "TEXT NOT NULL DEFAULT 'uploaded'")
    _ensure_sqlite_column(connection, "files", "parser_name", "TEXT")
    _ensure_sqlite_column(connection, "files", "parser_version", "TEXT")
    _ensure_sqlite_column(connection, "files", "ocr_used", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "files", "page_count", "INTEGER")
    _ensure_sqlite_column(connection, "files", "sheet_count", "INTEGER")
    _ensure_sqlite_column(connection, "files", "slide_count", "INTEGER")
    _ensure_sqlite_column(connection, "files", "error_message", "TEXT")
    _ensure_sqlite_column(connection, "files", "updated_at", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "tenant_id", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "visibility", "TEXT NOT NULL DEFAULT 'private'")
    _ensure_sqlite_column(connection, "knowledge_items", "created_by", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "source", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "source_url", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "sample_type", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_items", "business_topic", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_chunks", "tenant_id", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_chunks", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_chunks", "visibility", "TEXT NOT NULL DEFAULT 'private'")
    _ensure_sqlite_column(connection, "knowledge_chunks", "created_by", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_chunks", "updated_at", "TEXT")
    _ensure_sqlite_column(connection, "knowledge_chunks", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_sqlite_column(connection, "feedback_entries", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "carbon_calculations", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "carbon_calculations", "inventory_id", "TEXT")
    _ensure_sqlite_column(connection, "carbon_calculations", "factor_snapshot_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "carbon_calculations", "unit_conversion_trace_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "carbon_calculations", "formula_trace_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "carbon_calculations", "source_summary_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "carbon_calculations", "warnings_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "carbon_calculations", "activity_items_raw_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "carbon_calculations", "scope_summary_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_sqlite_column(connection, "carbon_calculations", "activity_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "carbon_calculations", "official_factor_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "carbon_calculations", "fallback_factor_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "carbon_factor_records", "gas", "TEXT")
    _ensure_sqlite_column(connection, "carbon_factor_records", "effective_year", "INTEGER")
    _ensure_sqlite_column(connection, "carbon_factor_records", "method_type", "TEXT")
    _ensure_sqlite_column(connection, "carbon_factor_records", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_sqlite_column(connection, "reports", "owner_user_id", "TEXT")
    _ensure_sqlite_column(connection, "rag_knowledge_bases", "embedding_model", "TEXT NOT NULL DEFAULT 'BAAI/bge-m3'")
    _ensure_sqlite_column(connection, "rag_knowledge_bases", "chunk_size", "INTEGER NOT NULL DEFAULT 512")
    _ensure_sqlite_column(connection, "rag_knowledge_bases", "chunk_overlap", "INTEGER NOT NULL DEFAULT 64")
    _ensure_sqlite_column(connection, "rag_knowledge_bases", "parent_chunk_size", "INTEGER")
    _ensure_sqlite_column(connection, "rag_knowledge_bases", "rerank_top_n", "INTEGER NOT NULL DEFAULT 5")
    _ensure_sqlite_column(connection, "rag_knowledge_bases", "retrieval_top_k", "INTEGER NOT NULL DEFAULT 20")
    _ensure_sqlite_column(connection, "rag_documents", "filename", "TEXT")
    _ensure_sqlite_column(connection, "rag_documents", "file_type", "TEXT")
    _ensure_sqlite_column(connection, "rag_documents", "file_size", "INTEGER")
    _ensure_sqlite_column(connection, "rag_documents", "file_path", "TEXT")
    _ensure_sqlite_column(connection, "rag_documents", "chunk_method", "TEXT NOT NULL DEFAULT 'recursive'")
    _ensure_sqlite_column(connection, "rag_documents", "parse_progress", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "rag_documents", "chunk_progress", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "rag_documents", "error_stage", "TEXT")
    _ensure_sqlite_column(connection, "rag_chunks", "token_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_sqlite_column(connection, "rag_chunks", "keywords_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "rag_chunks", "questions_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_sqlite_column(connection, "rag_chunks", "milvus_id", "TEXT")
    connection.executescript(SQLITE_INDEX_SCRIPT)


def _ensure_sqlite_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_postgres_schema(connection) -> None:
    with connection.cursor() as cursor:
        for statement in POSTGRES_SCHEMA_STATEMENTS:
            cursor.execute(statement)
