import type { UserRole } from "./auth";

export interface AdminUserSummary {
    user_id: string;
    username: string;
    role: UserRole;
    is_active: boolean;
    password_must_change: boolean;
    created_at: string;
    last_login_at: string | null;
    session_count: number;
    report_count: number;
    feedback_count: number;
}

export interface UpdateAdminUserRequest {
    role: UserRole;
    is_active: boolean;
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
}

export interface PolicyCrawlerStatusSummary {
    scheduler_started: boolean;
    scheduled_enabled: boolean;
    manual_enabled: boolean;
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
