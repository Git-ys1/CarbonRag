import axios from "axios";
import { listKnowledgeRefreshTasks, triggerKnowledgeRefresh } from "./admin";
import { getSession, listSessions, replaceAttachedPrivateSamples } from "./sessions";
import { listPrivateSamples } from "./privateSamples";
import { httpClient } from "./http";
import { listSessionReports } from "./reports";
import type { PrivateSampleCatalogItem } from "../types/privateSample";
import type { UploadedFile, SessionSummary } from "../types/session";
import type {
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    KnowledgeTask,
    MyKnowledgeFeedback,
    MyKnowledgeReport,
    MyKnowledgeWorkspace,
} from "../types/knowledge";

type RemoteKnowledgeItem = Omit<KnowledgeItem, "updated_at"> & {
    updated_at?: string | null;
};

type RemoteKnowledgeTask = Omit<KnowledgeTask, "task_type" | "target_label" | "last_error"> & {
    task_type?: KnowledgeTask["task_type"];
    target_label?: string | null;
    last_error?: string | null;
};

type RemoteKnowledgeTaskResponse = RemoteKnowledgeTask | RemoteKnowledgeTask[];

function isNotFoundError(error: unknown) {
    return axios.isAxiosError(error) && error.response?.status === 404;
}

async function tryRemote<T>(request: () => Promise<T>) {
    try {
        return await request();
    } catch (error) {
        if (isNotFoundError(error)) {
            return null;
        }
        throw error;
    }
}

function normalizeLifecycleStatus(value: string | null | undefined): KnowledgeLifecycleStatus {
    if (value === "running" || value === "succeeded" || value === "failed" || value === "ready") {
        return value;
    }
    if (value === "parsed" || value === "ingested" || value === "indexed") {
        return "succeeded";
    }
    if (value === "parse_failed" || value === "ingest_failed" || value === "index_failed") {
        return "failed";
    }
    if (value === "stale") {
        return "pending";
    }
    return "pending";
}

function mapPrivateSampleToKnowledgeItem(item: PrivateSampleCatalogItem): KnowledgeItem {
    const isEnabled = item.is_enabled ?? true;
    return {
        knowledge_item_id: item.doc_id,
        title: item.title,
        owner_user_id: null,
        library_scope: "shared",
        source_type: "private_sample_repo",
        source_ref: item.doc_id,
        source_label: `${sampleTypeLabelMap[item.sample_type]} · ${businessTopicLabelMap[item.business_topic]}`,
        mime_type: null,
        parse_status: isEnabled ? "ready" : "failed",
        ingest_status: isEnabled ? "ready" : "failed",
        index_status: isEnabled ? "ready" : "failed",
        is_enabled: isEnabled,
        session_attachable: item.session_attachable,
        last_error: isEnabled ? null : "当前知识条目已关闭。",
        updated_at: null,
    };
}

function mapUploadedFileToKnowledgeItem(file: UploadedFile, session: SessionSummary): KnowledgeItem {
    return {
        knowledge_item_id: file.file_id,
        title: file.filename,
        owner_user_id: null,
        library_scope: "personal",
        source_type: "uploaded_file",
        source_ref: file.file_id,
        source_label: `来自会话「${session.title}」`,
        mime_type: file.mime_type,
        parse_status: "pending",
        ingest_status: "pending",
        index_status: "pending",
        is_enabled: true,
        session_attachable: true,
        last_error: null,
        updated_at: file.stored_at,
        session_id: session.session_id,
        session_title: session.title,
        uploaded_at: file.stored_at,
        size: file.size,
    };
}

function mapRemoteKnowledgeItem(item: RemoteKnowledgeItem): KnowledgeItem {
    return {
        ...item,
        updated_at: item.updated_at ?? null,
        source_label: item.source_label || "知识条目",
        parse_status: normalizeLifecycleStatus(item.parse_status),
        ingest_status: normalizeLifecycleStatus(item.ingest_status),
        index_status: normalizeLifecycleStatus(item.index_status),
    };
}

function mapRemoteKnowledgeTask(task: RemoteKnowledgeTask): KnowledgeTask {
    return {
        task_id: task.task_id,
        task_type: task.task_type ?? "rescan",
        scope: task.scope,
        status: task.status,
        summary: task.summary,
        requested_by_user_id: task.requested_by_user_id,
        target_label: task.target_label ?? null,
        last_error: task.last_error ?? null,
        created_at: task.created_at,
        started_at: task.started_at,
        finished_at: task.finished_at,
    };
}

function pickKnowledgeTask(taskOrTasks: RemoteKnowledgeTaskResponse): KnowledgeTask {
    const task = Array.isArray(taskOrTasks) ? taskOrTasks[0] : taskOrTasks;
    return mapRemoteKnowledgeTask(task);
}

async function loadCurrentUserSessionData() {
    const sessions = await listSessions().catch(() => [] as SessionSummary[]);
    const details = await Promise.all(sessions.map((session) => getSession(session.session_id).catch(() => null)));
    const sessionDetails = details.filter((item): item is NonNullable<typeof item> => item !== null);
    return { sessions, sessionDetails };
}

export async function listAttachableKnowledgeItems(): Promise<KnowledgeItem[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<RemoteKnowledgeItem[]>("/v1/knowledge-items");
        return response.data.map(mapRemoteKnowledgeItem);
    });
    if (remote) {
        return remote;
    }

    const catalog = await listPrivateSamples().catch(() => [] as PrivateSampleCatalogItem[]);
    return catalog.map(mapPrivateSampleToKnowledgeItem);
}

export async function listAdminKnowledgeItems(): Promise<KnowledgeItem[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<RemoteKnowledgeItem[]>("/v1/admin/knowledge-items");
        return response.data.map(mapRemoteKnowledgeItem);
    });
    if (remote) {
        return remote;
    }

    return listAttachableKnowledgeItems();
}

export async function listKnowledgeTasks(): Promise<KnowledgeTask[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<RemoteKnowledgeTask[]>("/v1/knowledge-tasks");
        return response.data.map(mapRemoteKnowledgeTask);
    });
    if (remote) {
        return remote;
    }

    const refreshTasks = await listKnowledgeRefreshTasks().catch(() => []);
    return refreshTasks.map((item) => ({
        task_id: item.task_id,
        task_type: "rescan" as const,
        scope: item.scope,
        status: item.status,
        summary: item.summary,
        requested_by_user_id: item.requested_by_user_id,
        target_label: null,
        last_error: null,
        created_at: item.created_at,
        started_at: item.started_at,
        finished_at: item.finished_at,
    }));
}

export async function triggerKnowledgeScan(): Promise<KnowledgeTask> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.post<RemoteKnowledgeTaskResponse>("/v1/admin/knowledge-tasks/scan", {});
        return pickKnowledgeTask(response.data);
    });
    if (remote) {
        return remote;
    }

    const task = await triggerKnowledgeRefresh({ scope: "all" });
    return mapRemoteKnowledgeTask({
        ...task,
        task_type: "rescan",
        target_label: null,
        last_error: null,
    });
}

export async function triggerKnowledgeRebuild(): Promise<KnowledgeTask> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.post<RemoteKnowledgeTaskResponse>("/v1/admin/knowledge-tasks/rebuild", {});
        return pickKnowledgeTask(response.data);
    });
    if (remote) {
        return remote;
    }

    const task = await triggerKnowledgeRefresh({ scope: "private_sample" });
    return mapRemoteKnowledgeTask({
        ...task,
        task_type: "rebuild",
        target_label: null,
        last_error: null,
    });
}

export async function retryKnowledgeTask(taskId: string): Promise<KnowledgeTask> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.post<RemoteKnowledgeTask>(`/v1/admin/knowledge-tasks/${taskId}/retry`, {});
        return mapRemoteKnowledgeTask(response.data);
    });
    if (remote) {
        return remote;
    }

    const task = await triggerKnowledgeRefresh({ scope: "all" });
    return mapRemoteKnowledgeTask({
        ...task,
        task_type: "retry",
        target_label: taskId,
        last_error: null,
    });
}

export async function updateAdminKnowledgeItem(
    knowledgeItemId: string,
    payload: Pick<KnowledgeItem, "is_enabled" | "session_attachable">,
): Promise<KnowledgeItem> {
    const response = await httpClient.patch<RemoteKnowledgeItem>(`/v1/admin/knowledge-items/${knowledgeItemId}`, payload);
    return mapRemoteKnowledgeItem(response.data);
}

export async function listAdminKnowledgeTasks(): Promise<KnowledgeTask[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<RemoteKnowledgeTask[]>("/v1/admin/knowledge-tasks");
        return response.data.map(mapRemoteKnowledgeTask);
    });
    if (remote) {
        return remote;
    }

    return listKnowledgeTasks();
}

export async function listMyUploads(): Promise<KnowledgeItem[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<RemoteKnowledgeItem[]>("/v1/me/uploads");
        return response.data.map(mapRemoteKnowledgeItem);
    });
    if (remote) {
        return remote;
    }

    const { sessions, sessionDetails } = await loadCurrentUserSessionData();
    const sessionLookup = new Map(sessions.map((item) => [item.session_id, item]));
    return sessionDetails.flatMap((sessionDetail) =>
        sessionDetail.files.map((file) =>
            mapUploadedFileToKnowledgeItem(file, sessionLookup.get(sessionDetail.session_id) ?? sessionDetail),
        ),
    );
}

export async function listMyReports(): Promise<MyKnowledgeReport[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<MyKnowledgeReport[]>("/v1/me/reports");
        return response.data;
    });
    if (remote) {
        return remote;
    }

    const { sessions } = await loadCurrentUserSessionData();
    const reportLists = await Promise.all(sessions.map((session) => listSessionReports(session.session_id).catch(() => [])));
    return sessions.flatMap((session, index) =>
        reportLists[index].map((report) => ({
            ...report,
            session_id: session.session_id,
            session_title: session.title,
        })),
    );
}

export async function listMyFeedback(): Promise<MyKnowledgeFeedback[]> {
    const remote = await tryRemote(async () => {
        const response = await httpClient.get<MyKnowledgeFeedback[]>("/v1/me/feedback");
        return response.data;
    });
    if (remote) {
        return remote;
    }

    return [];
}

export async function loadMyKnowledgeWorkspace(): Promise<MyKnowledgeWorkspace> {
    const [uploads, knowledgeItems, reports, feedback] = await Promise.all([
        listMyUploads(),
        listAttachableKnowledgeItems(),
        listMyReports(),
        listMyFeedback(),
    ]);

    return {
        uploads,
        knowledgeItems,
        reports,
        feedback,
        taskSummary: await listKnowledgeTasks().catch(() => []),
    };
}

export async function replaceAttachedKnowledgeItems(sessionId: string, knowledgeItemIds: string[]) {
    try {
        const response = await httpClient.put(`/v1/sessions/${sessionId}/knowledge-items`, {
            knowledge_item_ids: knowledgeItemIds,
        });
        return response.data;
    } catch (error) {
        if (isNotFoundError(error)) {
            return replaceAttachedPrivateSamples(sessionId, { doc_ids: knowledgeItemIds });
        }
        throw error;
    }
}

const sampleTypeLabelMap: Record<PrivateSampleCatalogItem["sample_type"], string> = {
    doc: "文档",
    table: "表格",
};

const businessTopicLabelMap: Record<PrivateSampleCatalogItem["business_topic"], string> = {
    energy: "能耗",
    production: "生产",
    logistics: "物流",
    project_background: "项目背景",
};
