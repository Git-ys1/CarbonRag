import type { ReportSummary } from "./report";

export type KnowledgeLibraryScope = "personal" | "shared";
export type KnowledgeSourceType = "uploaded_file" | "private_sample_repo" | "knowledge_item" | "public_policy_web";
export type KnowledgeLifecycleStatus = "pending" | "running" | "succeeded" | "failed" | "ready";
export type KnowledgeTaskStatus = "queued" | "running" | "succeeded" | "failed";
export type KnowledgeTaskAction = "upload_ingest" | "rebuild" | "rescan" | "retry" | "crawl_ingest" | "crawl_refresh";

export interface KnowledgeItem {
    knowledge_item_id: string;
    title: string;
    owner_user_id: string | null;
    visibility?: "public" | "tenant" | "private" | "demo" | null;
    library_scope: KnowledgeLibraryScope;
    source_type: KnowledgeSourceType;
    source_ref: string;
    source_label: string;
    mime_type: string | null;
    parse_status: KnowledgeLifecycleStatus;
    ingest_status: KnowledgeLifecycleStatus;
    index_status: KnowledgeLifecycleStatus;
    is_enabled: boolean;
    session_attachable: boolean;
    last_error: string | null;
    updated_at: string | null;
    session_id?: string | null;
    session_title?: string | null;
    uploaded_at?: string | null;
    size?: number | null;
}

export interface KnowledgeTask {
    task_id: string;
    task_type: KnowledgeTaskAction;
    scope: string;
    status: KnowledgeTaskStatus;
    summary: string | null;
    requested_by_user_id: string | null;
    target_label: string | null;
    last_error: string | null;
    created_at: string;
    started_at: string | null;
    finished_at: string | null;
}

export interface MyKnowledgeFeedback {
    feedback_id: string;
    target_type: string;
    rating: "up" | "down";
    trace_id: string;
    session_id: string | null;
    comment: string | null;
    created_at: string;
}

export interface MyKnowledgeReport extends ReportSummary {
    session_id: string;
    session_title: string;
}

export interface MyKnowledgeWorkspace {
    uploads: KnowledgeItem[];
    knowledgeItems: KnowledgeItem[];
    reports: MyKnowledgeReport[];
    feedback: MyKnowledgeFeedback[];
    taskSummary: KnowledgeTask[];
}
