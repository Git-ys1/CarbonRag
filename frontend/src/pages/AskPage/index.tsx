import {
    BranchesOutlined,
    CopyOutlined,
    DownloadOutlined,
    EditOutlined,
    FileTextOutlined,
    LinkOutlined,
    MessageOutlined,
    MoreOutlined,
    PaperClipOutlined,
    ReloadOutlined,
    SettingOutlined,
    ShareAltOutlined,
    SoundOutlined,
    TagsOutlined,
} from "@ant-design/icons";
import {
    Alert,
    Button,
    Card,
    Checkbox,
    Collapse,
    Drawer,
    Empty,
    Input,
    List,
    Popover,
    Segmented,
    Select,
    Space,
    Spin,
    Tag,
    Tooltip,
    Typography,
    message as antdMessage,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useSettings } from "../../app/SettingsContext";
import { FeedbackButtonGroup } from "../../components/FeedbackButtonGroup";
import { FilePreviewDrawer } from "../../components/FilePreviewDrawer";
import { SystemInfoPanel } from "../../components/SystemInfoPanel";
import { useFeedback } from "../../hooks/useFeedback";
import { useWorkbenchShellContext } from "../../layouts/WorkbenchShellContext";
import { uploadSessionFile } from "../../services/files";
import { listKnowledgeBases } from "../../services/kb";
import { listAttachableKnowledgeItems, replaceAttachedKnowledgeItems } from "../../services/knowledge";
import { downloadReportFile } from "../../services/reports";
import {
    createSession as createSessionRequest,
    getSession,
    submitSessionAskStreamRequest,
} from "../../services/sessions";
import type {
    AskCitation,
    AskResponse,
    AskSourceSummary,
    AskStatus,
    AskStreamDeltaEvent,
    AskStreamErrorEvent,
    AskStreamMetadataEvent,
    AskStreamMessageStartEvent,
    AskStreamStatusEvent,
    GeneratedReportFile,
    GeneratedReportSummary,
    KnowledgeScope,
} from "../../types/ask";
import type { KnowledgeItem } from "../../types/knowledge";
import type { KnowledgeBase, RagRetrievalMode } from "../../types/kb";
import type { FilePreviewTarget } from "../../types/filePreview";
import type { SessionAttachment, SessionDetail, SessionMessage, SessionSummary } from "../../types/session";
import { normalizeAssistantMarkdown } from "./markdownNormalize";

type AssistantLifecycleState = "pending" | "connecting" | "thinking" | "reconnecting" | "streaming" | "done" | "error" | "failed";

const NEW_CHAT_PROMPTS = [
    "今天想问些什么？",
    "想了解些什么？",
    "今天你在想什么？",
    "随时开始",
    "有什么需要我帮你梳理？",
    "从一个问题开始吧",
    "今天要研究哪件事？",
    "准备好聊聊双碳了吗？",
];

interface ChatMessageView extends SessionMessage {
    client_state?: AssistantLifecycleState;
    thinking_content?: string | null;
    status_note?: string | null;
    client_attachments?: SessionAttachment[];
    generated_reports?: GeneratedReportSummary[];
}

interface ChatDraft {
    userMessage: ChatMessageView;
    assistantMessage: ChatMessageView;
}

interface StreamContextSource {
    recent_message_count: number;
    summary_present: boolean;
    citation_count: number;
}

interface LoadSessionDetailOptions {
    silent?: boolean;
    preserveDraftSelections?: boolean;
}

export function AskPage() {
    const { user } = useAuth();
    const { settings, getActiveProviderOverride } = useSettings();
    const feedback = useFeedback();
    const { activeSessionId, refreshSessions, syncSessionSummary, updateSessionSummary } = useWorkbenchShellContext();
    const [searchParams] = useSearchParams();
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const streamAbortRef = useRef<AbortController | null>(null);
    const messageStreamRef = useRef<HTMLDivElement | null>(null);
    const streamDraftRef = useRef<ChatDraft | null>(null);
    const streamingSessionIdRef = useRef<string | null>(null);
    const streamMemoryStateRef = useRef<SessionDetail["memory_state"] | null>(null);
    const streamContextSourceRef = useRef<StreamContextSource | null>(null);
    const shouldAutoFollowMessageStreamRef = useRef(true);
    const knowledgeScopeNoticeRef = useRef<string | null>(null);
    const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
    const [selectedCitationMessageId, setSelectedCitationMessageId] = useState<string | null>(null);
    const [filePreviewTarget, setFilePreviewTarget] = useState<FilePreviewTarget | null>(null);
    const [streamDraft, setStreamDraft] = useState<ChatDraft | null>(null);
    const [streamMemoryState, setStreamMemoryState] = useState<SessionDetail["memory_state"] | null>(null);
    const [streamContextSource, setStreamContextSource] = useState<StreamContextSource | null>(null);
    const [selectedThinkingMessageId, setSelectedThinkingMessageId] = useState<string | null>(null);
    const [question, setQuestion] = useState("");
    const [knowledgeScope, setKnowledgeScope] = useState<KnowledgeScope>("public");
    const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
    const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
    const [ragMode, setRagMode] = useState<RagRetrievalMode>("hybrid_rerank");
    const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
    const [privateSampleDrawerOpen, setPrivateSampleDrawerOpen] = useState(false);
    const [draftAttachedDocIds, setDraftAttachedDocIds] = useState<string[]>([]);
    const [draftAttachedFileIds, setDraftAttachedFileIds] = useState<string[]>([]);
    const [dismissedUploadedFileIds, setDismissedUploadedFileIds] = useState<string[]>([]);
    const [savingAttachedSamples, setSavingAttachedSamples] = useState(false);
    const [loadingPrivateSamples, setLoadingPrivateSamples] = useState(true);
    const [loadingSessionDetail, setLoadingSessionDetail] = useState(false);
    const [sidePanelOpen, setSidePanelOpen] = useState(false);
    const [sending, setSending] = useState(false);
    const [regeneratingMessageId, setRegeneratingMessageId] = useState<string | null>(null);
    const [uploading, setUploading] = useState(false);
    const [draggingFiles, setDraggingFiles] = useState(false);
    const [transportError, setTransportError] = useState<string | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const focusModeEnabled = searchParams.get("focus") !== "0";
    const isAdmin = user?.role === "admin" || user?.role === "super_admin";
    const sendShortcut = settings?.chat.send_shortcut ?? "enter";
    const reconnectNoticeMode = settings?.chat.reconnect_notice_mode ?? "message_only";
    const shouldShowContextDebug = settings?.chat.show_context_debug_by_default ?? false;

    const uploadedAttachments = dedupeUploadedAttachments(activeSession?.attached_files.filter((item) => item.source_type === "uploaded_file") ?? []);
    const dismissedUploadedFileIdSet = useMemo(() => new Set(dismissedUploadedFileIds), [dismissedUploadedFileIds]);
    const visibleUploadedAttachments = uploadedAttachments.filter((item) => !dismissedUploadedFileIdSet.has(item.file_id));
    const selectedUploadedAttachments = visibleUploadedAttachments.filter((item) => draftAttachedFileIds.includes(item.file_id));
    const selectedReadyUploadedAttachments = selectedUploadedAttachments.filter(isAttachmentReadyForAsk);
    const visibleMessages = useMemo<ChatMessageView[]>(() => {
        const baseMessages = attachCitedFilesToUserMessages((activeSession?.messages ?? []) as ChatMessageView[], uploadedAttachments);
        if (!streamDraft) {
            return baseMessages;
        }
        return [...baseMessages, streamDraft.userMessage, streamDraft.assistantMessage];
    }, [activeSession?.messages, streamDraft, uploadedAttachments]);

    const selectedCitationMessage = visibleMessages.find((message) => message.message_id === selectedCitationMessageId) ?? null;
    const selectedThinkingMessage = visibleMessages.find((message) => message.message_id === selectedThinkingMessageId) ?? null;

    useEffect(() => {
        if (!transportError) {
            return;
        }
        feedback.error({
            title: "对话工作台提示",
            description: transportError,
            source: "AskPage",
            key: `ask-transport:${transportError}`,
        });
    }, [feedback, transportError]);

    useEffect(() => {
        if (!uploadError) {
            return;
        }
        feedback.error({
            title: "附件上传失败",
            description: uploadError,
            source: "AskPage",
            key: `ask-upload:${uploadError}`,
        });
    }, [feedback, uploadError]);

    const privateAttachments = activeSession?.attached_files.filter((item) => item.source_type !== "uploaded_file") ?? [];

    useEffect(() => {
        if (knowledgeScope === "public" || privateAttachments.length > 0) {
            knowledgeScopeNoticeRef.current = null;
            return;
        }
        const key = `${knowledgeScope}:empty`;
        if (knowledgeScopeNoticeRef.current === key) {
            return;
        }
        knowledgeScopeNoticeRef.current = key;
        feedback.info({
            title: "当前范围已切到知识条目 / 混合",
            description: "当前会话还没有挂接任何知识条目，该范围下可能检索为空。",
            source: "AskPage",
            history: true,
            key: `ask-scope:${key}`,
        });
    }, [feedback, knowledgeScope, privateAttachments.length]);
    const citationGroups = groupCitationsBySource(selectedCitationMessage?.citations ?? []);
    const selectedRetrievalTrace = selectedCitationMessage?.retrieval_trace ?? null;
    const pendingUploadSignature = getPendingUploadSignature(uploadedAttachments);
    const effectiveSessionId = activeSessionId ?? activeSession?.session_id ?? null;
    const currentSourceSummary = buildPanelSourceSummary(selectedCitationMessage?.citations ?? [], activeSession?.source_summary);
    const effectiveMemoryState = streamMemoryState ?? activeSession?.memory_state ?? null;
    const currentStreamState = streamDraft?.assistantMessage.client_state ?? null;
    const currentStreamTag = currentStreamState ? lifecycleTagMap[currentStreamState] : null;
    const contextUsagePercent = getContextUsagePercent(effectiveMemoryState);
    const currentContextSourceText = buildContextSourceText(
        effectiveMemoryState,
        currentSourceSummary,
        visibleMessages.length,
        streamContextSource,
    );
    const isNewDraftChat = visibleMessages.length === 0 && !loadingSessionDetail;
    const newChatPrompt = useMemo(
        () => NEW_CHAT_PROMPTS[Math.floor(Math.random() * NEW_CHAT_PROMPTS.length)],
        [],
    );

    useEffect(() => {
        void loadKnowledgeCatalog();
        void loadKnowledgeBases();
    }, []);

    useEffect(() => {
        const kbIdFromUrl = searchParams.get("kb_id");
        const ragModeFromUrl = searchParams.get("rag_mode");
        const questionFromUrl = searchParams.get("question");
        if (kbIdFromUrl) {
            setSelectedKbId(kbIdFromUrl);
            setKnowledgeScope("mixed");
        }
        if (isRagRetrievalMode(ragModeFromUrl)) {
            setRagMode(ragModeFromUrl);
        }
        if (questionFromUrl) {
            setQuestion((current) => current || questionFromUrl);
        }
    }, [searchParams]);

    useEffect(() => {
        if (!activeSessionId) {
            setActiveSession(null);
            return;
        }
        if (streamingSessionIdRef.current === activeSessionId) {
            // A newly created chat can be selected in the shell while its SSE answer is still streaming.
            // Keep the local draft alive; the final refresh after completion will sync persisted messages.
            shouldAutoFollowMessageStreamRef.current = true;
            return;
        }
        streamAbortRef.current?.abort();
        streamAbortRef.current = null;
        replaceStreamDraft(null);
        replaceStreamMemoryState(null);
        replaceStreamContextSource(null);
        setDismissedUploadedFileIds([]);
        shouldAutoFollowMessageStreamRef.current = true;
        void loadSessionDetail(activeSessionId);
    }, [activeSessionId]);

    useEffect(() => {
        return () => {
            streamAbortRef.current?.abort();
        };
    }, []);

    useEffect(() => {
        if (!settings) {
            return;
        }
        setSidePanelOpen(settings.chat.show_evidence_panel_by_default);
    }, [settings?.chat.show_evidence_panel_by_default]);

    useEffect(() => {
        if (!effectiveSessionId || !pendingUploadSignature) {
            return;
        }
        const timer = window.setInterval(() => {
            void loadSessionDetail(effectiveSessionId, {
                silent: true,
                preserveDraftSelections: true,
            });
        }, 2500);
        return () => window.clearInterval(timer);
    }, [effectiveSessionId, pendingUploadSignature, dismissedUploadedFileIds]);

    useEffect(() => {
        const container = messageStreamRef.current;
        if (!container) {
            return;
        }
        if (shouldAutoFollowMessageStreamRef.current) {
            container.scrollTop = container.scrollHeight;
        }
    }, [visibleMessages, loadingSessionDetail, currentStreamState]);

    async function loadKnowledgeCatalog() {
        setLoadingPrivateSamples(true);
        setTransportError(null);

        try {
            const knowledgeCatalog = await listAttachableKnowledgeItems();
            setKnowledgeItems(knowledgeCatalog);
        } catch {
            setTransportError("当前无法初始化对话工作台，请确认后端已启动。");
        } finally {
            setLoadingPrivateSamples(false);
        }
    }

    async function loadKnowledgeBases() {
        try {
            const items = await listKnowledgeBases();
            setKnowledgeBases(items);
            setSelectedKbId((current) => current ?? items.find((item) => item.is_default)?.kb_id ?? items[0]?.kb_id ?? null);
        } catch {
            setKnowledgeBases([]);
        }
    }

    async function loadSessionDetail(sessionId: string, options: LoadSessionDetailOptions = {}) {
        if (!options.silent) {
            setLoadingSessionDetail(true);
            setTransportError(null);
        }

        try {
            const detail = await getSession(sessionId);
            setActiveSession(detail);
            if (!options.preserveDraftSelections) {
                setKnowledgeScope(detail.knowledge_scope_last_used ?? "public");
                setDraftAttachedDocIds(getAttachedPrivateSampleIds(detail.attached_files));
                setDraftAttachedFileIds([]);
            } else {
                setDraftAttachedFileIds((current) =>
                    keepAvailableUploadedFileSelection(current, detail.attached_files, dismissedUploadedFileIdSet),
                );
            }
            if (!options.silent) {
                setSelectedCitationMessageId(resolvePreferredCitationMessageId(detail));
            }
        } catch {
            if (!options.silent) {
                setActiveSession(null);
                setTransportError("当前无法读取选中会话，请稍后重试。");
            }
        } finally {
            if (!options.silent) {
                setLoadingSessionDetail(false);
            }
        }
    }

    async function handleSaveAttachedSamples() {
        const workingSessionId = activeSessionId ?? activeSession?.session_id ?? null;
        if (!workingSessionId) {
            return;
        }
        setSavingAttachedSamples(true);
        setTransportError(null);
        try {
            const detail = await replaceAttachedKnowledgeItems(workingSessionId, draftAttachedDocIds);
            setActiveSession(detail);
            setDraftAttachedDocIds(getAttachedPrivateSampleIds(detail.attached_files));
            await refreshSessions(workingSessionId);
            setPrivateSampleDrawerOpen(false);
        } catch (error) {
            setTransportError(extractDetailMessage(error) ?? "当前无法保存知识条目挂接状态。");
        } finally {
            setSavingAttachedSamples(false);
        }
    }

    async function ensureComposerSession() {
        if (activeSessionId) {
            return activeSessionId;
        }

        const created = await createSessionRequest();
        setActiveSession(createEmptySessionDetail(created, knowledgeScope));
        syncSessionSummary(created, { activate: true });
        return created.session_id;
    }

    function applySessionTitleUpdate(sessionId: string, title: string) {
        updateSessionSummary(sessionId, { title });
        setActiveSession((current) =>
            current?.session_id === sessionId
                ? { ...current, title }
                : current,
        );
    }

    async function handleSubmit() {
        await startAskStream(question.trim(), { clearComposer: true });
    }

    async function startAskStream(questionText: string, options: { clearComposer?: boolean } = {}): Promise<boolean> {
        const trimmed = questionText.trim();
        const providerOverride = getActiveProviderOverride();
        if (!trimmed) {
            setTransportError("问题不能为空。");
            return false;
        }

        setSending(true);
        setTransportError(null);
        streamAbortRef.current?.abort();
        const controller = new AbortController();
        streamAbortRef.current = controller;
        replaceStreamMemoryState(null);
        replaceStreamContextSource(null);

        const draftUserMessageId = createDraftMessageId("user");
        const draftAssistantMessageId = createDraftMessageId("assistant");
        const now = new Date().toISOString();
        const draftQuestion = trimmed;
        setSelectedCitationMessageId(draftAssistantMessageId);

        let workingSessionId: string;
        try {
            workingSessionId = await ensureComposerSession();
        } catch {
            setTransportError("当前无法创建新对话，请稍后重试。");
            setSending(false);
            return false;
        }
        streamingSessionIdRef.current = workingSessionId;

        replaceStreamDraft({
            userMessage: {
                message_id: draftUserMessageId,
                role: "user",
                content: draftQuestion,
                created_at: now,
                citations: [],
                client_attachments: selectedUploadedAttachments,
            },
            assistantMessage: {
                message_id: draftAssistantMessageId,
                role: "assistant",
                content: "",
                created_at: now,
                status: "connecting",
                citations: [],
                retrieval_trace: null,
                generated_reports: [],
                client_state: "connecting",
                thinking_content: "",
                status_note: "正在连接模型…",
            },
        });
        if (options.clearComposer !== false) {
            setQuestion("");
        }

        let committedLocally = false;
        let completed = false;
        try {
            const response = await submitSessionAskStreamRequest(
                workingSessionId,
                {
                    question: draftQuestion,
                    knowledge_scope: knowledgeScope,
                    top_k: 5,
                    kb_id: selectedKbId,
                    rag_mode: ragMode,
                    attached_file_ids: selectedReadyUploadedAttachments.map((attachment) => attachment.file_id),
                    attached_knowledge_item_ids: draftAttachedDocIds,
                    provider_override: providerOverride,
                },
                {
                onMessageStart: (event) => {
                    setSelectedCitationMessageId(event.assistant_message_id ?? draftAssistantMessageId);
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        userMessage: {
                            ...draft.userMessage,
                            message_id: event.user_message_id ?? draft.userMessage.message_id,
                        },
                        assistantMessage: {
                            ...draft.assistantMessage,
                            message_id: event.assistant_message_id ?? draft.assistantMessage.message_id,
                            trace_id: event.trace_id ?? draft.assistantMessage.trace_id ?? null,
                            status: "connecting",
                            client_state: "connecting",
                            status_note: event.title_updated ? "标题已自动更新，正在连接模型…" : "正在连接模型…",
                        },
                    }));
                },
                onSessionTitle: (event) => {
                    if (!event.title_updated || !event.session_title) {
                        return;
                    }
                    applySessionTitleUpdate(workingSessionId, event.session_title);
                    void refreshSessions(workingSessionId).then((sessionList) => {
                        syncActiveSessionSummaryFromList(sessionList ?? [], workingSessionId);
                    });
                },
                onStatus: (event) => {
                    maybeShowReconnectToast(event, reconnectNoticeMode);
                    updateStreamDraftState((draft) => {
                        const nextState = mapLifecycleStatusToMessageState(event.status, event.attempt, event.max_attempts, event.recovered);
                        return {
                            ...draft,
                            assistantMessage: {
                                ...draft.assistantMessage,
                                status: nextState.status,
                                client_state: nextState.client_state,
                                status_note: event.status_note ?? nextState.status_note,
                            },
                        };
                    });
                },
                onThinkingDelta: (event) => {
                    const delta = extractDeltaText(event);
                    if (!delta) {
                        return;
                    }
                    const isSyntheticThinking = Boolean(event.synthetic);
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: {
                            ...draft.assistantMessage,
                            status: isSyntheticThinking ? draft.assistantMessage.status ?? "thinking" : "thinking",
                            client_state: isSyntheticThinking ? draft.assistantMessage.client_state ?? "connecting" : "thinking",
                            status_note: isSyntheticThinking ? "正在整理问题与依据…" : "正在结合上下文组织回答…",
                            thinking_content: isSyntheticThinking ? draft.assistantMessage.thinking_content ?? "" : `${draft.assistantMessage.thinking_content ?? ""}${delta}`,
                        },
                    }));
                },
                onAnswerDelta: (event) => {
                    const delta = extractDeltaText(event);
                    if (!delta) {
                        return;
                    }
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: {
                            ...draft.assistantMessage,
                            status: "streaming",
                            client_state: "streaming",
                            status_note: "已建立连接，正在输出…",
                            content: `${draft.assistantMessage.content}${delta}`,
                        },
                    }));
                },
                onMetadata: (event) => {
                    setSelectedCitationMessageId(event.assistant_message_id ?? draftAssistantMessageId);
                    replaceStreamMemoryState(normalizeAskStreamMemoryState(event.memory_state));
                    replaceStreamContextSource(event.context_source ?? null);
                    if (event.title_updated && event.session_title) {
                        applySessionTitleUpdate(workingSessionId, event.session_title);
                    }
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: mergeStreamMetadata(draft.assistantMessage, event),
                    }));
                },
                onDone: (event) => {
                    setSelectedCitationMessageId(event.assistant_message_id ?? draftAssistantMessageId);
                    replaceStreamMemoryState(normalizeAskStreamMemoryState(event.memory_state));
                    replaceStreamContextSource(event.context_source ?? null);
                    if (event.title_updated && event.session_title) {
                        applySessionTitleUpdate(workingSessionId, event.session_title);
                    }
                    window.setTimeout(() => {
                        void refreshSessions().then((sessionList) => {
                            syncActiveSessionSummaryFromList(sessionList ?? [], workingSessionId);
                        });
                    }, 12_000);
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: {
                            ...mergeStreamMetadata(draft.assistantMessage, event),
                            status: event.status ?? "ok",
                            client_state: "done",
                            status_note: event.title_updated ? "标题已自动更新" : draft.assistantMessage.status_note ?? null,
                        },
                    }));
                },
                onError: (event) => {
                    setSelectedCitationMessageId(event.assistant_message_id ?? draftAssistantMessageId);
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: {
                            ...draft.assistantMessage,
                            status: event.status ?? "provider_error",
                            client_state: event.status === "provider_error" ? "failed" : "error",
                            content: event.message ?? event.detail ?? "当前问答服务暂不可用，请稍后重试。",
                            status_note: "本次未能连接到模型，请稍后重试或检查模型设置",
                        },
                    }));
                },
                },
                { signal: controller.signal },
            );

            if (response.status === "invalid_input") {
                setTransportError(response.answer);
            }
            if (response.status === "provider_error") {
                setTransportError("模型服务当前响应失败，系统已把这次失败记录到当前会话。");
            }

            commitDraftToActiveSession(workingSessionId, knowledgeScope);
            committedLocally = true;
            replaceStreamDraft(null);
            setDraftAttachedFileIds([]);

            const sessionList = await refreshSessions(workingSessionId);
            syncActiveSessionSummaryFromList(sessionList ?? [], workingSessionId);
            completed = true;
        } catch (error) {
            if (controller.signal.aborted || isAbortLikeError(error)) {
                return false;
            }
            if (isAskResponse(error)) {
                if (error.status === "invalid_input") {
                    setTransportError(error.answer);
                } else {
                    setTransportError("模型服务当前响应失败，系统已把这次失败记录到当前会话。");
                    await refreshSessions(workingSessionId);
                    await loadSessionDetail(workingSessionId);
                }
            } else {
                setTransportError("当前问答服务暂不可达，请确认后端已启动且模型服务可用。");
            }
        } finally {
            setSending(false);
            streamAbortRef.current = null;
            if (streamingSessionIdRef.current === workingSessionId) {
                streamingSessionIdRef.current = null;
            }
            if (!committedLocally) {
                replaceStreamDraft(null);
            }
        }
        return completed;
    }

    async function handleRegenerateMessage(targetMessage: ChatMessageView) {
        if (targetMessage.role !== "assistant") {
            return;
        }
        if (sending) {
            antdMessage.warning("当前仍有回答生成中，请稍后再重新生成。");
            return;
        }
        const targetIndex = visibleMessages.findIndex((message) => message.message_id === targetMessage.message_id);
        const sourceUserMessage = targetIndex >= 0
            ? visibleMessages.slice(0, targetIndex).reverse().find((message) => message.role === "user")
            : null;
        if (!sourceUserMessage?.content?.trim()) {
            antdMessage.error("未找到这条回答对应的原始提问。");
            return;
        }

        console.debug("[regenerate]", {
            targetMessageId: targetMessage.message_id,
            sourceMessageId: sourceUserMessage.message_id,
            sessionId: activeSession?.session_id ?? activeSessionId,
        });
        setRegeneratingMessageId(targetMessage.message_id);
        setSelectedCitationMessageId(targetMessage.message_id);
        try {
            const completed = await startAskStream(sourceUserMessage.content, { clearComposer: false });
            if (completed) {
                antdMessage.success("已按原问题重新生成一版回答。");
            } else {
                antdMessage.error("重新生成失败，请稍后重试。");
            }
        } catch (error) {
            console.error("[regenerate] failed", error);
            antdMessage.error("重新生成失败，请稍后重试。");
        } finally {
            setRegeneratingMessageId(null);
        }
    }

    async function handleShareMessage(targetMessage: ChatMessageView) {
        if (!targetMessage.content.trim()) {
            antdMessage.warning("这条消息没有可分享的内容。");
            return;
        }
        const shareText = buildMessageShareText(targetMessage, activeSession?.title);
        console.debug("[share]", targetMessage.message_id);
        try {
            await writeClipboardText(shareText);
            antdMessage.success("已复制这条回答的 Markdown 内容。");
        } catch (error) {
            console.error("[share] failed", error);
            antdMessage.error("分享失败，请稍后重试。");
        }
    }

    function dismissUploadedAttachment(fileId: string) {
        setDismissedUploadedFileIds((current) => (current.includes(fileId) ? current : [...current, fileId]));
        setDraftAttachedFileIds((current) => current.filter((currentFileId) => currentFileId !== fileId));
    }

    async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
        const files = Array.from(event.target.files ?? []);
        event.target.value = "";
        await handleUploadFiles(files);
    }

    async function handleUploadFiles(files: File[], targetSessionId?: string | null) {
        if (!files.length) {
            return;
        }

        let workingSessionId: string;
        try {
            workingSessionId = targetSessionId ?? (await ensureComposerSession());
        } catch {
            setUploadError("当前无法创建新对话，请稍后重试。");
            return;
        }

        setUploading(true);
        setUploadError(null);
        try {
            const uploadedFileIds: string[] = [];
            for (const file of files) {
                const uploaded = await uploadSessionFile(workingSessionId, file);
                uploadedFileIds.push(uploaded.file_id);
            }
            const sessionList = await refreshSessions(workingSessionId);
            syncActiveSessionSummaryFromList(sessionList ?? [], workingSessionId);
            await loadSessionDetail(workingSessionId, { silent: true, preserveDraftSelections: true });
            setDraftAttachedFileIds((current) => [...new Set([...current, ...uploadedFileIds])]);
        } catch (error) {
            setUploadError(extractDetailMessage(error) ?? "附件上传失败，请确认文件格式、大小和会话状态。");
        } finally {
            setUploading(false);
        }
    }

    function handleDragOver(event: DragEvent<HTMLDivElement>) {
        event.preventDefault();
        if (event.dataTransfer.types.includes("Files")) {
            setDraggingFiles(true);
        }
    }

    function handleDragLeave(event: DragEvent<HTMLDivElement>) {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setDraggingFiles(false);
        }
    }

    function handleDrop(event: DragEvent<HTMLDivElement>) {
        event.preventDefault();
        setDraggingFiles(false);
        void handleUploadFiles(Array.from(event.dataTransfer.files ?? []));
    }

    function openCitationPanel(messageId: string) {
        setSelectedCitationMessageId(messageId);
        setSidePanelOpen(true);
    }

    function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
            event.stopPropagation();
            return;
        }

        const shouldSendWithEnter =
            sendShortcut === "enter"
                ? event.key === "Enter" && !event.shiftKey
                : event.key === "Enter" && (event.ctrlKey || event.metaKey);

        if (shouldSendWithEnter && !event.nativeEvent.isComposing) {
            event.preventDefault();
            if (!sending) {
                void handleSubmit();
            }
        }
    }

    function replaceStreamDraft(next: ChatDraft | null) {
        streamDraftRef.current = next;
        setStreamDraft(next);
    }

    function updateStreamDraftState(updater: (draft: ChatDraft) => ChatDraft) {
        setStreamDraft((current) => {
            const next = updateStreamDraft(current, updater);
            streamDraftRef.current = next;
            return next;
        });
    }

    function replaceStreamMemoryState(next: SessionDetail["memory_state"] | null) {
        streamMemoryStateRef.current = next;
        setStreamMemoryState(next);
    }

    function replaceStreamContextSource(next: StreamContextSource | null) {
        streamContextSourceRef.current = next;
        setStreamContextSource(next);
    }

    function commitDraftToActiveSession(sessionId: string, nextKnowledgeScope: KnowledgeScope) {
        const draft = streamDraftRef.current;
        if (!draft) {
            return;
        }
        const nextMemoryState = streamMemoryStateRef.current;
        setActiveSession((current) => {
            if (!current || current.session_id !== sessionId) {
                return current;
            }
            const existingMessages = current.messages.filter(
                (message) =>
                    message.message_id !== draft.userMessage.message_id &&
                    message.message_id !== draft.assistantMessage.message_id,
            );
            const nextMessages = [...existingMessages, draft.userMessage, draft.assistantMessage];
            return {
                ...current,
                messages: nextMessages,
                message_count: nextMessages.length,
                updated_at: draft.assistantMessage.created_at,
                knowledge_scope_last_used: nextKnowledgeScope,
                source_summary: draft.assistantMessage.source_summary ?? current.source_summary ?? null,
                memory_state: nextMemoryState ?? current.memory_state ?? null,
            };
        });
    }

    function syncActiveSessionSummaryFromList(sessionList: SessionSummary[], sessionId: string) {
        const matched = sessionList.find((session) => session.session_id === sessionId);
        if (!matched) {
            return;
        }
        setActiveSession((current) => {
            if (!current || current.session_id !== sessionId) {
                return current;
            }
            return {
                ...current,
                title: matched.title,
                created_at: matched.created_at,
                updated_at: matched.updated_at,
                message_count: matched.message_count,
                file_count: matched.file_count,
                attached_private_sample_count: matched.attached_private_sample_count,
                attached_knowledge_item_count: matched.attached_knowledge_item_count,
            };
        });
    }

    function handleMessageStreamScroll() {
        const container = messageStreamRef.current;
        if (!container) {
            return;
        }
        const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        shouldAutoFollowMessageStreamRef.current = distanceToBottom <= 96;
    }

    const contextDetailOverlay = (
        <div className="chat-context-popover">
            <Space size={8} wrap>
                {effectiveMemoryState ? (
                    <>
                        <Tag>
                            占用（估算）：{formatContextEstimate(effectiveMemoryState.context_usage_estimate)} / {formatContextEstimate(effectiveMemoryState.context_budget_estimate)}
                        </Tag>
                        <Tag>已摘要覆盖：{effectiveMemoryState.compacted_message_count} 条</Tag>
                        <Tag>摘要状态：{effectiveMemoryState.summary_present ? "已启用" : "未启用"}</Tag>
                        <Tag>
                            最近摘要：{effectiveMemoryState.summary_updated_at ? formatTimestamp(effectiveMemoryState.summary_updated_at) : "暂无"}
                        </Tag>
                    </>
                ) : (
                    <Tag>当前暂无会话摘要状态。</Tag>
                )}
            </Space>
            <Typography.Paragraph type="secondary" className="chat-context-popover__hint">
                {effectiveMemoryState ? buildMemoryHint(effectiveMemoryState) : currentContextSourceText}
            </Typography.Paragraph>
            {effectiveMemoryState ? (
                <Typography.Paragraph type="secondary" className="chat-context-popover__hint">
                    {currentContextSourceText}
                </Typography.Paragraph>
            ) : null}
        </div>
    );

    const composerSettings = (
        <div className="chat-composer-settings">
            <Typography.Text strong>问答范围</Typography.Text>
            <Segmented<KnowledgeScope>
                value={knowledgeScope}
                onChange={(value) => setKnowledgeScope(value)}
                options={[
                    { label: "公共政策", value: "public" },
                    { label: "知识条目", value: "private_sample" },
                    { label: "混合", value: "mixed" },
                ]}
            />
            <Button icon={<TagsOutlined />} onClick={() => setPrivateSampleDrawerOpen(true)} disabled={loadingPrivateSamples}>
                管理知识条目挂接
            </Button>
            <Typography.Text strong>RAG 知识库</Typography.Text>
            <Select
                className="chat-composer-settings__select"
                value={selectedKbId ?? undefined}
                allowClear
                placeholder="默认自动知识库"
                onChange={(value) => setSelectedKbId(value ?? null)}
                options={knowledgeBases.map((item) => ({
                    label: `${item.name}${item.is_default ? " · 默认" : ""}`,
                    value: item.kb_id,
                }))}
            />
            <Typography.Text strong>检索模式</Typography.Text>
            <Segmented<RagRetrievalMode>
                value={ragMode}
                onChange={(value) => setRagMode(value)}
                options={[
                    { label: "Dense", value: "dense" },
                    { label: "Sparse", value: "sparse" },
                    { label: "Hybrid", value: "hybrid" },
                    { label: "Hybrid+Rerank", value: "hybrid_rerank" },
                ]}
            />
            <Typography.Paragraph type="secondary" className="chat-composer-settings__hint">
                默认走 RAG-Pro 主脊柱。选择知识库后，Ask 会带上 kb_id 与检索模式，并在回答里展示 RAG trace。
            </Typography.Paragraph>
        </div>
    );

    const showComposerMeta =
        selectedUploadedAttachments.length > 0 ||
        privateAttachments.length > 0 ||
        Boolean(currentStreamTag) ||
        uploading;
    const contextCircleBackground = `conic-gradient(#1677ff 0 ${contextUsagePercent}%, rgba(22, 119, 255, 0.14) ${contextUsagePercent}% 100%)`;

    return (
        <div
            className={`chat-workbench chat-workbench--single-column${focusModeEnabled ? " chat-workbench--focus-mode" : ""}${draggingFiles ? " chat-workbench--dragging-files" : ""}${isNewDraftChat ? " chat-workbench--empty-chat" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {draggingFiles ? (
                <div className="chat-upload-overlay">
                    <div className="chat-upload-overlay__panel">
                        <Typography.Text strong>松开鼠标即可上传附件</Typography.Text>
                        <Typography.Text type="secondary">
                            文件会先解析成可检索片段，解析完成后才会进入本轮提问。
                        </Typography.Text>
                    </div>
                </div>
            ) : null}
            <div className="chat-workbench__main">
                <Card
                    className="chat-workbench__stream-card"
                    title={(
                        <div className="chat-stream-card__title">
                            <Typography.Text strong className="chat-stream-card__title-text">
                                {activeSession?.title ?? "CarbonRag"}
                            </Typography.Text>
                            {activeSession ? (
                                <Tag color={scopeColorMap[knowledgeScope]} className="chat-stream-card__scope-tag">
                                    {scopeLabelMap[knowledgeScope]}
                                </Tag>
                            ) : null}
                        </div>
                    )}
                    extra={
                        <Space size={8} className="chat-stream-toolbar">
                            <Popover trigger="click" placement="bottomRight" content={composerSettings}>
                                <Button icon={<MoreOutlined />}>更多设置</Button>
                            </Popover>
                            {shouldShowContextDebug ? (
                                <Popover trigger="click" placement="bottomRight" content={contextDetailOverlay}>
                                    <button
                                        type="button"
                                        className="chat-context-circle"
                                        style={{ background: contextCircleBackground }}
                                        aria-label={`查看上下文详情，当前占用 ${contextUsagePercent}%`}
                                    >
                                        <span className="chat-context-circle__core">{contextUsagePercent}</span>
                                    </button>
                                </Popover>
                            ) : null}
                            <Button icon={<SettingOutlined />} onClick={() => setSidePanelOpen(true)}>
                                参考资料 {currentSourceSummary.total_citation_count > 0 ? `(${currentSourceSummary.total_citation_count})` : ""}
                            </Button>
                        </Space>
                    }
                >
                    {loadingSessionDetail ? (
                        <div className="chat-workbench__loading"><Spin /></div>
                    ) : (
                        <>
                            <div ref={messageStreamRef} className="chat-message-stream" onScroll={handleMessageStreamScroll}>
                                {visibleMessages.length === 0 ? (
                                    <div className="chat-message-stream__empty chat-message-stream__empty--new-chat">
                                        <Typography.Title level={2}>{newChatPrompt}</Typography.Title>
                                    </div>
                                ) : (
                                    visibleMessages.map((message) => (
                                        <MessageBubble
                                            key={message.message_id}
                                            message={message}
                                            sessionId={activeSession?.session_id ?? "draft"}
                                            activeCitation={message.message_id === selectedCitationMessageId}
                                            onOpenThinking={() => setSelectedThinkingMessageId(message.message_id)}
                                            onSelectCitations={() => openCitationPanel(message.message_id)}
                                            onShareMessage={handleShareMessage}
                                            onRegenerateMessage={handleRegenerateMessage}
                                            regenerating={regeneratingMessageId === message.message_id}
                                            actionDisabled={sending && regeneratingMessageId !== message.message_id}
                                            onEditUserMessage={(content) => {
                                                setQuestion(content);
                                                antdMessage.info("已放回输入框，可继续编辑后发送。");
                                            }}
                                            onOpenFilePreview={setFilePreviewTarget}
                                        />
                                    ))
                                )}
                            </div>
                        </>
                    )}
                </Card>

                <div className="chat-composer-dock">
                    <div className="chat-composer-dock__main">
                        <Tooltip title="添加附件">
                            <Button
                                className="chat-composer-dock__action"
                                icon={<PaperClipOutlined />}
                                onClick={() => fileInputRef.current?.click()}
                                loading={uploading}
                            />
                        </Tooltip>
                        <Input.TextArea
                            className="chat-composer-dock__input"
                            value={question}
                            onChange={(event) => setQuestion(event.target.value)}
                            onKeyDown={handleComposerKeyDown}
                            autoSize={{ minRows: 1, maxRows: 6 }}
                            maxLength={2000}
                            autoFocus
                            placeholder="例如：结合当前知识条目，压缩空气系统的能耗问题是什么？或者：双碳目标对这家知识条目意味着什么？"
                        />
                        <Button className="chat-composer-dock__send" type="primary" icon={<MessageOutlined />} onClick={handleSubmit} loading={sending}>
                            发送
                        </Button>
                    </div>
                    {showComposerMeta ? (
                        <div className="chat-composer-dock__meta">
                            <Space size={8} wrap className="chat-composer-dock__chips">
                                {selectedUploadedAttachments.map((attachment) => (
                                    <ComposerAttachmentChip
                                        key={attachment.file_id}
                                        attachment={attachment}
                                        onRemove={() => dismissUploadedAttachment(attachment.file_id)}
                                        onOpenPreview={() => setFilePreviewTarget(filePreviewTargetFromAttachment(attachment))}
                                    />
                                ))}
                                {privateAttachments.length > 0 ? <Tag color="magenta">知识条目 {privateAttachments.length}</Tag> : null}
                                {currentStreamTag ? <Tag color={currentStreamTag.color}>{currentStreamTag.label}</Tag> : null}
                                {uploading ? <Tag color="processing">正在上传附件</Tag> : null}
                            </Space>
                        </div>
                    ) : null}
                    <input
                        ref={fileInputRef}
                        hidden
                        type="file"
                        multiple
                        accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.html,.pptx,.png,.jpg,.jpeg"
                        onChange={handleUploadChange}
                    />
                </div>
            </div>

            <Drawer
                title="参考资料与状态"
                width={400}
                open={sidePanelOpen}
                onClose={() => setSidePanelOpen(false)}
            >
                <Card
                    title="当前回答依据"
                    extra={
                        <Space size={8} wrap>
                            <Tag color="green">{currentSourceSummary.total_citation_count} 条引用</Tag>
                            {currentSourceSummary.public_policy_count > 0 ? <Tag color="blue">政策 {currentSourceSummary.public_policy_count}</Tag> : null}
                            {(currentSourceSummary.public_policy_demo_count ?? 0) > 0 ? <Tag color="orange">演示样例 {currentSourceSummary.public_policy_demo_count ?? 0}</Tag> : null}
                            {currentSourceSummary.private_sample_count > 0 ? <Tag color="magenta">知识条目 {currentSourceSummary.private_sample_count}</Tag> : null}
                            {(currentSourceSummary.private_upload_count ?? 0) > 0 ? <Tag color="green">个人上传 {currentSourceSummary.private_upload_count ?? 0}</Tag> : null}
                        </Space>
                    }
                >
                    <Typography.Paragraph type="secondary">
                        默认只在这里展开完整引用。先读回答正文，再按需查看政策、知识条目或个人上传片段。
                    </Typography.Paragraph>
                    {selectedRetrievalTrace ? (
                        <RagProofPanel
                            trace={selectedRetrievalTrace}
                            knowledgeBases={knowledgeBases}
                            selectedKbId={selectedKbId}
                            ragMode={ragMode}
                            citationCount={selectedCitationMessage?.citations.length ?? 0}
                            selectedChunks={selectedCitationMessage?.citations ?? []}
                        />
                    ) : null}
                    {selectedCitationMessage?.citations.length ? (
                        <Collapse
                            className="chat-citation-collapse"
                            ghost
                            defaultActiveKey={[]}
                            items={buildCitationCollapseItems(citationGroups, setFilePreviewTarget)}
                        />
                    ) : (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选中一条带依据的助手消息后，这里会展示来源片段。" />
                    )}
                </Card>
                {isAdmin ? (
                    <Collapse
                        className="chat-side-drawer__system"
                        ghost
                        defaultActiveKey={[]}
                        items={[
                            {
                                key: "system-status",
                                label: "系统状态",
                                children: <SystemInfoPanel />,
                            },
                        ]}
                    />
                ) : null}
            </Drawer>

            <Drawer
                title="思考过程"
                width={420}
                open={Boolean(selectedThinkingMessageId)}
                onClose={() => setSelectedThinkingMessageId(null)}
            >
                {selectedThinkingMessage?.thinking_content?.trim() ? (
                    <Typography.Paragraph className="chat-thinking-drawer__content">
                        {selectedThinkingMessage.thinking_content}
                    </Typography.Paragraph>
                ) : (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="这条消息没有可回看的思考过程。" />
                )}
            </Drawer>

            <Drawer
                title="管理当前会话的知识条目挂接"
                width={420}
                open={privateSampleDrawerOpen}
                onClose={() => setPrivateSampleDrawerOpen(false)}
                extra={<Button type="primary" onClick={handleSaveAttachedSamples} loading={savingAttachedSamples}>保存挂接</Button>}
            >
                <Typography.Paragraph type="secondary">
                    这里选择的是当前会话可用于知识条目 / 混合检索的知识条目。共享样例和已入库的个人上传都会出现在这里。
                </Typography.Paragraph>
                {loadingPrivateSamples ? (
                    <div className="chat-workbench__loading"><Spin /></div>
                ) : (
                    <List
                        className="private-sample-list"
                        dataSource={knowledgeItems}
                        renderItem={(item) => {
                            const checked = draftAttachedDocIds.includes(item.knowledge_item_id);
                            return (
                                <List.Item key={item.knowledge_item_id}>
                                    <div className="private-sample-list__item">
                                        <Checkbox checked={checked} onChange={(event) => setDraftAttachedDocIds((current) => toggleDocId(current, item.knowledge_item_id, event.target.checked))}>
                                            <Typography.Text strong>{item.title}</Typography.Text>
                                        </Checkbox>
                                        <Space size={8} wrap>
                                            <Tag color="magenta">{item.source_label}</Tag>
                                            <Tag>{item.library_scope === "shared" ? "共享" : "个人"}</Tag>
                                        </Space>
                                    </div>
                                </List.Item>
                            );
                        }}
                    />
                )}
            </Drawer>

            <FilePreviewDrawer
                open={Boolean(filePreviewTarget)}
                target={filePreviewTarget}
                onClose={() => setFilePreviewTarget(null)}
            />
        </div>
    );
}

interface MessageBubbleProps {
    message: ChatMessageView;
    sessionId: string;
    activeCitation: boolean;
    onOpenThinking: () => void;
    onSelectCitations: () => void;
    onShareMessage?: (message: ChatMessageView) => void | Promise<void>;
    onRegenerateMessage?: (message: ChatMessageView) => void | Promise<void>;
    regenerating?: boolean;
    actionDisabled?: boolean;
    onEditUserMessage?: (content: string) => void;
    onOpenFilePreview?: (target: FilePreviewTarget) => void;
}

function ComposerAttachmentChip({ attachment, onRemove, onOpenPreview }: { attachment: SessionAttachment; onRemove: () => void; onOpenPreview?: () => void }) {
    return (
        <Popover trigger="click" content={<FileAttachmentPopover attachment={attachment} onOpenPreview={onOpenPreview} />}>
            <Tag
                className="chat-composer-attachment"
                closable
                color={fileAttachmentStatusColor(attachment)}
                onClose={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onRemove();
                }}
            >
                <FileTextOutlined />
                <span className="chat-composer-attachment__name">{attachment.filename}</span>
                <span className="chat-composer-attachment__status">{fileAttachmentStatusLabel(attachment)}</span>
            </Tag>
        </Popover>
    );
}

function MessageAttachmentStrip({ attachments, onOpenPreview }: { attachments: SessionAttachment[]; onOpenPreview?: (target: FilePreviewTarget) => void }) {
    if (!attachments.length) {
        return null;
    }
    return (
        <div className="chat-message-attachments">
            {attachments.map((attachment) => (
                <Popover key={attachment.file_id} trigger="click" content={<FileAttachmentPopover attachment={attachment} onOpenPreview={() => onOpenPreview?.(filePreviewTargetFromAttachment(attachment))} />}>
                    <span className="chat-message-attachment">
                        <FileTextOutlined />
                        <span className="chat-message-attachment__name">{attachment.filename}</span>
                        <span className="chat-message-attachment__status">{fileAttachmentStatusLabel(attachment)}</span>
                    </span>
                </Popover>
            ))}
        </div>
    );
}

function GeneratedReportCards({ reports }: { reports: GeneratedReportSummary[] }) {
    const files = dedupeGeneratedReportFiles(
        reports.flatMap((report) => (report.files ?? []).map((file) => ({ ...file, reportTitle: report.title ?? "生成的报告" }))),
    );
    const errors = reports
        .filter((report) => report.status !== "success" && report.error_message)
        .map((report) => report.error_message as string);

    async function handleDownload(file: GeneratedReportFile) {
        try {
            const { blob, filename } = await downloadReportFile(file);
            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(objectUrl);
        } catch {
            antdMessage.error("下载失败，请确认后端服务和登录状态正常。");
        }
    }

    if (!files.length && !errors.length) {
        return null;
    }

    return (
        <div className="chat-generated-reports">
            {files.length ? (
                <>
                    <div className="chat-generated-reports__header">
                        <FileTextOutlined />
                        <Typography.Text strong>已生成可下载文件</Typography.Text>
                    </div>
                    <div className="chat-generated-reports__list">
                        {files.map((file) => (
                            <div className="chat-generated-report-card" key={file.file_id || file.download_url}>
                                <div className="chat-generated-report-card__main">
                                    <Typography.Text strong ellipsis={{ tooltip: file.filename }}>
                                        {file.filename}
                                    </Typography.Text>
                                    <Space size={6} wrap>
                                        <Tag color={file.format === "pdf" ? "volcano" : "blue"}>{String(file.format || "file").toUpperCase()}</Tag>
                                        {file.file_size_bytes ? <Typography.Text type="secondary">{formatBytes(file.file_size_bytes)}</Typography.Text> : null}
                                    </Space>
                                </div>
                                <Button
                                    type="primary"
                                    size="small"
                                    icon={<DownloadOutlined />}
                                    onClick={() => void handleDownload(file)}
                                >
                                    下载
                                </Button>
                            </div>
                        ))}
                    </div>
                </>
            ) : null}
            {errors.length ? (
                <Alert
                    type="warning"
                    showIcon
                    message="报告文件未生成"
                    description={errors.join("；")}
                />
            ) : null}
        </div>
    );
}

function MessageBubble({
    message,
    sessionId,
    activeCitation,
    onOpenThinking,
    onSelectCitations,
    onShareMessage,
    onRegenerateMessage,
    regenerating = false,
    actionDisabled = false,
    onEditUserMessage,
    onOpenFilePreview,
}: MessageBubbleProps) {
    const isAssistant = message.role === "assistant";
    const isSystem = message.role === "system";
    const hasCitations = isAssistant && message.citations.length > 0;
    const hasRealThinkingContent = Boolean(message.thinking_content?.trim());
    const preparingActive =
        message.client_state === "pending" ||
        message.client_state === "connecting" ||
        message.client_state === "reconnecting";
    const thinkingActive = message.client_state === "thinking";
    const activityActive = preparingActive || thinkingActive;
    const shouldShowThinking = isAssistant && (activityActive || hasRealThinkingContent);
    const messageContent = resolveMessageContent(message, isAssistant);
    const generatedReports = isAssistant ? extractGeneratedReports(message) : [];
    const thinkingStartedAtRef = useRef(Date.now());
    const [thinkingElapsedSeconds, setThinkingElapsedSeconds] = useState(0);
    const [finalThinkingElapsedSeconds, setFinalThinkingElapsedSeconds] = useState<number | null>(null);
    const previousClientStateRef = useRef<AssistantLifecycleState | undefined>(message.client_state);

    useEffect(() => {
        const previousState = previousClientStateRef.current;
        const currentState = message.client_state;

        if (currentState === "thinking" && previousState !== currentState) {
            thinkingStartedAtRef.current = Date.now();
            setFinalThinkingElapsedSeconds(null);
            setThinkingElapsedSeconds(0);
        }

        const justFinishedThinking = previousState === "thinking" && currentState !== "thinking";
        if (hasRealThinkingContent && !thinkingActive && finalThinkingElapsedSeconds === null && justFinishedThinking) {
            const elapsed = Math.max(1, Math.round((Date.now() - thinkingStartedAtRef.current) / 1000));
            setFinalThinkingElapsedSeconds(elapsed);
        }

        previousClientStateRef.current = currentState;
    }, [finalThinkingElapsedSeconds, hasRealThinkingContent, message.client_state, message.message_id, thinkingActive]);

    useEffect(() => {
        if (!thinkingActive) {
            return;
        }
        const timer = window.setInterval(() => {
            setThinkingElapsedSeconds(Math.max(1, Math.round((Date.now() - thinkingStartedAtRef.current) / 1000)));
        }, 1000);
        return () => window.clearInterval(timer);
    }, [thinkingActive, message.message_id]);

    const resolvedFinalThinkingSeconds = finalThinkingElapsedSeconds ?? (thinkingElapsedSeconds || 1);
    const thinkingDurationText = thinkingActive
        ? `思考中… ${formatDurationSeconds(thinkingElapsedSeconds)}`
        : preparingActive
            ? resolvePreparationStatusText(message.client_state)
            : hasRealThinkingContent
            ? `思考了 ${formatDurationSeconds(resolvedFinalThinkingSeconds)}`
            : "思考中…";
    const thinkingPreview = activityActive
        ? message.status_note || "正在梳理上下文、依据和用户问题"
        : "查看思考过程";

    return (
        <div
            className={
                isAssistant
                    ? "chat-message chat-message--assistant"
                    : isSystem
                        ? "chat-message chat-message--system"
                        : "chat-message chat-message--user"
            }
        >
            <Card
                size="small"
                className={
                    isAssistant
                        ? "chat-message__card chat-message__card--assistant"
                        : isSystem
                            ? "chat-message__card chat-message__card--system"
                            : "chat-message__card chat-message__card--user"
                }
            >
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    {isSystem ? (
                        <Space size={8} wrap className="chat-message__header">
                            <Typography.Text className="chat-message__speaker chat-message__speaker--system">系统消息</Typography.Text>
                            <Typography.Text type="secondary">{formatTimestamp(message.created_at)}</Typography.Text>
                        </Space>
                    ) : null}
                    {isAssistant && shouldShowThinking ? (
                        <button
                            type="button"
                            className={activityActive ? "chat-message__thinking-inline chat-message__thinking-inline--active" : "chat-message__thinking-inline"}
                            onClick={hasRealThinkingContent ? onOpenThinking : undefined}
                            disabled={!hasRealThinkingContent}
                            aria-label={hasRealThinkingContent ? "打开思考过程" : thinkingActive ? "正在思考" : "正在准备回答"}
                        >
                            <span className="chat-thinking-pulse" aria-hidden="true" />
                            <span className="chat-message__thinking-time">{thinkingDurationText}</span>
                            <span className="chat-message__thinking-preview">{thinkingPreview}</span>
                            <span className="chat-message__thinking-chevron" aria-hidden="true">›</span>
                        </button>
                    ) : null}
                    <div className={isAssistant ? "chat-message__content chat-message__content--assistant" : "chat-message__content"}>
                        {renderMessageContent(message, isAssistant)}
                    </div>
                    {isAssistant && generatedReports.length ? <GeneratedReportCards reports={generatedReports} /> : null}
                    {!isAssistant && !isSystem ? <MessageAttachmentStrip attachments={message.client_attachments ?? []} onOpenPreview={onOpenFilePreview} /> : null}
                    {!isAssistant && !isSystem ? (
                        <div className="chat-message__quick-actions chat-message__quick-actions--user">
                            <Tooltip title="复制">
                                <Button
                                    type="text"
                                    size="small"
                                    icon={<CopyOutlined />}
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        void copyTextToClipboard(messageContent, "已复制这条消息。");
                                    }}
                                />
                            </Tooltip>
                            <Tooltip title="编辑并放回输入框">
                                <Button
                                    type="text"
                                    size="small"
                                    icon={<EditOutlined />}
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        onEditUserMessage?.(messageContent);
                                    }}
                                />
                            </Tooltip>
                        </div>
                    ) : null}
                    {isAssistant ? (
                        <div className="chat-message__meta">
                            <AssistantQuickActions
                                content={messageContent}
                                hasCitations={hasCitations}
                                activeCitation={activeCitation}
                                onSelectCitations={onSelectCitations}
                                citationCount={message.citations.length}
                                traceId={message.trace_id}
                                sessionId={sessionId}
                                createdAt={message.created_at}
                                message={message}
                                regenerating={regenerating}
                                disabled={actionDisabled}
                                onShare={onShareMessage}
                                onRegenerate={onRegenerateMessage}
                            />
                        </div>
                    ) : null}
                </Space>
            </Card>
        </div>
    );
}

interface AssistantQuickActionsProps {
    message: ChatMessageView;
    content: string;
    hasCitations: boolean;
    activeCitation: boolean;
    onSelectCitations: () => void;
    citationCount: number;
    traceId?: string | null;
    sessionId: string;
    createdAt: string;
    regenerating: boolean;
    disabled: boolean;
    onShare?: (message: ChatMessageView) => void | Promise<void>;
    onRegenerate?: (message: ChatMessageView) => void | Promise<void>;
}

function AssistantQuickActions({
    message,
    content,
    hasCitations,
    activeCitation,
    onSelectCitations,
    citationCount,
    traceId,
    sessionId,
    createdAt,
    regenerating,
    disabled,
    onShare,
    onRegenerate,
}: AssistantQuickActionsProps) {
    const moreContent = (
        <Space direction="vertical" size={10} className="chat-message-action-popover">
            <Typography.Text type="secondary">{formatTimestamp(createdAt)}</Typography.Text>
            <Button type="text" icon={<BranchesOutlined />} onClick={() => antdMessage.info("分支对话功能后续接入。")}>
                新聊天中的分支
            </Button>
            <Button type="text" icon={<SoundOutlined />} onClick={() => antdMessage.info("朗读功能后续接入。")}>
                朗读
            </Button>
        </Space>
    );

    return (
        <div className="chat-message__quick-actions chat-message__quick-actions--assistant">
            <Tooltip title="复制回答">
                <Button
                    type="text"
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={(event) => {
                        event.stopPropagation();
                        void copyTextToClipboard(content, "已复制回答。");
                    }}
                />
            </Tooltip>
            {traceId ? (
                <FeedbackButtonGroup
                    targetType="ask"
                    traceId={traceId}
                    sessionId={sessionId}
                    size="small"
                    iconOnly
                />
            ) : null}
            <Tooltip title="分享">
                <Button
                    type="text"
                    size="small"
                    icon={<ShareAltOutlined />}
                    disabled={disabled}
                    onClick={(event) => {
                        event.stopPropagation();
                        void onShare?.(message);
                    }}
                />
            </Tooltip>
            <Tooltip title="重新生成">
                <Button
                    type="text"
                    size="small"
                    icon={<ReloadOutlined spin={regenerating} />}
                    loading={regenerating}
                    disabled={disabled || regenerating}
                    onClick={(event) => {
                        event.stopPropagation();
                        void onRegenerate?.(message);
                    }}
                />
            </Tooltip>
            <Popover trigger="click" placement="top" content={moreContent}>
                <Button
                    type="text"
                    size="small"
                    icon={<MoreOutlined />}
                    onClick={(event) => event.stopPropagation()}
                />
            </Popover>
            {hasCitations ? (
                <Button
                    className="chat-message__source-action"
                    type={activeCitation ? "primary" : "default"}
                    size="small"
                    icon={<FileTextOutlined />}
                    onClick={(event) => {
                        event.stopPropagation();
                        onSelectCitations();
                    }}
                >
                    来源 {citationCount}
                </Button>
            ) : null}
        </div>
    );
}

interface CitationGroupProps {
    citations: AskCitation[];
}

function FileAttachmentPopover({ attachment, onOpenPreview }: { attachment: SessionAttachment; onOpenPreview?: () => void }) {
    const detailParts = [
        attachment.page_count ? `${attachment.page_count} 页` : null,
        attachment.sheet_count ? `${attachment.sheet_count} 个表` : null,
        attachment.slide_count ? `${attachment.slide_count} 页幻灯片` : null,
        attachment.chunk_count ? `${attachment.chunk_count} 个片段` : null,
    ].filter(Boolean);
    return (
        <Space direction="vertical" size={6} className="chat-file-popover">
            <Typography.Text strong>{attachment.filename}</Typography.Text>
            <Tag color={fileAttachmentStatusColor(attachment)}>{fileAttachmentStatusLabel(attachment)}</Tag>
            {detailParts.length ? <Typography.Text type="secondary">{detailParts.join(" · ")}</Typography.Text> : null}
            {attachment.summary ? <Typography.Paragraph ellipsis={{ rows: 3 }}>{attachment.summary}</Typography.Paragraph> : null}
            {attachment.error_message ? <Typography.Text type="danger">{attachment.error_message}</Typography.Text> : null}
            {onOpenPreview ? (
                <Button size="small" icon={<FileTextOutlined />} onClick={onOpenPreview}>
                    查看文件
                </Button>
            ) : null}
        </Space>
    );
}

function CitationGroup({ citations, onOpenPreview }: CitationGroupProps & { onOpenPreview?: (target: FilePreviewTarget) => void }) {
    return (
        <div className="chat-citation-group">
            <List
                size="small"
                dataSource={citations}
                renderItem={(citation) => (
                    <List.Item key={citation.chunk_id}>
                        <div className="chat-citation-card">
                            <Space size={8} wrap>
                                <Typography.Text strong>{citation.title}</Typography.Text>
                                <Tag color={citationSourceColor(citation.source_type)}>{citationSourceLabel(citation.source_type)}</Tag>
                                <Tag>{citation.source}</Tag>
                                {citation.source_type === "private_upload" ? <Tag>{formatCitationLocator(citation)}</Tag> : null}
                                <Typography.Text type="secondary">{citation.chunk_id}</Typography.Text>
                            </Space>
                            <Typography.Paragraph className="chat-citation-card__snippet" ellipsis={{ rows: 3, expandable: "collapsible", symbol: "展开" }}>
                                {citation.snippet}
                            </Typography.Paragraph>
                            {citation.source_url?.startsWith("http") ? (
                                <Space size={12} wrap>
                                    <Typography.Link href={citation.source_url} target="_blank" rel="noreferrer">
                                        <LinkOutlined /> 查看来源
                                    </Typography.Link>
                                    {filePreviewTargetFromCitation(citation) ? (
                                        <Button size="small" icon={<FileTextOutlined />} onClick={() => onOpenPreview?.(filePreviewTargetFromCitation(citation)!)}>查看文件</Button>
                                    ) : null}
                                </Space>
                            ) : citation.source_type === "public_policy_demo" ? (
                                <Typography.Text type="secondary">该条依据来自内置演示样例，不代表真实官方政策。</Typography.Text>
                            ) : citation.source_type === "private_upload" ? (
                                <Space size={12} wrap>
                                    <Typography.Text type="secondary">该条依据来自当前用户已入库的个人上传文档。</Typography.Text>
                                    {filePreviewTargetFromCitation(citation) ? (
                                        <Button size="small" icon={<FileTextOutlined />} onClick={() => onOpenPreview?.(filePreviewTargetFromCitation(citation)!)}>查看文件</Button>
                                    ) : null}
                                </Space>
                            ) : (
                                <Space size={12} wrap>
                                    <Typography.Text type="secondary">该条依据来自仓库内脱敏知识条目。</Typography.Text>
                                    {filePreviewTargetFromCitation(citation) ? (
                                        <Button size="small" icon={<FileTextOutlined />} onClick={() => onOpenPreview?.(filePreviewTargetFromCitation(citation)!)}>查看文件</Button>
                                    ) : null}
                                </Space>
                            )}
                        </div>
                    </List.Item>
                )}
            />
        </div>
    );
}

function filePreviewTargetFromAttachment(attachment: SessionAttachment): FilePreviewTarget {
    if (attachment.knowledge_item_id && attachment.source_type !== "uploaded_file") {
        return { sourceType: "knowledge_item", sourceId: attachment.knowledge_item_id };
    }
    return { sourceType: "session_file", sourceId: attachment.file_id };
}

function filePreviewTargetFromCitation(citation: AskCitation): FilePreviewTarget | null {
    if (citation.file_id) {
        return { sourceType: "session_file", sourceId: citation.file_id };
    }
    if (citation.knowledge_item_id) {
        return { sourceType: "knowledge_item", sourceId: citation.knowledge_item_id };
    }
    return null;
}

function citationSourceLabel(sourceType: AskCitation["source_type"]) {
    if (sourceType === "public_policy") {
        return "公共政策";
    }
    if (sourceType === "public_policy_demo") {
        return "演示样例";
    }
    if (sourceType === "private_upload") {
        return "个人上传";
    }
    return "知识条目";
}

function citationSourceColor(sourceType: AskCitation["source_type"]) {
    if (sourceType === "public_policy") {
        return "blue";
    }
    if (sourceType === "public_policy_demo") {
        return "orange";
    }
    if (sourceType === "private_upload") {
        return "green";
    }
    return "magenta";
}

const statusColorMap = {
    ok: "green",
    provider_error: "red",
    invalid_input: "gold",
} as const;

const statusLabelMap = {
    ok: "成功",
    provider_error: "模型服务失败",
    invalid_input: "输入无效",
} as const;

const scopeLabelMap: Record<KnowledgeScope, string> = {
    public: "公共政策",
    private_sample: "知识条目",
    mixed: "混合",
};

const scopeColorMap: Record<KnowledgeScope, string> = {
    public: "blue",
    private_sample: "magenta",
    mixed: "gold",
};

const compactionStatusColorMap = {
    idle: "default",
    compacted: "processing",
    failed: "error",
} as const;

const compactionStatusLabelMap = {
    idle: "当前未压缩",
    compacted: "已自动压缩",
    failed: "压缩失败",
} as const;

const lifecycleTagMap = {
    pending: { color: "default", label: "等待开始" },
    connecting: { color: "processing", label: "正在连接" },
    thinking: { color: "processing", label: "思考中" },
    reconnecting: { color: "warning", label: "正在重连" },
    streaming: { color: "blue", label: "正在输出" },
    done: { color: "green", label: "已完成" },
    error: { color: "red", label: "生成失败" },
    failed: { color: "red", label: "连接失败" },
} as const;

const lifecycleStatusTextMap = {
    pending: "正在准备回答",
    connecting: "正在连接模型",
    thinking: "思考中",
    reconnecting: "正在重连",
    streaming: "正在输出",
    done: "已完成",
    error: "生成失败",
    failed: "连接失败",
} as const;

function getAttachedPrivateSampleIds(attachedFiles: SessionAttachment[]) {
    return attachedFiles
        .filter(
            (item) =>
                item.source_type === "private_sample" ||
                item.source_type === "private_sample_repo" ||
                item.source_type === "knowledge_item",
        )
        .map((item) => item.knowledge_item_id ?? item.file_id)
        .filter((value): value is string => Boolean(value));
}

function dedupeUploadedAttachments(attachedFiles: SessionAttachment[]) {
    const deduped = new Map<string, SessionAttachment>();
    for (const item of attachedFiles) {
        const existing = deduped.get(item.file_id);
        if (!existing || (!existing.knowledge_item_id && item.knowledge_item_id)) {
            deduped.set(item.file_id, item);
        }
    }
    return [...deduped.values()];
}

function keepAvailableUploadedFileSelection(
    currentFileIds: string[],
    attachedFiles: SessionAttachment[],
    dismissedFileIds?: Set<string>,
) {
    const availableUploadedFileIds = dedupeUploadedAttachments(attachedFiles.filter((item) => item.source_type === "uploaded_file"))
        .map((item) => item.file_id)
        .filter((fileId) => !dismissedFileIds?.has(fileId));
    const availableUploadedFileIdSet = new Set(availableUploadedFileIds);
    return currentFileIds.filter((fileId) => availableUploadedFileIdSet.has(fileId));
}

function attachCitedFilesToUserMessages(messages: ChatMessageView[], uploadedAttachments: SessionAttachment[]) {
    if (!messages.length || !uploadedAttachments.length) {
        return messages;
    }

    const attachmentsByFileId = new Map(uploadedAttachments.map((attachment) => [attachment.file_id, attachment]));
    const nextMessages = messages.map((message) => ({ ...message }));

    for (let index = 0; index < nextMessages.length; index += 1) {
        const message = nextMessages[index];
        if (message.role !== "assistant" || !message.citations.length) {
            continue;
        }
        const citedAttachments = dedupeUploadedAttachments(
            message.citations
                .filter((citation) => citation.source_type === "private_upload" && citation.file_id)
                .map((citation) => attachmentsByFileId.get(citation.file_id ?? ""))
                .filter((attachment): attachment is SessionAttachment => Boolean(attachment)),
        );
        if (!citedAttachments.length) {
            continue;
        }
        for (let userIndex = index - 1; userIndex >= 0; userIndex -= 1) {
            if (nextMessages[userIndex].role !== "user") {
                continue;
            }
            nextMessages[userIndex] = {
                ...nextMessages[userIndex],
                client_attachments: dedupeUploadedAttachments([
                    ...(nextMessages[userIndex].client_attachments ?? []),
                    ...citedAttachments,
                ]),
            };
            break;
        }
    }

    return nextMessages;
}

function isAttachmentReadyForAsk(attachment: SessionAttachment) {
    return attachment.parse_status === "parsed" && attachment.index_status === "indexed";
}

function getPendingUploadSignature(attachments: SessionAttachment[]) {
    const pendingUploads = attachments.filter((item) => ["uploaded", "pending", "queued", "running", "parsing"].includes(item.parse_status ?? ""));
    if (!pendingUploads.length) {
        return "";
    }
    return pendingUploads
        .map((item) => `${item.file_id}:${item.parse_status ?? ""}:${item.index_status ?? ""}:${item.chunk_count ?? 0}`)
        .sort()
        .join("|");
}

function fileAttachmentStatusLabel(attachment: SessionAttachment) {
    if (isAttachmentReadyForAsk(attachment)) {
        return "可提问";
    }
    if (attachment.parse_status === "parse_failed" || attachment.index_status === "index_failed") {
        return "解析失败";
    }
    if (["uploaded", "pending", "queued", "running", "parsing"].includes(attachment.parse_status ?? "")) {
        return "解析中";
    }
    return "待处理";
}

function fileAttachmentStatusColor(attachment: SessionAttachment) {
    if (isAttachmentReadyForAsk(attachment)) {
        return "green";
    }
    if (attachment.parse_status === "parse_failed" || attachment.index_status === "index_failed") {
        return "red";
    }
    return "processing";
}

function formatCitationLocator(citation: AskCitation) {
    const parts = [
        citation.page_number ? `p.${citation.page_number}` : null,
        citation.sheet_name ? `sheet ${citation.sheet_name}` : null,
        citation.slide_number ? `slide ${citation.slide_number}` : null,
        citation.section_title ?? null,
    ].filter(Boolean);
    return parts.length ? parts.join(" / ") : "文件片段";
}

function resolvePreferredCitationMessageId(detail: SessionDetail | null): string | null {
    if (!detail) {
        return null;
    }
    const reversed = [...detail.messages].reverse();
    const latestAssistantWithCitations = reversed.find((message) => message.role === "assistant" && message.citations.length > 0);
    return latestAssistantWithCitations?.message_id ?? null;
}

function groupCitationsBySource(citations: AskCitation[]) {
    return {
        public_policy: citations.filter((item) => item.source_type === "public_policy"),
        public_policy_demo: citations.filter((item) => item.source_type === "public_policy_demo"),
        private_sample: citations.filter((item) => item.source_type === "private_sample"),
        private_upload: citations.filter((item) => item.source_type === "private_upload"),
    };
}

function summarizeCitations(citations: AskCitation[]): AskSourceSummary {
    const groups = groupCitationsBySource(citations);
    const publicEvidenceCount = groups.public_policy.length + groups.public_policy_demo.length;
    return {
        knowledge_scope:
            publicEvidenceCount && (groups.private_sample.length || groups.private_upload.length)
                ? "mixed"
                : groups.private_sample.length || groups.private_upload.length
                    ? "private_sample"
                    : "public",
        public_policy_count: groups.public_policy.length,
        public_policy_demo_count: groups.public_policy_demo.length,
        private_sample_count: groups.private_sample.length,
        private_upload_count: groups.private_upload.length,
        total_citation_count: citations.length,
    };
}

function buildPanelSourceSummary(citations: AskCitation[], fallback?: AskSourceSummary | null): AskSourceSummary {
    if (citations.length > 0) {
        return summarizeCitations(citations);
    }
    return fallback ?? {
        knowledge_scope: "public",
        public_policy_count: 0,
        public_policy_demo_count: 0,
        private_sample_count: 0,
        private_upload_count: 0,
        total_citation_count: 0,
    };
}

function buildCitationCollapseItems(groups: ReturnType<typeof groupCitationsBySource>, onOpenPreview?: (target: FilePreviewTarget) => void) {
    return [
        groups.public_policy.length
            ? {
                key: "public_policy",
                label: (
                    <Space size={8} wrap>
                        <Typography.Text strong>政策依据</Typography.Text>
                        <Tag color="blue">{groups.public_policy.length}</Tag>
                    </Space>
                ),
                children: <CitationGroup citations={groups.public_policy} onOpenPreview={onOpenPreview} />,
            }
            : null,
        groups.public_policy_demo.length
            ? {
                key: "public_policy_demo",
                label: (
                    <Space size={8} wrap>
                        <Typography.Text strong>演示样例依据</Typography.Text>
                        <Tag color="orange">{groups.public_policy_demo.length}</Tag>
                    </Space>
                ),
                children: <CitationGroup citations={groups.public_policy_demo} onOpenPreview={onOpenPreview} />,
            }
            : null,
        groups.private_sample.length
            ? {
                key: "private_sample",
                label: (
                    <Space size={8} wrap>
                        <Typography.Text strong>共享知识依据</Typography.Text>
                        <Tag color="magenta">{groups.private_sample.length}</Tag>
                    </Space>
                ),
                children: <CitationGroup citations={groups.private_sample} onOpenPreview={onOpenPreview} />,
            }
            : null,
        groups.private_upload.length
            ? {
                key: "private_upload",
                label: (
                    <Space size={8} wrap>
                        <Typography.Text strong>个人上传依据</Typography.Text>
                        <Tag color="green">{groups.private_upload.length}</Tag>
                    </Space>
                ),
                children: <CitationGroup citations={groups.private_upload} onOpenPreview={onOpenPreview} />,
            }
            : null,
    ].filter(Boolean) as Array<{ key: string; label: any; children: any }>;
}

function buildContextSourceText(
    memoryState: SessionDetail["memory_state"],
    sourceSummary: AskSourceSummary,
    messageCount: number,
    contextSource?: StreamContextSource | null,
) {
    const parts: string[] = [];
    const recentMessageCount = contextSource?.recent_message_count ?? Math.min(6, Math.max(1, messageCount));
    const summaryPresent = contextSource?.summary_present ?? memoryState?.summary_present ?? false;
    const citationCount = contextSource?.citation_count ?? sourceSummary.total_citation_count;
    parts.push(`本轮使用最近 ${recentMessageCount} 轮消息`);

    if (summaryPresent) {
        parts.push("会话摘要");
    }

    if (citationCount > 0) {
        parts.push(`${citationCount} 条依据`);
    } else {
        parts.push("当前无额外依据");
    }

    if (summaryPresent && memoryState?.compacted_message_count) {
        parts.push(`已压缩 ${memoryState.compacted_message_count} 条更早消息`);
    }

    return parts.join(" + ");
}

function getContextUsagePercent(memoryState: SessionDetail["memory_state"]) {
    if (!memoryState || memoryState.context_budget_estimate <= 0) {
        return 0;
    }

    const percent = Math.round((memoryState.context_usage_estimate / memoryState.context_budget_estimate) * 100);
    return Math.max(0, Math.min(percent, 100));
}

function buildAssistantEvidenceSummary(sourceSummary: AskSourceSummary) {
    const parts: string[] = [];
    if (sourceSummary.public_policy_count > 0) {
        parts.push(`政策 ${sourceSummary.public_policy_count}`);
    }
    if ((sourceSummary.public_policy_demo_count ?? 0) > 0) {
        parts.push(`演示样例 ${sourceSummary.public_policy_demo_count ?? 0}`);
    }
    if (sourceSummary.private_sample_count > 0) {
        parts.push(`知识条目 ${sourceSummary.private_sample_count}`);
    }
    if ((sourceSummary.private_upload_count ?? 0) > 0) {
        parts.push(`个人上传 ${sourceSummary.private_upload_count ?? 0}`);
    }
    return parts.join(" · ");
}

function RagProofPanel({
    trace,
    knowledgeBases,
    selectedKbId,
    ragMode,
    citationCount,
    selectedChunks,
}: {
    trace: Record<string, unknown>;
    knowledgeBases: KnowledgeBase[];
    selectedKbId: string | null;
    ragMode: RagRetrievalMode;
    citationCount: number;
    selectedChunks: AskCitation[];
}) {
    const kbId = typeof trace.kb_id === "string" ? trace.kb_id : selectedKbId;
    const kbName = knowledgeBases.find((item) => item.kb_id === kbId)?.name ?? (kbId ? "未命名知识库" : "未指定知识库");
    const effectiveMode = typeof trace.retrieval_mode === "string" ? trace.retrieval_mode : ragMode;
    const provider = typeof trace.generation_provider === "string" ? trace.generation_provider : undefined;
    const model = typeof trace.generation_model === "string" ? trace.generation_model : undefined;
    const warnings = Array.isArray(trace.warnings) ? trace.warnings.filter((item): item is string => typeof item === "string") : [];
    const riskMessages = buildRagRiskMessages(trace, effectiveMode, citationCount);

    return (
        <Space direction="vertical" size={10} className="chat-rag-proof-panel" style={{ width: "100%" }}>
            <Space size={8} wrap className="chat-rag-trace-tags">
                <Tag color={kbId ? "blue" : "red"}>知识库：{kbName}{kbId ? ` · ${kbId}` : ""}</Tag>
                <Tag color="purple">检索模式：{ragModeLabel(effectiveMode)}</Tag>
                {provider ? <Tag color="green">Provider：{provider}</Tag> : null}
                {model ? <Tag>模型：{model}</Tag> : null}
                {buildRagTraceTags(trace).map((tag) => (
                    <Tag key={tag.key} color={tag.color}>{tag.label}</Tag>
                ))}
                <Tag color={citationCount > 0 ? "green" : "red"}>引用 {citationCount}</Tag>
            </Space>
            {riskMessages.length ? <Alert type="warning" showIcon message="RAG 证明存在风险" description={riskMessages.join("；")} /> : null}
            {warnings.length ? <Alert type="warning" showIcon message="RAG warnings" description={warnings.join("；")} /> : null}
            {selectedChunks.length ? (
                <Collapse
                    ghost
                    items={[
                        {
                            key: "selected-chunks",
                            label: `本轮引用片段 ${selectedChunks.length} 条`,
                            children: (
                                <List
                                    size="small"
                                    dataSource={selectedChunks.slice(0, 5)}
                                    renderItem={(citation) => (
                                        <List.Item>
                                            <Typography.Paragraph ellipsis={{ rows: 2, expandable: "collapsible", symbol: "展开" }}>
                                                <Typography.Text strong>{citation.title}</Typography.Text>
                                                <br />
                                                {citation.snippet}
                                            </Typography.Paragraph>
                                        </List.Item>
                                    )}
                                />
                            ),
                        },
                    ]}
                />
            ) : null}
        </Space>
    );
}

function buildRagRiskMessages(trace: Record<string, unknown>, mode: string, citationCount: number) {
    const denseCount = readTraceNumber(trace, "dense_count") ?? readTraceNumber(trace, "vector_count");
    const vectorRuntime = typeof trace.vector_runtime === "string" ? trace.vector_runtime : "";
    const rerankApplied = trace.rerank_applied === true;
    const messages: string[] = [];
    if (trace.degraded === true) {
        messages.push("当前 RAG 已降级");
    }
    if (vectorRuntime === "memory_dev") {
        messages.push("当前使用内存开发模式，不算正式验收");
    }
    if (denseCount === 0) {
        messages.push("向量命中为 0");
    }
    if (citationCount === 0) {
        messages.push("没有 citation");
    }
    if (mode === "hybrid_rerank" && !rerankApplied) {
        messages.push("选择了 hybrid+rerank，但重排序未执行");
    }
    return messages;
}

function ragModeLabel(value: string) {
    if (value === "dense") return "仅向量";
    if (value === "sparse") return "仅关键词";
    if (value === "hybrid") return "混合检索";
    if (value === "hybrid_rerank") return "混合检索 + 重排序";
    return value;
}

function buildRagTraceTags(trace?: Record<string, unknown> | null) {
    if (!trace) {
        return [];
    }
    const bm25Count = readTraceNumber(trace, "bm25_count") ?? readTraceNumber(trace, "sparse_count");
    const vectorCount = readTraceNumber(trace, "vector_count") ?? readTraceNumber(trace, "dense_count");
    const mergedCount = readTraceNumber(trace, "merged_count");
    const rerankApplied = trace.rerank_applied === true;
    const vectorStatus = typeof trace.vector_status === "string" ? trace.vector_status : (trace.degraded === true ? "degraded" : "");
    const vectorBackend = typeof trace.vector_backend === "string" ? trace.vector_backend : "vector";
    const fallbackReason = typeof trace.fallback_reason === "string" ? trace.fallback_reason : "";
    const hydeQuery = typeof trace.hyde_query === "string" ? trace.hyde_query : "";
    const degraded = trace.degraded === true;

    return [
        hydeQuery ? { key: "hyde", color: "purple", label: "HyDE 已生成" } : null,
        bm25Count !== null ? { key: "bm25", color: "blue", label: `Sparse/BM25 ${bm25Count}` } : null,
        vectorCount !== null ? { key: "vector", color: degraded ? "orange" : "geekblue", label: `${vectorBackend} ${vectorCount}` } : null,
        mergedCount !== null ? { key: "merged", color: "cyan", label: `融合 ${mergedCount}` } : null,
        { key: "rerank", color: rerankApplied ? "green" : "default", label: rerankApplied ? "Rerank 已应用" : "Rerank 跳过" },
        degraded ? { key: "degraded", color: "orange", label: `降级: ${vectorStatus || "vector unavailable"}` } : null,
        fallbackReason ? { key: "fallback", color: "orange", label: `fallback: ${fallbackReason}` } : null,
    ].filter(Boolean) as Array<{ key: string; color: string; label: string }>;
}

function readTraceNumber(trace: Record<string, unknown>, key: string) {
    const value = trace[key];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function extractGeneratedReports(message: ChatMessageView): GeneratedReportSummary[] {
    if (message.generated_reports?.length) {
        return message.generated_reports;
    }
    return extractGeneratedReportsFromTrace(message.retrieval_trace) ?? [];
}

function extractGeneratedReportsFromTrace(retrievalTrace?: Record<string, unknown> | null): GeneratedReportSummary[] | undefined {
    if (!retrievalTrace || typeof retrievalTrace !== "object") {
        return undefined;
    }
    const candidate = retrievalTrace.generated_reports;
    return Array.isArray(candidate) ? (candidate as GeneratedReportSummary[]) : undefined;
}

function dedupeGeneratedReportFiles<T extends GeneratedReportFile>(files: T[]): T[] {
    const seen = new Set<string>();
    const deduped: T[] = [];
    for (const file of files) {
        const key = file.file_id || file.download_url || file.filename;
        if (!key || seen.has(key)) {
            continue;
        }
        seen.add(key);
        deduped.push(file);
    }
    return deduped;
}

function formatBytes(value: number) {
    if (!Number.isFinite(value) || value <= 0) {
        return "";
    }
    if (value < 1024) {
        return `${value} B`;
    }
    if (value < 1024 * 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
    }
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function isRagRetrievalMode(value: string | null): value is RagRetrievalMode {
    return value === "dense" || value === "sparse" || value === "hybrid" || value === "hybrid_rerank";
}

function resolveMessageContent(message: ChatMessageView, isAssistant: boolean) {
    if (message.content) {
        return message.content;
    }
    if (!isAssistant) {
        return "";
    }
    if (message.client_state === "pending") {
        return "正在准备回答…";
    }
    if (message.client_state === "thinking") {
        return "正在结合上下文与依据组织回答…";
    }
    if (message.client_state === "streaming") {
        return "正在开始输出回答…";
    }
    if (message.client_state === "error") {
        return "当前问答服务暂不可用，请稍后重试。";
    }
    return "";
}

function renderMessageContent(message: ChatMessageView, isAssistant: boolean) {
    const content = resolveMessageContent(message, isAssistant);
    if (!content) {
        return null;
    }

    if (!isAssistant) {
        return <Typography.Paragraph>{content}</Typography.Paragraph>;
    }

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                table: ({ children }) => (
                    <div className="chat-markdown-table-scroll">
                        <table>{children}</table>
                    </div>
                ),
            }}
        >
            {normalizeAssistantMarkdown(content)}
        </ReactMarkdown>
    );
}

async function copyTextToClipboard(text: string, successMessage: string) {
    const normalized = text.trim();
    if (!normalized) {
        antdMessage.warning("没有可复制的内容。");
        return;
    }

    try {
        await writeClipboardText(normalized);
        antdMessage.success(successMessage);
    } catch (error) {
        console.error("[clipboard] write failed", error);
        antdMessage.error("复制失败，请手动选择内容。");
    }
}

async function writeClipboardText(text: string) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
        const copied = document.execCommand("copy");
        if (!copied) {
            throw new Error("document.execCommand('copy') returned false.");
        }
    } finally {
        document.body.removeChild(textarea);
    }
}

function buildMessageShareText(message: ChatMessageView, sessionTitle?: string | null) {
    const parts = [
        "CarbonRag 对话分享",
        sessionTitle ? `会话：${sessionTitle}` : null,
        `时间：${formatTimestamp(message.created_at)}`,
        "",
        message.content.trim(),
    ].filter((item): item is string => item !== null);
    return parts.join("\n");
}


function normalizeAskStreamMemoryState(memoryState: AskStreamMetadataEvent["memory_state"]): SessionDetail["memory_state"] {
    if (!memoryState || typeof memoryState !== "object") {
        return null;
    }
    if (
        typeof memoryState.context_usage_estimate !== "number" ||
        typeof memoryState.context_budget_estimate !== "number" ||
        typeof memoryState.summary_present !== "boolean" ||
        typeof memoryState.compacted_message_count !== "number"
    ) {
        return null;
    }
    if (
        memoryState.compaction_status !== "idle" &&
        memoryState.compaction_status !== "compacted" &&
        memoryState.compaction_status !== "failed"
    ) {
        return null;
    }
    return {
        context_usage_estimate: memoryState.context_usage_estimate,
        context_budget_estimate: memoryState.context_budget_estimate,
        summary_present: memoryState.summary_present,
        summary_updated_at: memoryState.summary_updated_at ?? null,
        compacted_message_count: memoryState.compacted_message_count,
        compaction_status: memoryState.compaction_status,
        summary_estimated_tokens: memoryState.summary_estimated_tokens ?? 0,
    };
}

function formatContextEstimate(value: number): string {
    if (value >= 1000) {
        return `${(value / 1000).toFixed(1)}K`;
    }
    return `${value}`;
}

function buildMemoryHint(memoryState: NonNullable<SessionDetail["memory_state"]>) {
    if (memoryState.compaction_status === "failed") {
        return "本轮旧对话压缩没有成功，系统会继续使用现有摘要和最近消息窗口回答。";
    }
    if (memoryState.summary_present) {
        return "已自动压缩旧对话，当前保留最近 6 轮完整消息，并用摘要承接更早的上下文。";
    }
    return "当前会话尚未触发自动压缩，系统会在上下文接近阈值时压缩较早对话。";
}

function toggleDocId(current: string[], target: string, checked: boolean) {
    if (checked) {
        return current.includes(target) ? current : [...current, target];
    }
    return current.filter((item) => item !== target);
}

function formatTimestamp(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("zh-CN", {
        hour12: false,
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function formatDurationSeconds(value: number) {
    if (!Number.isFinite(value) || value <= 0) {
        return "0s";
    }
    const seconds = Math.max(1, Math.round(value));
    if (seconds < 60) {
        return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

function resolvePreparationStatusText(state: AssistantLifecycleState | undefined) {
    if (state === "reconnecting") {
        return "重连中";
    }
    if (state === "connecting") {
        return "连接模型中";
    }
    return "准备回答";
}

function isAskResponse(value: unknown): value is AskResponse {
    if (!value || typeof value !== "object") {
        return false;
    }
    const candidate = value as Partial<AskResponse>;
    return candidate.mode === "ask" && typeof candidate.answer === "string" && typeof candidate.trace_id === "string" && Array.isArray(candidate.citations) && typeof candidate.source_summary === "object";
}

function createEmptySessionDetail(summary: SessionSummary, knowledgeScope: KnowledgeScope): SessionDetail {
    return {
        ...summary,
        messages: [],
        files: [],
        attached_files: [],
        knowledge_scope_last_used: knowledgeScope,
        source_summary: null,
        memory_state: null,
    };
}

function extractDeltaText(payload: AskStreamDeltaEvent) {
    return (payload.delta ?? payload.text ?? payload.content ?? "").trimStart();
}

function createDraftMessageId(role: "user" | "assistant") {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return `${role}-${crypto.randomUUID()}`;
    }
    return `${role}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function updateStreamDraft(current: ChatDraft | null, updater: (draft: ChatDraft) => ChatDraft) {
    if (!current) {
        return current;
    }
    return updater(current);
}

function mergeStreamMetadata(message: ChatMessageView, event: AskStreamMetadataEvent) {
    const nextRetrievalTrace = event.retrieval_trace ?? message.retrieval_trace ?? null;
    return {
        ...message,
        message_id: event.assistant_message_id ?? message.message_id,
        trace_id: event.trace_id ?? message.trace_id ?? null,
        citations: event.citations ?? message.citations,
        source_summary: event.source_summary ?? message.source_summary ?? null,
        retrieval_trace: nextRetrievalTrace,
        generated_reports: event.generated_reports ?? extractGeneratedReportsFromTrace(nextRetrievalTrace) ?? message.generated_reports ?? [],
        thinking_content:
            typeof event.thinking_content === "string"
                ? event.thinking_content
                : event.thinking_content === null
                    ? null
                    : message.thinking_content ?? null,
        content: typeof event.answer === "string" && event.answer ? event.answer : message.content,
        status: event.status ?? message.status ?? "ok",
    } as ChatMessageView;
}

function maybeShowReconnectToast(
    event: AskStreamStatusEvent,
    reconnectNoticeMode: "message_only" | "toast_and_message",
) {
    if (reconnectNoticeMode !== "toast_and_message") {
        return;
    }
    if (event.status === "reconnecting" && event.attempt && event.max_attempts) {
        antdMessage.info(`连接中断，正在重试（${event.attempt}/${event.max_attempts}）…`);
        return;
    }
    if (event.recovered && event.attempt) {
        antdMessage.success(`第 ${event.attempt} 次重连成功`);
    }
}

function mapLifecycleStatusToMessageState(
    status: AskStreamStatusEvent["status"],
    attempt?: number | null,
    maxAttempts?: number | null,
    recovered?: boolean | null,
) {
    const retrySuffix = attempt && maxAttempts ? `（${attempt}/${maxAttempts}）` : "";
    switch (status) {
        case "pending":
            return { status: "pending" as const, client_state: "pending" as const, status_note: "正在准备回答…" };
        case "connecting":
            return { status: "connecting" as const, client_state: "connecting" as const, status_note: "正在连接模型…" };
        case "thinking":
            return {
                status: "thinking" as const,
                client_state: "thinking" as const,
                status_note: recovered ? `第 ${attempt ?? 1} 次重连成功，正在思考…` : "思考中…",
            };
        case "reconnecting":
            return {
                status: "reconnecting" as const,
                client_state: "reconnecting" as const,
                status_note: `连接中断，正在重试${retrySuffix}…`,
            };
        case "streaming":
            return {
                status: "streaming" as const,
                client_state: "streaming" as const,
                status_note: recovered ? `第 ${attempt ?? 1} 次重连成功` : "已建立连接，正在输出…",
            };
        case "done":
            return { status: "done" as const, client_state: "done" as const, status_note: null };
        case "error":
            return { status: "provider_error" as const, client_state: "error" as const, status_note: "当前生成已中断。" };
        case "failed":
            return { status: "provider_error" as const, client_state: "failed" as const, status_note: "本次未能连接到模型，请稍后重试或检查模型设置" };
        default:
            return { status: null, client_state: "pending" as const, status_note: null };
    }
}

function isFinalAskStatus(status: SessionMessage["status"]): status is AskStatus {
    return status === "ok" || status === "provider_error" || status === "invalid_input";
}

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { detail?: unknown };
    return typeof candidate.detail === "string" ? candidate.detail : null;
}

function isAbortLikeError(value: unknown) {
    if (!value || typeof value !== "object") {
        return false;
    }
    const candidate = value as { name?: unknown; code?: unknown };
    return candidate.name === "AbortError" || candidate.code === "ERR_CANCELED";
}
