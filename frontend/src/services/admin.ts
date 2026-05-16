import { httpClient } from "./http";
import { buildActionAckHeaders } from "./managementApi";
import type {
    AdminFeedbackOverview,
    AdminPrivateSampleItem,
    AdminSystemStatus,
    AdminUserSummary,
    DeleteAdminUsersRequest,
    DeleteAdminUsersResponse,
    KnowledgeRefreshTask,
    PolicyCrawlerCandidateStatus,
    PolicyCrawlerCandidateArtifactsSummary,
    PolicyCrawlerCandidateSummary,
    PolicyCrawlerDryRunSummary,
    PolicyCrawlerRecommendedImportSummary,
    PolicyCrawlerRunSummary,
    PolicyCrawlerSourceSummary,
    PolicyCrawlerSourceUpsertRequest,
    PolicyCrawlerStatusSummary,
    PolicyShowcaseChunkSummary,
    PolicyShowcaseRetrievalPreview,
    PolicyShowcaseSourceSummary,
    PolicyShowcaseStatus,
    TriggerKnowledgeRefreshRequest,
    UpdateAdminPrivateSampleRequest,
    UpdateAdminUserRequest,
    ResetPasswordResponse,
} from "../types/admin";

const crawlerRequestConfig = { timeout: 120000 };

export async function listAdminUsers() {
    const response = await httpClient.get<AdminUserSummary[]>("/v1/admin/users");
    return response.data;
}

export async function updateAdminUser(userId: string, payload: UpdateAdminUserRequest) {
    const headers = await buildActionAckHeaders("ADMIN_USER_UPDATE", "user", userId, payload);
    const response = await httpClient.patch<AdminUserSummary>(`/v1/admin/users/${userId}`, payload, { headers });
    return response.data;
}

export async function resetAdminUserPassword(userId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders("ADMIN_USER_RESET_PASSWORD", "user", userId, payload);
    const response = await httpClient.post<ResetPasswordResponse>(`/v1/admin/users/${userId}/reset-password`, payload, { headers });
    return response.data;
}

export async function deleteAdminUsers(payload: DeleteAdminUsersRequest) {
    const headers = await buildActionAckHeaders("ADMIN_USER_DELETE", "user_batch", "batch", payload);
    const response = await httpClient.delete<DeleteAdminUsersResponse>("/v1/admin/users", { data: payload, headers });
    return response.data;
}

export async function getAdminFeedbackOverview() {
    const response = await httpClient.get<AdminFeedbackOverview>("/v1/admin/feedback/overview");
    return response.data;
}

export async function listAdminPrivateSamples() {
    const response = await httpClient.get<AdminPrivateSampleItem[]>("/v1/admin/private-samples");
    return response.data;
}

export async function listPolicyShowcaseSources() {
    const response = await httpClient.get<PolicyShowcaseSourceSummary[]>("/v1/admin/policy-sources");
    return response.data;
}

export async function runPolicyShowcaseSource(sourceId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders("ADMIN_POLICY_SOURCE_RUN", "policy_source", sourceId, payload);
    const response = await httpClient.post<PolicyShowcaseStatus>(`/v1/admin/policy-sources/${sourceId}/run`, payload, { headers });
    return response.data;
}

export async function getPolicyShowcaseStatus(sourceId: string) {
    const response = await httpClient.get<PolicyShowcaseStatus>(`/v1/admin/policy-sources/${sourceId}/status`);
    return response.data;
}

export async function listPolicyShowcaseChunks(sourceId: string) {
    const response = await httpClient.get<PolicyShowcaseChunkSummary[]>(`/v1/admin/policy-sources/${sourceId}/chunks`);
    return response.data;
}

export async function getPolicyShowcaseRetrievalPreview(sourceId: string, query?: string, topK = 5) {
    const response = await httpClient.get<PolicyShowcaseRetrievalPreview>(
        `/v1/admin/policy-sources/${sourceId}/retrieval-preview`,
        {
            params: {
                query,
                top_k: topK,
            },
        },
    );
    return response.data;
}

export async function getPolicyCrawlerStatus() {
    const response = await httpClient.get<PolicyCrawlerStatusSummary>("/v1/admin/policy-crawler/status");
    return response.data;
}

export async function listPolicyCrawlerSources() {
    const response = await httpClient.get<PolicyCrawlerSourceSummary[]>("/v1/admin/policy-crawler/sources");
    return response.data;
}

export async function createPolicyCrawlerSource(payload: PolicyCrawlerSourceUpsertRequest) {
    const headers = await buildActionAckHeaders("POLICY_CRAWLER_SOURCE_CREATE", "policy_crawler_source", "new", payload);
    const response = await httpClient.post<PolicyCrawlerSourceSummary>("/v1/admin/policy-crawler/sources", payload, { headers });
    return response.data;
}

export async function updatePolicyCrawlerSource(sourceId: string, payload: PolicyCrawlerSourceUpsertRequest) {
    const headers = await buildActionAckHeaders("POLICY_CRAWLER_SOURCE_UPDATE", "policy_crawler_source", sourceId, payload);
    const response = await httpClient.patch<PolicyCrawlerSourceSummary>(
        `/v1/admin/policy-crawler/sources/${sourceId}`,
        payload,
        { headers },
    );
    return response.data;
}

export async function deletePolicyCrawlerSource(sourceId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders("POLICY_CRAWLER_SOURCE_DELETE", "policy_crawler_source", sourceId, payload);
    const response = await httpClient.delete<{ status: string; source_id: string }>(
        `/v1/admin/policy-crawler/sources/${sourceId}`,
        { data: payload, headers },
    );
    return response.data;
}

export async function importRecommendedPolicyCrawlerSources() {
    const payload = {};
    const headers = await buildActionAckHeaders("POLICY_CRAWLER_RECOMMENDED_IMPORT", "policy_crawler_source", "recommended", payload);
    const response = await httpClient.post<PolicyCrawlerRecommendedImportSummary>(
        "/v1/admin/policy-crawler/sources/recommended/import",
        payload,
        { headers },
    );
    return response.data;
}

export async function dryRunPolicyCrawlerSource(sourceId: string) {
    const response = await httpClient.post<PolicyCrawlerDryRunSummary>(
        `/v1/admin/policy-crawler/sources/${sourceId}/dry-run`,
        {},
        crawlerRequestConfig,
    );
    return response.data;
}

export async function runPolicyCrawlerSource(sourceId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders("POLICY_CRAWLER_SOURCE_RUN", "policy_crawler_source", sourceId, payload);
    const response = await httpClient.post<PolicyCrawlerRunSummary>(
        `/v1/admin/policy-crawler/sources/${sourceId}/run`,
        payload,
        { ...crawlerRequestConfig, headers },
    );
    return response.data;
}

export async function listPolicyCrawlerRuns(sourceId?: string, limit = 20) {
    const response = await httpClient.get<PolicyCrawlerRunSummary[]>("/v1/admin/policy-crawler/runs", {
        params: {
            source_id: sourceId,
            limit,
        },
    });
    return response.data;
}

export async function listPolicyCrawlerCandidates(
    status?: PolicyCrawlerCandidateStatus,
    sourceId?: string,
    limit = 50,
) {
    const response = await httpClient.get<PolicyCrawlerCandidateSummary[]>("/v1/admin/policy-crawler/candidates", {
        params: {
            status,
            source_id: sourceId,
            limit,
        },
    });
    return response.data;
}

export async function publishPolicyCrawlerCandidate(candidateId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders(
        "POLICY_CRAWLER_CANDIDATE_PUBLISH_LEGACY",
        "policy_crawler_candidate",
        candidateId,
        payload,
    );
    const response = await httpClient.post<PolicyCrawlerCandidateSummary>(
        `/v1/admin/policy-crawler/candidates/${candidateId}/publish`,
        payload,
        { headers },
    );
    return response.data;
}

export async function publishPolicyCrawlerCandidateToRag(candidateId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders(
        "POLICY_CRAWLER_CANDIDATE_PUBLISH_TO_RAG",
        "policy_crawler_candidate",
        candidateId,
        payload,
    );
    const response = await httpClient.post<PolicyCrawlerCandidateSummary>(
        `/v1/admin/policy-crawler/candidates/${candidateId}/publish-to-rag`,
        payload,
        { ...crawlerRequestConfig, headers },
    );
    return response.data;
}

export async function getPolicyCrawlerCandidateArtifacts(candidateId: string) {
    const response = await httpClient.get<PolicyCrawlerCandidateArtifactsSummary>(
        `/v1/admin/policy-crawler/candidates/${candidateId}/artifacts`,
        crawlerRequestConfig,
    );
    return response.data;
}

export async function rejectPolicyCrawlerCandidate(candidateId: string) {
    const payload = {};
    const headers = await buildActionAckHeaders(
        "POLICY_CRAWLER_CANDIDATE_REJECT",
        "policy_crawler_candidate",
        candidateId,
        payload,
    );
    const response = await httpClient.post<PolicyCrawlerCandidateSummary>(
        `/v1/admin/policy-crawler/candidates/${candidateId}/reject`,
        payload,
        { headers },
    );
    return response.data;
}

export async function updateAdminPrivateSample(docId: string, payload: UpdateAdminPrivateSampleRequest) {
    const headers = await buildActionAckHeaders("ADMIN_PRIVATE_SAMPLE_UPDATE", "private_sample", docId, payload);
    const response = await httpClient.patch<AdminPrivateSampleItem>(`/v1/admin/private-samples/${docId}`, payload, { headers });
    return response.data;
}

export async function listKnowledgeRefreshTasks() {
    const response = await httpClient.get<KnowledgeRefreshTask[]>("/v1/admin/knowledge-refresh-tasks");
    return response.data;
}

export async function triggerKnowledgeRefresh(payload: TriggerKnowledgeRefreshRequest) {
    const headers = await buildActionAckHeaders("ADMIN_KNOWLEDGE_REFRESH_TRIGGER", "knowledge_refresh", "trigger", payload);
    const response = await httpClient.post<KnowledgeRefreshTask>("/v1/admin/knowledge-refresh-tasks", payload, { headers });
    return response.data;
}

export async function getAdminSystemStatus() {
    const response = await httpClient.get<AdminSystemStatus>("/v1/admin/system/status");
    return response.data;
}
