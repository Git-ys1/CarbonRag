import axios from "axios";
import { httpClient } from "./http";
import { consumeSseTextChunk, createSseParserState, flushSseState } from "./sse";
import type {
    AskResponse,
    AskStreamCallbacks,
    AskStreamDeltaEvent,
    AskStreamErrorEvent,
    AskStreamLifecycleStatus,
    AskStreamMetadataEvent,
    AskStreamMessageStartEvent,
    AskStreamStatusEvent,
} from "../types/ask";
import type {
    CreateSessionRequest,
    ReplaceAttachedPrivateSamplesRequest,
    SessionAskRequest,
    SessionAskResponse,
    SessionDetail,
    SessionMemoryState,
    SessionSummary,
    UpdateSessionRequest,
} from "../types/session";

const STREAM_RECOVERY_DELAYS_MS = [800, 1600, 3200, 5000, 8000];
const MAX_STREAM_RECOVERY_ATTEMPTS = 5;

interface StreamAccumulatedState {
    answer: string;
    thinking: string;
    citations: SessionAskResponse["citations"];
    source_summary: SessionAskResponse["source_summary"] | undefined;
    trace_id: string;
    mode: SessionAskResponse["mode"];
    status: SessionAskResponse["status"];
    user_message_id: string | null;
    assistant_message_id: string | null;
    memory_state: SessionMemoryState | undefined;
    request_group_id: string;
    provider_ref: string | null;
    last_event_seq: number;
    terminal: boolean;
}

export async function listSessions() {
    const response = await httpClient.get<SessionSummary[]>("/v1/sessions");
    return response.data;
}

export async function createSession(payload: CreateSessionRequest = {}) {
    const response = await httpClient.post<SessionSummary>("/v1/sessions", payload);
    return response.data;
}

export async function getSession(sessionId: string) {
    const response = await httpClient.get<SessionDetail>(`/v1/sessions/${sessionId}`);
    return response.data;
}

export async function updateSessionTitle(sessionId: string, payload: UpdateSessionRequest) {
    const response = await httpClient.patch<SessionSummary>(`/v1/sessions/${sessionId}`, payload);
    return response.data;
}

export async function replaceAttachedPrivateSamples(
    sessionId: string,
    payload: ReplaceAttachedPrivateSamplesRequest,
) {
    const response = await httpClient.put<SessionDetail>(
        `/v1/sessions/${sessionId}/attached-files/private-samples`,
        payload,
    );
    return response.data;
}

export async function submitSessionAskRequest(
    sessionId: string,
    payload: SessionAskRequest,
    options?: { signal?: AbortSignal },
) {
    try {
        const response = await httpClient.post<SessionAskResponse>(
            `/v1/sessions/${sessionId}/ask`,
            payload,
            { signal: options?.signal },
        );
        return response.data;
    } catch (error) {
        if (axios.isAxiosError<SessionAskResponse>(error) && error.response?.data) {
            throw error.response.data;
        }
        throw error;
    }
}

export async function submitSessionAskStreamRequest(
    sessionId: string,
    payload: SessionAskRequest,
    callbacks: AskStreamCallbacks = {},
    options?: { signal?: AbortSignal },
) {
    const streamUrl = buildApiUrl(`/v1/sessions/${sessionId}/ask/stream`);
    const requestGroupId = payload.request_group_id ?? createRequestGroupId();
    const state: StreamAccumulatedState = {
        answer: "",
        thinking: "",
        citations: [],
        source_summary: undefined,
        trace_id: "",
        mode: "ask",
        status: "ok",
        user_message_id: null,
        assistant_message_id: null,
        memory_state: undefined,
        request_group_id: requestGroupId,
        provider_ref: null,
        last_event_seq: payload.resume_cursor ?? 0,
        terminal: false,
    };

    let attempt = 0;
    callbacks.onStatus?.({
        status: "pending",
        request_group_id: requestGroupId,
        attempt: 1,
        max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
    });

    while (attempt < MAX_STREAM_RECOVERY_ATTEMPTS) {
        attempt += 1;
        const requestPayload: SessionAskRequest = {
            ...payload,
            request_group_id: requestGroupId,
            resume_cursor: state.last_event_seq > 0 ? state.last_event_seq : undefined,
        };

        let fallbackResponse: Response | null = null;
        try {
            fallbackResponse = await fetch(streamUrl, {
                method: "POST",
                headers: {
                    Accept: "text/event-stream",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestPayload),
                credentials: "include",
                signal: options?.signal,
            });
        } catch (error) {
            if (options?.signal?.aborted) {
                throw error;
            }
            if (attempt >= MAX_STREAM_RECOVERY_ATTEMPTS) {
                throw error;
            }
            emitReconnectNotice(callbacks, state, attempt);
            await waitFor(STREAM_RECOVERY_DELAYS_MS[Math.min(attempt - 1, STREAM_RECOVERY_DELAYS_MS.length - 1)]);
            continue;
        }

        if (fallbackResponse.status === 404 && state.last_event_seq === 0 && attempt === 1) {
            const response = await submitSessionAskRequest(sessionId, requestPayload, options);
            emitSyntheticStreamEvents(response, callbacks, requestGroupId);
            return response;
        }

        const contentType = fallbackResponse.headers.get("content-type") ?? "";
        if (!fallbackResponse.ok || !contentType.includes("text/event-stream")) {
            const responseText = await fallbackResponse.text();
            let parsedJson: SessionAskResponse | null = null;
            if (contentType.includes("application/json")) {
                try {
                    parsedJson = JSON.parse(responseText) as SessionAskResponse;
                } catch {
                    parsedJson = null;
                }
            }

            if (parsedJson?.mode === "ask") {
                throw parsedJson;
            }

            if (state.last_event_seq === 0 && attempt === 1) {
                const response = await submitSessionAskRequest(sessionId, requestPayload, options);
                emitSyntheticStreamEvents(response, callbacks, requestGroupId);
                return response;
            }

            if (attempt >= MAX_STREAM_RECOVERY_ATTEMPTS) {
                throw new Error(responseText || "SSE transport failed.");
            }
            emitReconnectNotice(callbacks, state, attempt);
            await waitFor(STREAM_RECOVERY_DELAYS_MS[Math.min(attempt - 1, STREAM_RECOVERY_DELAYS_MS.length - 1)]);
            continue;
        }

        if (!fallbackResponse.body) {
            if (state.last_event_seq === 0 && attempt === 1) {
                const response = await submitSessionAskRequest(sessionId, requestPayload, options);
                emitSyntheticStreamEvents(response, callbacks, requestGroupId);
                return response;
            }
            if (attempt >= MAX_STREAM_RECOVERY_ATTEMPTS) {
                throw new Error("SSE body is unavailable.");
            }
            emitReconnectNotice(callbacks, state, attempt);
            await waitFor(STREAM_RECOVERY_DELAYS_MS[Math.min(attempt - 1, STREAM_RECOVERY_DELAYS_MS.length - 1)]);
            continue;
        }

        if (attempt > 1) {
            callbacks.onStatus?.({
                status: state.answer ? "streaming" : "thinking",
                request_group_id: requestGroupId,
                attempt,
                max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
                recovered: true,
                resume_supported: true,
                provider_ref: state.provider_ref,
            });
        }

        const parserState = createSseParserState();
        const decoder = new TextDecoder();
        const reader = fallbackResponse.body.getReader();

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (value) {
                    const text = decoder.decode(value, { stream: !done });
                    const events = consumeSseTextChunk(text, parserState);
                    for (const event of events) {
                        applyStreamEvent(event, state, callbacks);
                    }
                }
                if (done) {
                    const finalEvent = flushSseState(parserState);
                    if (finalEvent) {
                        applyStreamEvent(finalEvent, state, callbacks);
                    }
                    break;
                }
            }
        } catch (error) {
            if (options?.signal?.aborted) {
                throw error;
            }
            if (attempt >= MAX_STREAM_RECOVERY_ATTEMPTS || state.terminal) {
                throw error;
            }
            emitReconnectNotice(callbacks, state, attempt);
            await waitFor(STREAM_RECOVERY_DELAYS_MS[Math.min(attempt - 1, STREAM_RECOVERY_DELAYS_MS.length - 1)]);
            continue;
        } finally {
            reader.releaseLock();
        }

        if (state.terminal) {
            return buildAskResponseFromStreamState(state);
        }

        if (attempt >= MAX_STREAM_RECOVERY_ATTEMPTS) {
            break;
        }
        emitReconnectNotice(callbacks, state, attempt);
        await waitFor(STREAM_RECOVERY_DELAYS_MS[Math.min(attempt - 1, STREAM_RECOVERY_DELAYS_MS.length - 1)]);
    }

    callbacks.onError?.({
        message: "本次未能连接到模型，请稍后重试或检查模型设置",
        status: "provider_error",
        trace_id: state.trace_id || undefined,
        user_message_id: state.user_message_id,
        assistant_message_id: state.assistant_message_id,
        request_group_id: state.request_group_id,
        attempt,
        max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
    });

    return {
        answer: state.answer.trim() || "本次未能连接到模型，请稍后重试或检查模型设置。",
        mode: "ask",
        status: "provider_error",
        citations: state.citations,
        source_summary:
            state.source_summary ?? {
                knowledge_scope: "public",
                public_policy_count: 0,
                public_policy_demo_count: 0,
                private_sample_count: 0,
                private_upload_count: 0,
                total_citation_count: 0,
            },
        trace_id: state.trace_id,
    };
}

function buildApiUrl(path: string) {
    const baseUrl = httpClient.defaults.baseURL ?? "";
    const normalizedBase = baseUrl.replace(/\/+$/, "");
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return `${normalizedBase}${normalizedPath}`;
}

function emitReconnectNotice(
    callbacks: AskStreamCallbacks,
    state: StreamAccumulatedState,
    attempt: number,
) {
    callbacks.onStatus?.({
        status: "reconnecting",
        request_group_id: state.request_group_id,
        trace_id: state.trace_id || undefined,
        user_message_id: state.user_message_id,
        assistant_message_id: state.assistant_message_id,
        attempt,
        max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
        recovered: false,
        resume_supported: true,
        provider_ref: state.provider_ref,
    });
}

function emitSyntheticStreamEvents(
    response: SessionAskResponse,
    callbacks: AskStreamCallbacks,
    requestGroupId: string,
) {
    callbacks.onStatus?.({
        status: "connecting",
        request_group_id: requestGroupId,
        attempt: 1,
        max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
    });
    callbacks.onMessageStart?.({
        user_message_id: null,
        assistant_message_id: null,
        trace_id: response.trace_id,
        request_group_id: requestGroupId,
    });
    callbacks.onStatus?.({
        status: "thinking",
        trace_id: response.trace_id,
        request_group_id: requestGroupId,
        attempt: 1,
        max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
    });
    callbacks.onThinkingDelta?.({
        delta: "模型正在组织上下文与回答，请稍候。",
        synthetic: true,
        trace_id: response.trace_id,
        request_group_id: requestGroupId,
    });
    if (response.answer) {
        callbacks.onStatus?.({
            status: "streaming",
            trace_id: response.trace_id,
            request_group_id: requestGroupId,
            attempt: 1,
            max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
        });
        callbacks.onAnswerDelta?.({
            delta: response.answer,
            trace_id: response.trace_id,
            request_group_id: requestGroupId,
        });
    }
    callbacks.onMetadata?.({
        ...response,
        memory_state: undefined,
        assistant_message_id: null,
        user_message_id: null,
        request_group_id: requestGroupId,
    });
    callbacks.onStatus?.({
        status: "done",
        trace_id: response.trace_id,
        request_group_id: requestGroupId,
        attempt: 1,
        max_attempts: MAX_STREAM_RECOVERY_ATTEMPTS,
    });
    callbacks.onDone?.({
        ...response,
        memory_state: undefined,
        assistant_message_id: null,
        user_message_id: null,
        request_group_id: requestGroupId,
    });
}

function applyStreamEvent(
    event: { event: string; data: string },
    state: StreamAccumulatedState,
    callbacks: AskStreamCallbacks,
) {
    const payload = parseStreamEventData(event.data);
    const eventSeq = extractEventSeq(payload);
    if (eventSeq > 0) {
        state.last_event_seq = Math.max(state.last_event_seq, eventSeq);
    }

    switch (event.event) {
        case "message_start": {
            const start = payload as AskStreamMessageStartEvent;
            state.trace_id = start.trace_id ?? state.trace_id;
            state.user_message_id = start.user_message_id ?? state.user_message_id;
            state.assistant_message_id = start.assistant_message_id ?? state.assistant_message_id;
            callbacks.onMessageStart?.(start);
            return;
        }
        case "status": {
            const statusEvent = payload as AskStreamStatusEvent;
            if (statusEvent.status) {
                state.status = mapLifecycleStatusToAskStatus(statusEvent.status);
            }
            state.trace_id = statusEvent.trace_id ?? state.trace_id;
            state.user_message_id = statusEvent.user_message_id ?? state.user_message_id;
            state.assistant_message_id = statusEvent.assistant_message_id ?? state.assistant_message_id;
            state.provider_ref = statusEvent.provider_ref ?? state.provider_ref;
            callbacks.onStatus?.(statusEvent);
            return;
        }
        case "thinking_delta": {
            const thinkingEvent = payload as AskStreamDeltaEvent;
            const delta = extractDeltaText(thinkingEvent);
            if (delta && !thinkingEvent.synthetic) {
                state.thinking += delta;
            }
            state.trace_id = thinkingEvent.trace_id ?? state.trace_id;
            callbacks.onThinkingDelta?.(thinkingEvent);
            return;
        }
        case "answer_delta": {
            const answerEvent = payload as AskStreamDeltaEvent;
            const delta = extractDeltaText(answerEvent);
            if (delta) {
                state.answer += delta;
            }
            state.trace_id = answerEvent.trace_id ?? state.trace_id;
            callbacks.onAnswerDelta?.(answerEvent);
            return;
        }
        case "metadata": {
            const metadata = payload as AskStreamMetadataEvent;
            state.trace_id = metadata.trace_id ?? state.trace_id;
            state.citations = metadata.citations ?? state.citations;
            state.source_summary = metadata.source_summary ?? state.source_summary;
            state.status = metadata.status ?? state.status;
            state.provider_ref = metadata.provider_ref ?? state.provider_ref;
            if (typeof metadata.answer === "string" && metadata.answer) {
                state.answer = metadata.answer;
            }
            if (typeof metadata.thinking_content === "string") {
                state.thinking = metadata.thinking_content;
            } else if (metadata.thinking_content === null) {
                state.thinking = "";
            }
            state.memory_state = normalizeMemoryState(metadata.memory_state, state.memory_state);
            callbacks.onMetadata?.(metadata);
            return;
        }
        case "done": {
            const doneEvent = payload as AskStreamMetadataEvent;
            state.trace_id = doneEvent.trace_id ?? state.trace_id;
            state.citations = doneEvent.citations ?? state.citations;
            state.source_summary = doneEvent.source_summary ?? state.source_summary;
            state.status = doneEvent.status ?? state.status;
            state.provider_ref = doneEvent.provider_ref ?? state.provider_ref;
            if (typeof doneEvent.answer === "string" && doneEvent.answer) {
                state.answer = doneEvent.answer;
            }
            if (typeof doneEvent.thinking_content === "string") {
                state.thinking = doneEvent.thinking_content;
            } else if (doneEvent.thinking_content === null) {
                state.thinking = "";
            }
            state.memory_state = normalizeMemoryState(doneEvent.memory_state, state.memory_state);
            state.terminal = true;
            callbacks.onDone?.(doneEvent);
            return;
        }
        case "error": {
            const errorEvent = payload as AskStreamErrorEvent;
            state.status = errorEvent.status ?? "provider_error";
            state.trace_id = errorEvent.trace_id ?? state.trace_id;
            state.terminal = true;
            callbacks.onError?.(errorEvent);
            return;
        }
        default: {
            return;
        }
    }
}

function buildAskResponseFromStreamState(state: StreamAccumulatedState): SessionAskResponse {
    return {
        answer: state.answer.trim(),
        mode: state.mode,
        status: state.status,
        citations: state.citations,
        source_summary:
            state.source_summary ?? {
                knowledge_scope: "public",
                public_policy_count: 0,
                public_policy_demo_count: 0,
                private_sample_count: 0,
                private_upload_count: 0,
                total_citation_count: 0,
            },
        trace_id: state.trace_id,
    };
}

function normalizeMemoryState(
    memoryState: AskStreamMetadataEvent["memory_state"],
    fallback?: SessionMemoryState,
): SessionMemoryState | undefined {
    if (!memoryState || typeof memoryState !== "object") {
        return fallback;
    }

    const candidate = memoryState as Partial<SessionMemoryState>;
    if (
        typeof candidate.context_usage_estimate !== "number" ||
        typeof candidate.context_budget_estimate !== "number" ||
        typeof candidate.summary_present !== "boolean" ||
        typeof candidate.compacted_message_count !== "number" ||
        typeof candidate.summary_estimated_tokens !== "number"
    ) {
        return fallback;
    }

    const compactionStatus = candidate.compaction_status;
    if (compactionStatus !== "idle" && compactionStatus !== "compacted" && compactionStatus !== "failed") {
        return fallback;
    }

    return {
        context_usage_estimate: candidate.context_usage_estimate,
        context_budget_estimate: candidate.context_budget_estimate,
        summary_present: candidate.summary_present,
        summary_updated_at: candidate.summary_updated_at ?? null,
        compacted_message_count: candidate.compacted_message_count,
        compaction_status: compactionStatus,
        summary_estimated_tokens: candidate.summary_estimated_tokens,
    };
}

function parseStreamEventData(rawData: string) {
    const trimmed = rawData.trim();
    if (!trimmed) {
        return {};
    }
    try {
        return JSON.parse(trimmed) as unknown;
    } catch {
        return { delta: trimmed };
    }
}

function extractEventSeq(payload: unknown) {
    if (!payload || typeof payload !== "object") {
        return 0;
    }
    const candidate = payload as { event_seq?: unknown };
    return typeof candidate.event_seq === "number" ? candidate.event_seq : 0;
}

function extractDeltaText(payload: AskStreamDeltaEvent) {
    return payload.delta ?? payload.text ?? payload.content ?? "";
}

function mapLifecycleStatusToAskStatus(status: AskStreamLifecycleStatus): SessionAskResponse["status"] {
    if (status === "error" || status === "failed") {
        return "provider_error";
    }
    return "ok";
}

function createRequestGroupId() {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return `reqgrp-${crypto.randomUUID()}`;
    }
    return `reqgrp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function waitFor(delayMs: number) {
    return new Promise<void>((resolve) => {
        window.setTimeout(resolve, delayMs);
    });
}
