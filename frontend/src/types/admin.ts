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
