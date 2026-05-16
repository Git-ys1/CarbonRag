import type { UserRole } from "./auth";

export interface AdminUserSummary {
    user_id: string;
    username: string;
    display_name: string;
    role: UserRole;
    is_active: boolean;
    password_must_change: boolean;
    created_at: string;
    last_login_at: string | null;
    session_count: number;
    report_count: number;
    feedback_count: number;
}

export interface CreateAdminUserRequest {
    username: string;
    display_name?: string | null;
    password: string;
    role: "user" | "admin" | "super_admin";
}

export interface UpdateAdminUserRequest {
    role: UserRole;
    is_active: boolean;
}

export interface DeleteAdminUsersRequest {
    user_ids: string[];
    current_password: string;
}

export interface DeleteAdminUsersResponse {
    status: "ok";
    deleted_user_ids: string[];
}

export interface ResetPasswordResponse {
    status: "ok";
    temporary_password: string;
}

export interface AdminFeedbackRecentEntry {
    feedback_id: string;
    target_type: string;
    rating: string;
    session_id: string | null;
    owner_user_id: string | null;
    created_at: string;
}

export interface AdminFeedbackOverview {
    total_count: number;
    ask_up_count: number;
    ask_down_count: number;
    calc_up_count: number;
    calc_down_count: number;
    recent_entries: AdminFeedbackRecentEntry[];
}

export interface AdminPrivateSampleItem {
    doc_id: string;
    title: string;
    source_type: string;
    sample_type: string;
    business_topic: string;
    session_attachable: boolean;
    is_enabled: boolean;
}

export interface PolicyShowcaseSourceSummary {
    source_id: string;
    title: string;
    source_url: string;
    source_label: string;
    description: string;
    default_query: string;
    content_type: string;
    metadata: Record<string, unknown>;
}

export interface PolicyShowcaseWorkflowNodeSummary {
    node_id: string;
    node_type: string;
    status: string;
    input_ref: string | null;
    output_ref: string | null;
    started_at: string | null;
    finished_at: string | null;
    error_message: string | null;
    retry_count: number;
    metadata: Record<string, unknown>;
}

export interface PolicyShowcaseWorkflowSummary {
    workflow_id: string;
    workflow_type: string;
    status: string;
    current_node: string | null;
    error_message: string | null;
    created_at: string;
    updated_at: string;
    nodes: PolicyShowcaseWorkflowNodeSummary[];
}

export interface PolicyShowcaseChunkSummary {
    chunk_id: string;
    knowledge_item_id: string;
    title: string;
    source_type: string;
    source: string;
    source_url: string | null;
    issued_at: string | null;
    region: string | null;
    doc_type: string | null;
    snippet: string;
    order_index: number;
    metadata: Record<string, unknown>;
}

export interface PolicyShowcaseRetrievalHit {
    chunk_id: string;
    knowledge_item_id: string | null;
    title: string;
    source_type: string;
    source: string;
    source_url: string | null;
    issued_at: string | null;
    region: string | null;
    doc_type: string | null;
    snippet: string;
    score: number;
    matched_source: boolean;
}

export interface PolicyShowcaseRetrievalPreview {
    source_id: string;
    query: string;
    top_k: number;
    total_hits: number;
    hits: PolicyShowcaseRetrievalHit[];
}

export interface PolicyShowcaseStatus {
    source: PolicyShowcaseSourceSummary;
    item: import("./knowledge").KnowledgeItem | null;
    latest_task: import("./knowledge").KnowledgeTask | null;
    workflow: PolicyShowcaseWorkflowSummary | null;
    chunks: PolicyShowcaseChunkSummary[];
    retrieval_preview: PolicyShowcaseRetrievalPreview | null;
    indexed: boolean;
}

export type PolicyCrawlerCandidateStatus = "pending_review" | "published" | "rejected";

export interface PolicyCrawlerSourceSummary {
    source_id: string;
    title: string;
    source_url: string;
    source_label: string;
    allowed_domain: string;
    is_enabled: boolean;
    schedule_interval_seconds: number | null;
    last_run_id: string | null;
    last_run_status: string | null;
    last_run_at: string | null;
    next_run_at: string | null;
    last_error: string | null;
    metadata: Record<string, unknown>;
    source_category?: string | null;
    region?: string | null;
    priority?: number | null;
    topic_tags?: string[];
    parser_profile?: string | null;
    review_required?: boolean | null;
    target_rag_kb_id?: string | null;
    recommendation_reason?: string | null;
    risk_level?: string | null;
}

export interface PolicyCrawlerSourceUpsertRequest {
    source_id: string;
    title: string;
    source_url: string;
    source_label: string;
    allowed_domain?: string | null;
    is_enabled?: boolean;
    schedule_interval_seconds?: number | null;
    source_category?: string | null;
    region?: string | null;
    priority?: number;
    topic_tags?: string[];
    start_urls?: string[];
    extra_start_urls?: string[];
    include_patterns?: string[];
    exclude_patterns?: string[];
    required_keywords?: string[];
    optional_keywords?: string[];
    crawl_mode?: string;
    parser_profile?: string;
    max_depth?: number;
    max_pages?: number;
    download_delay_seconds?: number;
    schedule_enabled?: boolean;
    review_required?: boolean;
    target_rag_kb_id?: string | null;
    metadata?: Record<string, unknown>;
}

export interface PolicyCrawlerDryRunCandidateSummary {
    url: string;
    title: string | null;
    content_type: string;
    http_status: number | null;
    matched_keywords: string[];
    skip_reason: string | null;
    candidate_quality_score: number;
    quality_breakdown: Record<string, number>;
    cleaned_markdown_preview: string;
    estimated_chunk_count: number;
    target_rag_kb_id: string | null;
    canonical_url: string | null;
}

export interface PolicyCrawlerDryRunSummary {
    source_id: string;
    status: string;
    provider_name: string | null;
    start_urls: string[];
    robots_obey: boolean;
    candidate_count: number;
    skipped_count: number;
    target_rag_kb_id: string | null;
    candidates: PolicyCrawlerDryRunCandidateSummary[];
    errors: string[];
    metadata: Record<string, unknown>;
}

export interface PolicyCrawlerRecommendedImportSummary {
    imported_count: number;
    enabled_count: number;
    sources: PolicyCrawlerSourceSummary[];
}

export interface PolicyCrawlerRunRequest {
    auto_rag_ingest_enabled?: boolean;
    auto_rag_ingest_min_quality?: number;
    auto_rag_ingest_min_extraction?: number;
    auto_rag_ingest_min_markdown_size?: number;
    auto_rag_ingest_skip_duplicate?: boolean;
}

export interface PolicyCrawlerRunSummary {
    run_id: string;
    source_id: string;
    trigger_type: string;
    triggered_by_user_id: string | null;
    status: string;
    provider_name: string | null;
    started_at: string;
    finished_at: string | null;
    document_count: number;
    candidate_count: number;
    error_detail: string | null;
    metadata: Record<string, unknown>;
    auto_rag_attempted_count?: number;
    auto_rag_indexed_count?: number;
    auto_rag_failed_count?: number;
    auto_rag_skipped_count?: number;
    target_kb_id?: string | null;
    target_kb_name?: string | null;
}

export interface PolicyCrawlerRunPage {
    items: PolicyCrawlerRunSummary[];
    total: number;
    page: number;
    page_size: number;
}

export interface PolicyCrawlerCandidateSummary {
    candidate_id: string;
    run_id: string;
    source_id: string;
    url: string;
    title: string | null;
    content_type: string;
    content_hash: string;
    source_name: string | null;
    fetched_at: string | null;
    status: PolicyCrawlerCandidateStatus;
    reviewed_by_user_id: string | null;
    reviewed_at: string | null;
    review_note: string | null;
    knowledge_item_id: string | null;
    created_at: string;
    updated_at: string;
    metadata: Record<string, unknown>;
    rag_kb_id: string | null;
    rag_doc_id: string | null;
    rag_pipeline_status: string | null;
    rag_indexed_chunk_count: number | null;
    rag_search_smoke_passed: boolean | null;
    rag_error_stage: string | null;
    rag_error_detail?: string | null;
    candidate_quality_score?: number | null;
    extraction_quality_score?: number | null;
    topic_relevance_score?: number | null;
    topic_class?: string | null;
    artifact_errors?: string[];
    cleaned_size?: number | null;
    markdown_size?: number | null;
    estimated_chunk_count?: number | null;
    quality_breakdown?: Record<string, unknown>;
    matched_keywords?: string[];
    skip_reason?: string | null;
    duplicate_reason?: string | null;
}

export interface PolicyCrawlerCandidatePage {
    items: PolicyCrawlerCandidateSummary[];
    total: number;
    page: number;
    page_size: number;
}

export interface PolicyCrawlerBatchPublishRequest {
    candidate_ids: string[];
    target_kb_policy?: "auto_crawler_default";
    skip_duplicates?: boolean;
}

export interface PolicyCrawlerBatchPublishItem {
    candidate_id: string;
    status: "published" | "skipped" | "failed";
    rag_doc_id: string | null;
    indexed_chunk_count: number;
    reason: string | null;
}

export interface PolicyCrawlerBatchPublishResponse {
    total: number;
    published: number;
    skipped: number;
    failed: number;
    items: PolicyCrawlerBatchPublishItem[];
}

export interface PolicyCrawlerActiveMaintenanceRequest {
    retry_failed_ingestion?: boolean;
    crawl_enabled_sources?: boolean;
    source_ids?: string[];
    domains?: string[];
    max_sources?: number;
    max_candidates?: number;
    auto_rag_ingest_min_quality?: number;
    auto_rag_ingest_min_extraction?: number;
    auto_rag_ingest_min_markdown_size?: number;
    auto_rag_ingest_skip_duplicate?: boolean;
}

export interface PolicyCrawlerActiveMaintenanceResponse {
    status: "succeeded" | "partial" | "skipped";
    retried_count: number;
    retry_published_count: number;
    retry_skipped_count: number;
    retry_failed_count: number;
    crawled_source_count: number;
    crawled_runs: PolicyCrawlerRunSummary[];
    items: PolicyCrawlerBatchPublishItem[];
    target_kb_id: string | null;
    target_kb_name: string | null;
    warnings: string[];
}

export interface PolicyCrawlerAutoRagKbStatus {
    kb_id: string | null;
    kb_name: string;
    legacy_kb_name: string;
    found: boolean;
    visibility: string | null;
    document_count: number;
    indexed_chunk_count: number;
    latest_run_id: string | null;
    latest_run_status: string | null;
    latest_ingest_status: string | null;
    latest_ingest_at: string | null;
    recent_results: PolicyCrawlerCandidateSummary[];
}

export interface PolicyCrawlerCandidateArtifactsSummary {
    candidate_id: string;
    raw_exists: boolean;
    cleaned_exists: boolean;
    markdown_exists: boolean;
    raw_size: number;
    cleaned_size: number;
    markdown_size: number;
    markdown_preview: string;
    cleaned_text_preview: string;
    raw_excerpt: string;
    estimated_chunk_count: number;
    artifact_errors: string[];
    extraction_quality_score: number | null;
    topic_relevance_score: number | null;
    topic_class: string | null;
    metadata: Record<string, unknown>;
}

export interface PolicyCrawlerStatusSummary {
    scheduler_started: boolean;
    scheduled_enabled: boolean;
    manual_enabled: boolean;
    auto_publish_enabled: boolean;
    running: boolean;
    crawler_backend: string;
    provider_name: string;
    provider_mode: string;
    provider_enabled: boolean;
    provider_available: boolean;
    local_scrapy_available: boolean | null;
    scrapyd_available: boolean | null;
    scrapyd_endpoint_label: string | null;
    provider_error: string | null;
    external_job_id: string | null;
    interval_seconds: number;
    initial_delay_seconds: number;
    source_count: number;
    pending_candidate_count: number;
    recent_run_status: string | null;
    safe_limits: Record<string, unknown>;
}

export interface UpdateAdminPrivateSampleRequest {
    is_enabled: boolean;
    session_attachable: boolean;
}

export type KnowledgeRefreshScope = "public_policy" | "private_sample" | "all";
export type KnowledgeRefreshStatus = "running" | "succeeded" | "failed";

export interface KnowledgeRefreshTask {
    task_id: string;
    scope: KnowledgeRefreshScope;
    status: KnowledgeRefreshStatus;
    requested_by_user_id: string | null;
    summary: string | null;
    created_at: string;
    started_at: string | null;
    finished_at: string | null;
}

export interface TriggerKnowledgeRefreshRequest {
    scope: KnowledgeRefreshScope;
}

export interface AdminSystemStatus {
    app_name: string;
    version: string;
    env: string;
    database_backend: string;
    model_provider_mode: string;
    model_name: string;
    total_users: number;
    total_sessions: number;
    total_reports: number;
    total_feedback_entries: number;
    total_private_samples: number;
    enabled_private_samples: number;
    latest_refresh_status: KnowledgeRefreshStatus | null;
}
