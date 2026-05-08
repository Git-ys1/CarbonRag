import {
    FileTextOutlined,
    LinkOutlined,
    MessageOutlined,
    MoreOutlined,
    PaperClipOutlined,
    SettingOutlined,
    TagsOutlined,
} from "@ant-design/icons";
import {
    Alert,
    Button,
    Card,
    Checkbox,
    Collapse,
    type CollapseProps,
    Drawer,
    Empty,
    Input,
    List,
    Popover,
    Segmented,
    Space,
    Spin,
    Tag,
    Tooltip,
    Typography,
    message as antdMessage,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useSettings } from "../../app/SettingsContext";
import { FeedbackButtonGroup } from "../../components/FeedbackButtonGroup";
import { SystemInfoPanel } from "../../components/SystemInfoPanel";
import { useWorkbenchShellContext } from "../../layouts/WorkbenchShellContext";
import { uploadSessionFile } from "../../services/files";
import { listAttachableKnowledgeItems, replaceAttachedKnowledgeItems } from "../../services/knowledge";
import {
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
    KnowledgeScope,
} from "../../types/ask";
import type { KnowledgeItem } from "../../types/knowledge";
import type { SessionAttachment, SessionDetail, SessionMessage, SessionSummary } from "../../types/session";

type AssistantLifecycleState = "pending" | "connecting" | "thinking" | "reconnecting" | "streaming" | "done" | "error" | "failed";

interface ChatMessageView extends SessionMessage {
    client_state?: AssistantLifecycleState;
    thinking_content?: string | null;
    status_note?: string | null;
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

export function AskPage() {
    const { user } = useAuth();
    const { settings, getActiveProviderOverride } = useSettings();
    const { activeSessionId, refreshSessions } = useWorkbenchShellContext();
    const [searchParams] = useSearchParams();
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const streamAbortRef = useRef<AbortController | null>(null);
    const messageStreamRef = useRef<HTMLDivElement | null>(null);
    const streamDraftRef = useRef<ChatDraft | null>(null);
    const streamMemoryStateRef = useRef<SessionDetail["memory_state"] | null>(null);
    const streamContextSourceRef = useRef<StreamContextSource | null>(null);
    const shouldAutoFollowMessageStreamRef = useRef(true);
    const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
    const [selectedCitationMessageId, setSelectedCitationMessageId] = useState<string | null>(null);
    const [streamDraft, setStreamDraft] = useState<ChatDraft | null>(null);
    const [streamMemoryState, setStreamMemoryState] = useState<SessionDetail["memory_state"] | null>(null);
    const [streamContextSource, setStreamContextSource] = useState<StreamContextSource | null>(null);
    const [question, setQuestion] = useState("");
    const [knowledgeScope, setKnowledgeScope] = useState<KnowledgeScope>("public");
    const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
    const [privateSampleDrawerOpen, setPrivateSampleDrawerOpen] = useState(false);
    const [draftAttachedDocIds, setDraftAttachedDocIds] = useState<string[]>([]);
    const [savingAttachedSamples, setSavingAttachedSamples] = useState(false);
    const [loadingPrivateSamples, setLoadingPrivateSamples] = useState(true);
    const [loadingSessionDetail, setLoadingSessionDetail] = useState(false);
    const [sidePanelOpen, setSidePanelOpen] = useState(false);
    const [sending, setSending] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [transportError, setTransportError] = useState<string | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const focusModeEnabled = searchParams.get("focus") !== "0";
    const isAdmin = user?.role === "admin";
    const sendShortcut = settings?.chat.send_shortcut ?? "enter";
    const reconnectNoticeMode = settings?.chat.reconnect_notice_mode ?? "message_only";
    const shouldShowContextDebug = settings?.chat.show_context_debug_by_default ?? false;

    const visibleMessages = useMemo<ChatMessageView[]>(() => {
        const baseMessages = (activeSession?.messages ?? []) as ChatMessageView[];
        if (!streamDraft) {
            return baseMessages;
        }
        return [...baseMessages, streamDraft.userMessage, streamDraft.assistantMessage];
    }, [activeSession?.messages, streamDraft]);

    const selectedCitationMessage = visibleMessages.find((message) => message.message_id === selectedCitationMessageId) ?? null;
    const citationGroups = groupCitationsBySource(selectedCitationMessage?.citations ?? []);
    const uploadedAttachments = activeSession?.attached_files.filter((item) => item.source_type === "uploaded_file") ?? [];
    const privateAttachments = activeSession?.attached_files.filter((item) => item.source_type !== "uploaded_file") ?? [];
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

    useEffect(() => {
        void loadKnowledgeCatalog();
    }, []);

    useEffect(() => {
        if (!activeSessionId) {
            setActiveSession(null);
            return;
        }
        streamAbortRef.current?.abort();
        streamAbortRef.current = null;
        replaceStreamDraft(null);
        replaceStreamMemoryState(null);
        replaceStreamContextSource(null);
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

    async function loadSessionDetail(sessionId: string) {
        setLoadingSessionDetail(true);
        setTransportError(null);

        try {
            const detail = await getSession(sessionId);
            setActiveSession(detail);
            setKnowledgeScope(detail.knowledge_scope_last_used ?? "public");
            setDraftAttachedDocIds(getAttachedPrivateSampleIds(detail.attached_files));
            setSelectedCitationMessageId(resolvePreferredCitationMessageId(detail));
        } catch {
            setActiveSession(null);
            setTransportError("当前无法读取选中会话，请稍后重试。");
        } finally {
            setLoadingSessionDetail(false);
        }
    }

    async function handleSaveAttachedSamples() {
        if (!activeSessionId) {
            return;
        }
        setSavingAttachedSamples(true);
        setTransportError(null);
        try {
            const detail = await replaceAttachedKnowledgeItems(activeSessionId, draftAttachedDocIds);
            setActiveSession(detail);
            setDraftAttachedDocIds(getAttachedPrivateSampleIds(detail.attached_files));
            await refreshSessions(activeSessionId);
            setPrivateSampleDrawerOpen(false);
        } catch (error) {
            setTransportError(extractDetailMessage(error) ?? "当前无法保存知识条目挂接状态。");
        } finally {
            setSavingAttachedSamples(false);
        }
    }

    async function handleSubmit() {
        const trimmed = question.trim();
        const providerOverride = getActiveProviderOverride();
        if (!activeSessionId) {
            setTransportError("当前没有可用会话，请先创建会话。");
            return;
        }
        if (!trimmed) {
            setTransportError("问题不能为空。");
            return;
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

        replaceStreamDraft({
            userMessage: {
                message_id: draftUserMessageId,
                role: "user",
                content: draftQuestion,
                created_at: now,
                citations: [],
            },
            assistantMessage: {
                message_id: draftAssistantMessageId,
                role: "assistant",
                content: "",
                created_at: now,
                status: "connecting",
                citations: [],
                client_state: "connecting",
                thinking_content: "",
                status_note: "正在连接模型…",
            },
        });
        setQuestion("");

        let committedLocally = false;
        try {
            const response = await submitSessionAskStreamRequest(
                activeSessionId,
                {
                    question: draftQuestion,
                    knowledge_scope: knowledgeScope,
                    top_k: 5,
                    attached_file_ids: knowledgeScope === "public" ? [] : draftAttachedDocIds,
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
                            status_note: "正在连接模型…",
                        },
                    }));
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
                                status_note: nextState.status_note,
                            },
                        };
                    });
                },
                onThinkingDelta: (event) => {
                    const delta = extractDeltaText(event);
                    if (!delta) {
                        return;
                    }
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: {
                            ...draft.assistantMessage,
                            status: "thinking",
                            client_state: "thinking",
                            status_note: "正在结合上下文组织回答…",
                            thinking_content: event.synthetic ? draft.assistantMessage.thinking_content ?? "" : `${draft.assistantMessage.thinking_content ?? ""}${delta}`,
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
                    updateStreamDraftState((draft) => ({
                        ...draft,
                        assistantMessage: mergeStreamMetadata(draft.assistantMessage, event),
                    }));
                },
                onDone: (event) => {
                    setSelectedCitationMessageId(event.assistant_message_id ?? draftAssistantMessageId);
                    replaceStreamMemoryState(normalizeAskStreamMemoryState(event.memory_state));
                    replaceStreamContextSource(event.context_source ?? null);
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

            commitDraftToActiveSession(activeSessionId, knowledgeScope);
            committedLocally = true;
            replaceStreamDraft(null);

            const sessionList = await refreshSessions(activeSessionId);
            syncActiveSessionSummaryFromList(sessionList ?? [], activeSessionId);
        } catch (error) {
            if (controller.signal.aborted || isAbortLikeError(error)) {
                return;
            }
            if (isAskResponse(error)) {
                if (error.status === "invalid_input") {
                    setTransportError(error.answer);
                } else {
                    setTransportError("模型服务当前响应失败，系统已把这次失败记录到当前会话。");
                    await refreshSessions(activeSessionId);
                    await loadSessionDetail(activeSessionId);
                }
            } else {
                setTransportError("当前问答服务暂不可达，请确认后端已启动且模型服务可用。");
            }
        } finally {
            setSending(false);
            streamAbortRef.current = null;
            if (!committedLocally) {
                replaceStreamDraft(null);
            }
        }
    }

    async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file || !activeSessionId) {
            return;
        }

        setUploading(true);
        setUploadError(null);
        try {
            await uploadSessionFile(activeSessionId, file);
            await refreshSessions(activeSessionId);
            await loadSessionDetail(activeSessionId);
        } catch (error) {
            setUploadError(extractDetailMessage(error) ?? "附件上传失败，请确认文件格式、大小和会话状态。");
        } finally {
            setUploading(false);
        }
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
            <Typography.Paragraph type="secondary" className="chat-composer-settings__hint">
                默认优先把输入框留在视觉中心。范围和知识条目挂接放到这里按需调整。
            </Typography.Paragraph>
        </div>
    );

    const showComposerMeta = uploadedAttachments.length > 0 || privateAttachments.length > 0 || Boolean(currentStreamTag) || uploading;
    const contextCircleBackground = `conic-gradient(#1677ff 0 ${contextUsagePercent}%, rgba(22, 119, 255, 0.14) ${contextUsagePercent}% 100%)`;

    return (
        <div className={`chat-workbench chat-workbench--single-column${focusModeEnabled ? " chat-workbench--focus-mode" : ""}`}>
            <div className="chat-workbench__main">
                {transportError ? <Alert type="warning" showIcon className="chat-workbench__alert" message="对话工作台提示" description={transportError} /> : null}
                {uploadError ? <Alert type="warning" showIcon className="chat-workbench__alert" message="附件上传提示" description={uploadError} /> : null}
                {knowledgeScope !== "public" && privateAttachments.length === 0 ? (
                    <Alert
                        type="info"
                        showIcon
                        className="chat-workbench__alert"
                        message="当前范围已切到知识条目 / 混合"
                        description="当前会话还没有挂接任何知识条目，因此该范围下可能检索为空。"
                    />
                ) : null}

                <Card
                    className="chat-workbench__stream-card"
                    title={(
                        <div className="chat-stream-card__title">
                            <Typography.Text strong className="chat-stream-card__title-text">
                                {activeSession?.title ?? "当前对话"}
                            </Typography.Text>
                            <Tag color={scopeColorMap[knowledgeScope]} className="chat-stream-card__scope-tag">
                                {scopeLabelMap[knowledgeScope]}
                            </Tag>
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
                    ) : activeSession ? (
                        <>
                            <div ref={messageStreamRef} className="chat-message-stream" onScroll={handleMessageStreamScroll}>
                                {visibleMessages.length === 0 ? (
                                    <div className="chat-message-stream__empty">
                                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前会话还没有消息，先问一个双碳问题试试。" />
                                    </div>
                                ) : (
                                    visibleMessages.map((message) => (
                                        <MessageBubble
                                            key={message.message_id}
                                            message={message}
                                            sessionId={activeSession.session_id}
                                            activeCitation={message.message_id === selectedCitationMessageId}
                                            expandThinkingByDefault={settings?.chat.expand_thinking_by_default ?? false}
                                            onSelectCitations={() => openCitationPanel(message.message_id)}
                                        />
                                    ))
                                )}
                            </div>
                        </>
                    ) : (
                        <Empty description="当前没有可展示的会话内容。" />
                    )}
                </Card>

                <div className="chat-composer-dock">
                    <div className="chat-composer-dock__main">
                        <Tooltip title="添加附件">
                            <Button className="chat-composer-dock__action" icon={<PaperClipOutlined />} onClick={() => fileInputRef.current?.click()} loading={uploading} />
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
                                {uploadedAttachments.length > 0 ? <Tag color="green">附件 {uploadedAttachments.length}</Tag> : null}
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
                        accept=".pdf,.doc,.docx,.txt,.md,.csv,.xls,.xlsx"
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
                    {selectedCitationMessage?.citations.length ? (
                        <Collapse
                            className="chat-citation-collapse"
                            ghost
                            defaultActiveKey={[]}
                            items={buildCitationCollapseItems(citationGroups)}
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
        </div>
    );
}

interface MessageBubbleProps {
    message: ChatMessageView;
    sessionId: string;
    activeCitation: boolean;
    expandThinkingByDefault: boolean;
    onSelectCitations: () => void;
}

function MessageBubble({ message, sessionId, activeCitation, expandThinkingByDefault, onSelectCitations }: MessageBubbleProps) {
    const isAssistant = message.role === "assistant";
    const isSystem = message.role === "system";
    const hasCitations = isAssistant && message.citations.length > 0;
    const messageSourceSummary = summarizeCitations(message.citations);
    const lifecycleTag = message.client_state ? lifecycleTagMap[message.client_state] : null;
    const finalStatusTag = isAssistant && isFinalAskStatus(message.status) ? statusColorMap[message.status] : null;
    const finalStatusLabel = isAssistant && isFinalAskStatus(message.status) ? statusLabelMap[message.status] : null;
    const hasRealThinkingContent = Boolean(message.thinking_content?.trim());
    const shouldShowThinking = isAssistant && (message.client_state === "pending" || message.client_state === "thinking" || hasRealThinkingContent);
    const shouldShowDetails = Boolean(message.trace_id) || Boolean(message.trace_id && (!message.client_state || message.client_state === "done" || message.client_state === "error"));
    const liveStateText = message.client_state ? lifecycleStatusTextMap[message.client_state] : null;
    const [thinkingExpanded, setThinkingExpanded] = useState(
        expandThinkingByDefault || message.client_state === "pending" || message.client_state === "thinking",
    );
    const previousClientStateRef = useRef<AssistantLifecycleState | undefined>(message.client_state);

    useEffect(() => {
        const previousState = previousClientStateRef.current;
        const currentState = message.client_state;

        if (currentState === "pending" || currentState === "thinking") {
            setThinkingExpanded(true);
        } else if (
            hasRealThinkingContent &&
            (currentState === "done" || currentState === "error") &&
            previousState !== currentState
        ) {
            setThinkingExpanded(false);
        } else if (!hasRealThinkingContent) {
            setThinkingExpanded(false);
        }

        previousClientStateRef.current = currentState;
    }, [expandThinkingByDefault, hasRealThinkingContent, message.client_state, message.message_id]);

    const thinkingCollapseItems: CollapseProps["items"] = shouldShowThinking
        ? [
            {
                key: "thinking",
                label: (
                    <Space size={8} wrap className="chat-message__thinking-label">
                        <span className="chat-thinking-pulse" aria-hidden="true" />
                        <Typography.Text strong>
                            {message.client_state === "pending" || message.client_state === "thinking" ? "思考中" : "思考过程"}
                        </Typography.Text>
                        {message.client_state ? <Tag color={lifecycleTag?.color ?? "processing"}>{lifecycleTag?.label ?? "生成中"}</Tag> : null}
                    </Space>
                ),
                children: (
                    <Typography.Paragraph className="chat-message__thinking-content">
                        {message.thinking_content || "模型正在组织上下文与回答，请稍候。"}
                    </Typography.Paragraph>
                ),
            },
        ]
        : [];

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
                    <Space size={8} wrap className="chat-message__header">
                        <Typography.Text className={isAssistant ? "chat-message__speaker chat-message__speaker--assistant" : isSystem ? "chat-message__speaker chat-message__speaker--system" : "chat-message__speaker chat-message__speaker--user"}>
                            {isAssistant ? "CarbonRag" : isSystem ? "系统消息" : "我"}
                        </Typography.Text>
                        {message.client_state && ["pending", "connecting", "thinking", "reconnecting", "streaming"].includes(message.client_state) ? (
                            <span className={`chat-live-state chat-live-state--${message.client_state}`}>
                                <span className="chat-live-state__dot" aria-hidden="true" />
                                <span>{liveStateText}</span>
                            </span>
                        ) : lifecycleTag ? (
                            <Tag color={lifecycleTag.color}>{lifecycleTag.label}</Tag>
                        ) : null}
                        {message.status_note ? (
                            <Typography.Text type="secondary">{message.status_note}</Typography.Text>
                        ) : null}
                        {finalStatusTag && finalStatusLabel ? <Tag color={finalStatusTag}>{finalStatusLabel}</Tag> : null}
                        <Typography.Text type="secondary">{formatTimestamp(message.created_at)}</Typography.Text>
                    </Space>
                    {isAssistant && shouldShowThinking ? (
                        <Collapse
                            ghost
                            className="chat-message__thinking"
                            activeKey={thinkingExpanded ? ["thinking"] : []}
                            onChange={(keys) => setThinkingExpanded(Array.isArray(keys) ? keys.includes("thinking") : keys === "thinking")}
                            items={thinkingCollapseItems}
                        />
                    ) : null}
                    <div className={isAssistant ? "chat-message__content chat-message__content--assistant" : "chat-message__content"}>
                        {renderMessageContent(message, isAssistant)}
                    </div>
                    {isAssistant ? (
                        <div className="chat-message__meta">
                            <Space size={12} wrap>
                                {hasCitations ? (
                                    <>
                                        <Typography.Text type="secondary" className="chat-message__evidence-summary">
                                            {buildAssistantEvidenceSummary(messageSourceSummary)}
                                        </Typography.Text>
                                        <Button type={activeCitation ? "primary" : "default"} size="small" icon={<FileTextOutlined />} onClick={onSelectCitations}>
                                            查看依据 {message.citations.length}
                                        </Button>
                                    </>
                                ) : null}
                            </Space>
                            {shouldShowDetails ? (
                                <Collapse
                                    ghost
                                    className="chat-message__details"
                                    defaultActiveKey={[]}
                                    items={[
                                        {
                                            key: "details",
                                            label: "查看详细信息",
                                            children: (
                                                <Space direction="vertical" size={10} style={{ width: "100%" }}>
                                                    {message.trace_id ? (
                                                        <Typography.Text type="secondary">
                                                            追踪号：<Typography.Text code>{message.trace_id}</Typography.Text>
                                                        </Typography.Text>
                                                    ) : null}
                                                    {message.trace_id && (!message.client_state || message.client_state === "done" || message.client_state === "error") ? (
                                                        <FeedbackButtonGroup
                                                            targetType="ask"
                                                            traceId={message.trace_id}
                                                            sessionId={sessionId}
                                                            size="small"
                                                        />
                                                    ) : null}
                                                </Space>
                                            ),
                                        },
                                    ]}
                                />
                            ) : null}
                        </div>
                    ) : null}
                </Space>
            </Card>
        </div>
    );
}

interface CitationGroupProps {
    citations: AskCitation[];
}

function CitationGroup({ citations }: CitationGroupProps) {
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
                                <Typography.Text type="secondary">{citation.chunk_id}</Typography.Text>
                            </Space>
                            <Typography.Paragraph className="chat-citation-card__snippet" ellipsis={{ rows: 3, expandable: "collapsible", symbol: "展开" }}>
                                {citation.snippet}
                            </Typography.Paragraph>
                            {citation.source_url?.startsWith("http") ? (
                                <Typography.Link href={citation.source_url} target="_blank" rel="noreferrer">
                                    <LinkOutlined /> 查看来源
                                </Typography.Link>
                            ) : citation.source_type === "public_policy_demo" ? (
                                <Typography.Text type="secondary">该条依据来自内置演示样例，不代表真实官方政策。</Typography.Text>
                            ) : citation.source_type === "private_upload" ? (
                                <Typography.Text type="secondary">该条依据来自当前用户已入库的个人上传文档。</Typography.Text>
                            ) : (
                                <Typography.Text type="secondary">该条依据来自仓库内脱敏知识条目。</Typography.Text>
                            )}
                        </div>
                    </List.Item>
                )}
            />
        </div>
    );
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
    pending: "正在建立回答位",
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

function buildCitationCollapseItems(groups: ReturnType<typeof groupCitationsBySource>) {
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
                children: <CitationGroup citations={groups.public_policy} />,
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
                children: <CitationGroup citations={groups.public_policy_demo} />,
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
                children: <CitationGroup citations={groups.private_sample} />,
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
                children: <CitationGroup citations={groups.private_upload} />,
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

function resolveMessageContent(message: ChatMessageView, isAssistant: boolean) {
    if (message.content) {
        return message.content;
    }
    if (!isAssistant) {
        return "";
    }
    if (message.client_state === "pending") {
        return "正在为这条问题创建回答位…";
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

    return <ReactMarkdown>{content}</ReactMarkdown>;
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

function isAskResponse(value: unknown): value is AskResponse {
    if (!value || typeof value !== "object") {
        return false;
    }
    const candidate = value as Partial<AskResponse>;
    return candidate.mode === "ask" && typeof candidate.answer === "string" && typeof candidate.trace_id === "string" && Array.isArray(candidate.citations) && typeof candidate.source_summary === "object";
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
    return {
        ...message,
        message_id: event.assistant_message_id ?? message.message_id,
        trace_id: event.trace_id ?? message.trace_id ?? null,
        citations: event.citations ?? message.citations,
        source_summary: event.source_summary ?? message.source_summary ?? null,
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
            return { status: "pending" as const, client_state: "pending" as const, status_note: "正在准备回答位…" };
        case "connecting":
            return { status: "connecting" as const, client_state: "connecting" as const, status_note: "正在连接模型…" };
        case "thinking":
            return {
                status: "thinking" as const,
                client_state: "thinking" as const,
                status_note: recovered ? `第 ${attempt ?? 1} 次重连成功` : "正在组织上下文与回答…",
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
