import { httpClient } from "./http";
import type { KnowledgeBase, KnowledgeBaseOverview, RagChunk, RagDocument, RagPipelineBatchResult, RagPipelineMode, RagPipelineResult } from "../types/kb";

export async function listKnowledgeBases() {
    const response = await httpClient.get<KnowledgeBase[]>("/v1/kb");
    return response.data;
}

export async function createKnowledgeBase(payload: {
    name: string;
    description?: string;
    embedding_model?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    parent_chunk_size?: number | null;
    rerank_top_n?: number;
    retrieval_top_k?: number;
}) {
    const response = await httpClient.post<KnowledgeBase>("/v1/kb", payload);
    return response.data;
}

export async function createKbDocument(kbId: string, payload: { knowledge_item_id?: string; title?: string; text?: string }) {
    const response = await httpClient.post<RagDocument>(`/v1/kb/${encodeURIComponent(kbId)}/documents`, payload);
    return response.data;
}

export async function listKbDocuments(kbId: string) {
    const response = await httpClient.get<RagDocument[]>(`/v1/kb/${encodeURIComponent(kbId)}/documents`);
    return response.data;
}

export async function getKnowledgeBaseOverview(kbId: string) {
    const response = await httpClient.get<KnowledgeBaseOverview>(`/v1/kb/${encodeURIComponent(kbId)}/overview`);
    return response.data;
}

export async function uploadKbDocument(kbId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    const response = await httpClient.post<RagDocument>(`/v1/kb/${encodeURIComponent(kbId)}/documents/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
}

export async function getKbDocumentStatus(kbId: string, docId: string) {
    const response = await httpClient.get<RagDocument>(`/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/status`);
    return response.data;
}

export async function parseKbDocument(kbId: string, docId: string) {
    const response = await httpClient.post<RagDocument>(`/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/parse`);
    return response.data;
}

export async function chunkKbDocument(kbId: string, docId: string) {
    const response = await httpClient.post<RagDocument>(`/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/chunk`);
    return response.data;
}

export async function indexKbDocument(kbId: string, docId: string) {
    const response = await httpClient.post<RagDocument>(`/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/index`);
    return response.data;
}

export async function runKbDocumentPipeline(kbId: string, docId: string, pipelineMode: RagPipelineMode = "quick") {
    const response = await httpClient.post<RagPipelineResult>(
        `/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/run-pipeline`,
        { pipeline_mode: pipelineMode },
    );
    return response.data;
}

export async function runKbDocumentPipelineBatch(kbId: string, docIds?: string[], pipelineMode: RagPipelineMode = "quick") {
    const response = await httpClient.post<RagPipelineBatchResult>(
        `/v1/kb/${encodeURIComponent(kbId)}/documents/run-pipeline-batch`,
        { ...(docIds ? { doc_ids: docIds } : {}), pipeline_mode: pipelineMode },
    );
    return response.data;
}

export async function deleteKbDocument(kbId: string, docId: string) {
    const response = await httpClient.delete<{ status: string; kb_id: string; doc_id: string }>(
        `/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}`,
    );
    return response.data;
}

export async function rebuildKbDocumentIndex(kbId: string, docId: string) {
    const response = await httpClient.post<RagDocument>(
        `/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/rebuild-index`,
    );
    return response.data;
}

export async function listKbDocumentChunks(kbId: string, docId: string) {
    const response = await httpClient.get<RagChunk[]>(`/v1/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(docId)}/chunks`);
    return response.data;
}

