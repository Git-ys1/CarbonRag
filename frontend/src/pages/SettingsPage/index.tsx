import { CloudServerOutlined, DeleteOutlined, FolderOpenOutlined, PlusOutlined, SaveOutlined, UploadOutlined } from "@ant-design/icons";
import {
    Alert,
    App as AntdApp,
    AutoComplete,
    Avatar,
    Button,
    Card,
    Checkbox,
    Empty,
    Input,
    List,
    Modal,
    Segmented,
    Select,
    Space,
    Spin,
    Switch,
    Tabs,
    Tag,
    Typography,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useSettings } from "../../app/SettingsContext";
import { useTheme } from "../../app/ThemeContext";
import { useFeedback } from "../../hooks/useFeedback";
import { useWorkbenchShellContext } from "../../layouts/WorkbenchShellContext";
import { discoverProviderModels, testProviderConnection } from "../../services/settings";
import { bulkDeleteSessions } from "../../services/sessions";
import type {
    AppearanceSettings,
    ChatPreferenceSettings,
    DataPrivacySettings,
    ProviderProfile,
    ProviderType,
} from "../../types/settings";
import type { SessionSummary } from "../../types/session";

type ProviderDraft = {
    profileId?: string;
    providerType: ProviderType;
    displayName: string;
    baseUrl: string;
    apiKey: string;
    modelName: string;
    models: string[];
    configJson: Record<string, unknown>;
};

const providerTypeOptions = [
    { label: "默认云端", value: "carbonrag_cloud" },
    { label: "OpenAI 兼容", value: "openai_compatible" },
    { label: "Ollama", value: "ollama" },
    { label: "OpenAI", value: "openai" },
    { label: "Anthropic", value: "anthropic" },
    { label: "Gemini", value: "gemini" },
    { label: "DeepSeek", value: "deepseek" },
] as const;

const BUILTIN_PROVIDER_REF = "builtin:carbonrag-cloud";

function buildBlankProviderDraft(): ProviderDraft {
    return {
        providerType: "openai_compatible",
        displayName: "我的账号模型",
        baseUrl: "",
        apiKey: "",
        modelName: "",
        models: [],
        configJson: {},
    };
}

function buildOllamaDeepSeekDraft(): ProviderDraft {
    return {
        providerType: "ollama",
        displayName: "本地 DeepSeek-R1 8B",
        baseUrl: "http://localhost:11434",
        apiKey: "",
        modelName: "deepseek-r1:8b",
        models: ["deepseek-r1:8b"],
        configJson: {
            timeout_seconds: 180,
            max_retries: 1,
            temperature: 0.2,
            num_ctx: 8192,
            keep_alive: "10m",
            think: true,
        },
    };
}

export function SettingsPage() {
    const { modal, message: messageApi } = AntdApp.useApp();
    const navigate = useNavigate();
    const { user, updateProfile, deleteAccount } = useAuth();
    const feedback = useFeedback();
    const {
        sessions: shellSessions,
        activeSessionId,
        refreshSessions,
        selectSession,
    } = useWorkbenchShellContext();
    const { themeMode, themePreset, allPresets, setThemeMode, setThemePreset } = useTheme();
    const {
        settings,
        providerList,
        loading,
        saveSettings,
        createAccountProviderProfile,
        updateAccountProviderProfile,
        deleteAccountProviderProfile,
    } = useSettings();
    const [transportError, setTransportError] = useState<string | null>(null);
    const [providerDraft, setProviderDraft] = useState<ProviderDraft>(() => buildBlankProviderDraft());
    const [testingProvider, setTestingProvider] = useState(false);
    const [savingProvider, setSavingProvider] = useState(false);
    const [profileNameDraft, setProfileNameDraft] = useState("");
    const [profileAvatarDraft, setProfileAvatarDraft] = useState<string | null>(null);
    const [profileSaving, setProfileSaving] = useState(false);
    const [sessionList, setSessionList] = useState<SessionSummary[]>([]);
    const [loadingSessionList, setLoadingSessionList] = useState(false);
    const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);
    const [deletingSessions, setDeletingSessions] = useState(false);
    const [deleteAccountModalOpen, setDeleteAccountModalOpen] = useState(false);
    const [deleteAccountPassword, setDeleteAccountPassword] = useState("");
    const [deletingAccount, setDeletingAccount] = useState(false);
    const avatarInputRef = useRef<HTMLInputElement | null>(null);

    const quickThemePresets = useMemo(() => allPresets.slice(0, 4), [allPresets]);
    const extendedThemePresets = useMemo(() => allPresets.slice(4), [allPresets]);

    useEffect(() => {
        if (!transportError) {
            return;
        }
        feedback.error({
            title: "通用设置提示",
            description: transportError,
            source: "SettingsPage",
            key: `settings:${transportError}`,
        });
    }, [feedback, transportError]);

    useEffect(() => {
        if (!settings) {
            return;
        }
        setThemeMode(settings.appearance.theme_mode);
        setThemePreset(settings.appearance.theme_preset);
    }, [settings?.appearance.theme_mode, settings?.appearance.theme_preset]);

    useEffect(() => {
        if (!user) {
            return;
        }
        setProfileNameDraft(user.display_name || user.username);
        setProfileAvatarDraft(user.avatar_url ?? null);
    }, [user?.user_id, user?.display_name, user?.avatar_url, user?.username]);

    useEffect(() => {
        void loadSessionListForSettings();
    }, []);

    useEffect(() => {
        setSessionList(shellSessions);
        setSelectedSessionIds((current) =>
            current.filter((sessionId) => shellSessions.some((session) => session.session_id === sessionId)),
        );
    }, [shellSessions]);

    async function handleSaveAppearance() {
        await handleSaveAppearanceDraft({
            ...settings!.appearance,
            theme_mode: themeMode,
            theme_preset: themePreset,
        }, true);
    }

    async function handleSaveAppearanceDraft(nextAppearance: AppearanceSettings, showSuccess = false) {
        try {
            setTransportError(null);
            await saveSettings({
                appearance: nextAppearance,
            });
            if (showSuccess) {
                messageApi.success("外观设置已保存。");
            }
        } catch {
            setTransportError("当前无法保存外观设置。");
        }
    }

    function handleThemeModeChange(nextMode: typeof themeMode) {
        setThemeMode(nextMode);
        if (!settings) {
            return;
        }
        void handleSaveAppearanceDraft({
            ...settings.appearance,
            theme_mode: nextMode,
            theme_preset: themePreset,
        });
    }

    function handleThemePresetChange(nextPreset: typeof themePreset) {
        setThemePreset(nextPreset);
        if (!settings) {
            return;
        }
        void handleSaveAppearanceDraft({
            ...settings.appearance,
            theme_mode: themeMode,
            theme_preset: nextPreset,
        });
    }

    async function handleSaveChatSettings(partial: Partial<ChatPreferenceSettings>) {
        try {
            setTransportError(null);
            await saveSettings({
                chat: {
                    ...settings!.chat,
                    ...partial,
                },
            });
        } catch {
            setTransportError("当前无法保存聊天偏好。");
        }
    }

    async function handleSaveDataPrivacy(partial: Partial<DataPrivacySettings>) {
        try {
            setTransportError(null);
            await saveSettings({
                data_privacy: {
                    ...settings!.data_privacy,
                    ...partial,
                },
            });
        } catch {
            setTransportError("当前无法保存数据与隐私设置。");
        }
    }

    async function handleSetActiveProvider(providerRef: string) {
        if (providerRef.startsWith("local:")) {
            setTransportError("本地 Provider 已停用，请保存为账号 Provider 后再启用。");
            return;
        }
        try {
            setTransportError(null);
            await saveSettings({ active_provider_ref: providerRef });
            messageApi.success("当前模型提供方已切换。");
        } catch {
            setTransportError("当前无法切换模型提供方。");
        }
    }

    function handleAvatarFileChange(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file) {
            return;
        }
        if (!file.type.startsWith("image/")) {
            messageApi.warning("请选择图片文件作为头像。");
            return;
        }
        if (file.size > 180_000) {
            messageApi.warning("头像图片请控制在 180KB 以内。");
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            setProfileAvatarDraft(typeof reader.result === "string" ? reader.result : null);
        };
        reader.readAsDataURL(file);
    }

    async function handleSaveProfile() {
        if (!user) {
            return;
        }
        const displayName = profileNameDraft.trim();
        if (!displayName) {
            messageApi.warning("名称不能为空。");
            return;
        }
        setProfileSaving(true);
        try {
            await updateProfile({
                display_name: displayName,
                avatar_url: profileAvatarDraft,
            });
            messageApi.success("个人资料已更新。");
        } catch (error) {
            messageApi.warning(extractDetailMessage(error) ?? "名称可能已重复，请换一个名称。");
        } finally {
            setProfileSaving(false);
        }
    }

    async function loadSessionListForSettings() {
        setLoadingSessionList(true);
        try {
            const sessions = await refreshSessions(activeSessionId);
            setSessionList(sessions);
            setSelectedSessionIds((current) =>
                current.filter((sessionId) => sessions.some((session) => session.session_id === sessionId)),
            );
        } catch {
            setTransportError("当前无法读取会话列表。");
        } finally {
            setLoadingSessionList(false);
        }
    }

    function toggleSessionSelection(sessionId: string, checked: boolean) {
        setSelectedSessionIds((current) => {
            if (checked) {
                return current.includes(sessionId) ? current : [...current, sessionId];
            }
            return current.filter((item) => item !== sessionId);
        });
    }

    function handleSelectAllSessions() {
        setSelectedSessionIds(sessionList.map((session) => session.session_id));
    }

    async function executeSessionDeletion(targetSessionIds: string[]) {
        if (!targetSessionIds.length) {
            return;
        }
        setDeletingSessions(true);
        try {
            const result = await bulkDeleteSessions(targetSessionIds);
            const deletedSessionIdSet = new Set(result.deleted_session_ids);
            if (deletedSessionIdSet.size) {
                setSessionList((current) => current.filter((session) => !deletedSessionIdSet.has(session.session_id)));
            }
            setSelectedSessionIds((current) =>
                current.filter((sessionId) => !deletedSessionIdSet.has(sessionId)),
            );
            const nextPreferredSessionId = deletedSessionIdSet.has(activeSessionId ?? "") ? null : activeSessionId;
            const sessions = await refreshSessions(nextPreferredSessionId);
            setSessionList(sessions);
            if (result.deleted_count > 0) {
                messageApi.success(`已删除 ${result.deleted_count} 个会话。`);
            }
            if (result.missing_session_ids.length) {
                messageApi.warning("部分会话已不存在，列表已同步刷新。");
            }
        } catch {
            setTransportError("会话删除失败，请刷新后重试。");
        } finally {
            setDeletingSessions(false);
        }
    }

    function handleDeleteSelectedSessions() {
        const targetSelection = [...selectedSessionIds];
        if (!targetSelection.length) {
            messageApi.info("请先选择要删除的会话。");
            return;
        }
        modal.confirm({
            title: "确认删除选中的会话？",
            content: `将删除 ${targetSelection.length} 个会话。该操作不可撤销。`,
            okText: "删除",
            okButtonProps: { danger: true },
            cancelText: "取消",
            async onOk() {
                await executeSessionDeletion(targetSelection);
            },
        });
    }

    function handleDeleteSingleSession(session: SessionSummary) {
        modal.confirm({
            title: "确认删除该会话？",
            content: `将删除“${session.title || "未命名会话"}”。该操作不可撤销。`,
            okText: "删除",
            okButtonProps: { danger: true },
            cancelText: "取消",
            async onOk() {
                await executeSessionDeletion([session.session_id]);
            },
        });
    }

    function handleOpenManagedSession(sessionId: string) {
        selectSession(sessionId);
    }

    async function handleDeleteOwnAccount() {
        if (!deleteAccountPassword.trim()) {
            messageApi.warning("请输入当前账号密码。");
            return;
        }
        setDeletingAccount(true);
        try {
            await deleteAccount({ current_password: deleteAccountPassword });
            messageApi.success("账号已注销。");
        } catch (error) {
            messageApi.warning(extractDetailMessage(error) ?? "账号注销失败，请确认当前密码。");
        } finally {
            setDeletingAccount(false);
        }
    }

    async function handleDiscoverModels() {
        setTestingProvider(true);
        try {
            const result = await discoverProviderModels({
                provider_type: providerDraft.providerType,
                base_url: providerDraft.baseUrl || undefined,
                api_key: providerDraft.apiKey || undefined,
                model_name: providerDraft.modelName || undefined,
                config_json: providerDraft.configJson,
            });
            setProviderDraft((current) => ({
                ...current,
                baseUrl: result.normalized_base_url ?? current.baseUrl,
                models: result.models,
                modelName: current.modelName || result.models[0] || "",
            }));
            messageApi.success("模型列表已刷新。");
        } catch {
            setTransportError("当前无法发现模型列表，请检查提供方配置。");
        } finally {
            setTestingProvider(false);
        }
    }

    async function handleTestProvider() {
        setTestingProvider(true);
        try {
            const result = await testProviderConnection({
                provider_type: providerDraft.providerType,
                base_url: providerDraft.baseUrl || undefined,
                api_key: providerDraft.apiKey || undefined,
                model_name: providerDraft.modelName || undefined,
                config_json: providerDraft.configJson,
            });
            if (result.ok) {
                messageApi.success(result.message);
                if (result.discovered_models.length) {
                    setProviderDraft((current) => ({
                        ...current,
                        models: result.discovered_models,
                        modelName: current.modelName || result.discovered_models[0] || "",
                    }));
                }
            } else {
                setTransportError(result.message);
            }
        } catch {
            setTransportError("当前无法测试 provider 连接。");
        } finally {
            setTestingProvider(false);
        }
    }

    async function handleSaveProvider() {
        setSavingProvider(true);
        try {
            setTransportError(null);
            const payload = {
                provider_type: providerDraft.providerType,
                display_name: providerDraft.displayName,
                base_url: providerDraft.baseUrl || undefined,
                api_key: providerDraft.apiKey || undefined,
                model_name: providerDraft.modelName || undefined,
                config_json: providerDraft.configJson,
                storage_mode: "account" as const,
            };
            let profileId = providerDraft.profileId;
            if (profileId) {
                await updateAccountProviderProfile(profileId, payload);
            } else {
                const created = await createAccountProviderProfile(payload);
                profileId = created.profile_id;
            }
            await handleSetActiveProvider(`account:${profileId}`);
            setProviderDraft(buildBlankProviderDraft());
            messageApi.success("Provider 配置已保存。");
        } catch {
            setTransportError("当前无法保存 provider 配置。");
        } finally {
            setSavingProvider(false);
        }
    }

    function editAccountProfile(profile: ProviderProfile) {
        setProviderDraft({
            profileId: profile.profile_id,
            providerType: profile.provider_type,
            displayName: profile.display_name,
            baseUrl: profile.base_url ?? "",
            apiKey: "",
            modelName: profile.model_name ?? "",
            models: [],
            configJson: profile.config_json ?? {},
        });
    }

    if (loading || !settings || !providerList || !user) {
        return (
            <div className="settings-console settings-console--loading">
                <Spin />
            </div>
        );
    }

    const appearanceTab = (
        <div className="settings-section-grid">
            <Card className="settings-section-card" title="主题">
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                    <div className="settings-field">
                        <Typography.Text strong>主题模式</Typography.Text>
                        <Segmented
                            block
                            value={themeMode}
                            options={[
                                { label: "浅色", value: "light" },
                                { label: "暗色", value: "dark" },
                                { label: "跟随系统", value: "system" },
                            ]}
                            onChange={(value) => handleThemeModeChange(value as typeof themeMode)}
                        />
                    </div>
                    <div className="settings-field">
                        <Typography.Text strong>快速主题</Typography.Text>
                        <div className="settings-theme-grid">
                            {quickThemePresets.map((preset) => (
                                <button
                                    key={preset.id}
                                    type="button"
                                    className={preset.id === themePreset ? "theme-preset-card theme-preset-card--active" : "theme-preset-card"}
                                    onClick={() => handleThemePresetChange(preset.id)}
                                >
                                    <span className="theme-preset-card__swatches">
                                        {preset.preview.map((color, index) => (
                                            <span key={`${preset.id}-${index}`} className="theme-preset-card__swatch" style={{ background: color }} />
                                        ))}
                                    </span>
                                    <span className="theme-preset-card__copy">
                                        <Typography.Text strong>{preset.label}</Typography.Text>
                                        <Typography.Text type="secondary">{preset.description}</Typography.Text>
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="settings-field">
                        <Typography.Text strong>更多主题</Typography.Text>
                        <div className="settings-theme-grid settings-theme-grid--extended">
                            {extendedThemePresets.map((preset) => (
                                <button
                                    key={preset.id}
                                    type="button"
                                    className={preset.id === themePreset ? "theme-preset-card theme-preset-card--active" : "theme-preset-card"}
                                    onClick={() => handleThemePresetChange(preset.id)}
                                >
                                    <span className="theme-preset-card__swatches">
                                        {preset.preview.map((color, index) => (
                                            <span key={`${preset.id}-${index}`} className="theme-preset-card__swatch" style={{ background: color }} />
                                        ))}
                                    </span>
                                    <span className="theme-preset-card__copy">
                                        <Typography.Text strong>{preset.label}</Typography.Text>
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                    <Button type="primary" icon={<SaveOutlined />} onClick={() => void handleSaveAppearance()}>
                        保存外观设置
                    </Button>
                </Space>
            </Card>

            <Card className="settings-section-card" title="界面偏好">
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                    <div className="settings-field">
                        <Typography.Text strong>气泡密度</Typography.Text>
                        <Segmented
                            block
                            value={settings.appearance.bubble_density}
                            options={[
                                { label: "舒适", value: "comfortable" },
                                { label: "紧凑", value: "compact" },
                            ]}
                            onChange={(value) => void saveSettings({
                                appearance: {
                                    ...settings.appearance,
                                    bubble_density: value as "comfortable" | "compact",
                                },
                            })}
                        />
                    </div>
                    <div className="settings-field">
                        <Typography.Text strong>字体大小</Typography.Text>
                        <Segmented
                            block
                            value={settings.appearance.font_size}
                            options={[
                                { label: "默认", value: "default" },
                                { label: "大号", value: "large" },
                            ]}
                            onChange={(value) => void saveSettings({
                                appearance: {
                                    ...settings.appearance,
                                    font_size: value as "default" | "large",
                                },
                            })}
                        />
                    </div>
                    <div className="settings-field">
                        <Typography.Text strong>侧栏默认状态</Typography.Text>
                        <Segmented
                            block
                            value={settings.appearance.sidebar_default}
                            options={[
                                { label: "默认展开", value: "expanded" },
                                { label: "默认收起", value: "collapsed" },
                            ]}
                            onChange={(value) => void saveSettings({
                                appearance: {
                                    ...settings.appearance,
                                    sidebar_default: value as "expanded" | "collapsed",
                                },
                            })}
                        />
                    </div>
                </Space>
            </Card>
        </div>
    );

    const chatTab = (
        <div className="settings-section-grid">
            <Card className="settings-section-card" title="发送与展示">
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                    <div className="settings-field">
                        <Typography.Text strong>发送方式</Typography.Text>
                        <Segmented
                            block
                            value={settings.chat.send_shortcut}
                            options={[
                                { label: "Enter 发送", value: "enter" },
                                { label: "Ctrl+Enter 发送", value: "ctrl_enter" },
                            ]}
                            onChange={(value) => void handleSaveChatSettings({ send_shortcut: value as "enter" | "ctrl_enter" })}
                        />
                    </div>
                    <SettingSwitch
                        checked={settings.chat.expand_thinking_by_default}
                        label="默认展开思考过程"
                        onChange={(checked) => void handleSaveChatSettings({ expand_thinking_by_default: checked })}
                    />
                    <SettingSwitch
                        checked={settings.chat.show_evidence_panel_by_default}
                        label="默认显示依据面板"
                        onChange={(checked) => void handleSaveChatSettings({ show_evidence_panel_by_default: checked })}
                    />
                    <SettingSwitch
                        checked={settings.chat.show_context_debug_by_default}
                        label="显示上下文调试信息"
                        onChange={(checked) => void handleSaveChatSettings({ show_context_debug_by_default: checked })}
                    />
                    <SettingSwitch
                        checked={settings.chat.auto_generate_title_for_new_session}
                        label="新会话自动生成标题"
                        onChange={(checked) => void handleSaveChatSettings({ auto_generate_title_for_new_session: checked })}
                    />
                </Space>
            </Card>
            <Card className="settings-section-card" title="可靠性提示">
                <div className="settings-field">
                    <Typography.Text strong>重连提示显示方式</Typography.Text>
                    <Segmented
                        block
                        value={settings.chat.reconnect_notice_mode}
                        options={[
                            { label: "仅消息内提示", value: "message_only" },
                            { label: "消息内 + 弹出提示", value: "toast_and_message" },
                        ]}
                        onChange={(value) => void handleSaveChatSettings({
                            reconnect_notice_mode: value as "message_only" | "toast_and_message",
                        })}
                    />
                </div>
            </Card>
        </div>
    );

    const sessionManagementTab = (
        <div className="settings-section-grid">
            <Card
                className="settings-section-card settings-section-card--wide"
                title="批量管理会话"
                extra={<Tag color={selectedSessionIds.length ? "blue" : "default"}>已选 {selectedSessionIds.length}</Tag>}
            >
                <Space direction="vertical" size={14} style={{ width: "100%" }}>
                    <Typography.Paragraph type="secondary">
                        用于一次性清理不需要的历史会话。这里只删除会话记录，不会影响账号、主题和模型配置。
                    </Typography.Paragraph>
                    <div className="settings-session-toolbar">
                        <Space wrap>
                            <Button onClick={handleSelectAllSessions} disabled={!sessionList.length}>
                                全选当前列表
                            </Button>
                            <Button onClick={() => setSelectedSessionIds([])} disabled={!selectedSessionIds.length}>
                                清空选择
                            </Button>
                            <Button onClick={() => void loadSessionListForSettings()} loading={loadingSessionList}>
                                刷新
                            </Button>
                        </Space>
                        <Button
                            danger
                            type="primary"
                            loading={deletingSessions}
                            onClick={handleDeleteSelectedSessions}
                        >
                            删除选中
                        </Button>
                    </div>
                    <List
                        className="settings-session-bulk-list"
                        loading={loadingSessionList}
                        dataSource={sessionList}
                        locale={{ emptyText: "当前没有可清理的会话。" }}
                        renderItem={(session) => (
                            <List.Item
                                className={[
                                    "settings-session-bulk-list__item",
                                    selectedSessionIds.includes(session.session_id) ? "settings-session-bulk-list__item--selected" : null,
                                ].filter(Boolean).join(" ")}
                                role="button"
                                tabIndex={0}
                                actions={[
                                    <Button
                                        key="open"
                                        type="text"
                                        size="small"
                                        icon={<FolderOpenOutlined />}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            handleOpenManagedSession(session.session_id);
                                        }}
                                    >
                                        打开
                                    </Button>,
                                    <Button
                                        key="delete"
                                        danger
                                        type="text"
                                        size="small"
                                        icon={<DeleteOutlined />}
                                        loading={deletingSessions}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            handleDeleteSingleSession(session);
                                        }}
                                    >
                                        删除
                                    </Button>,
                                ]}
                                onClick={() => toggleSessionSelection(
                                    session.session_id,
                                    !selectedSessionIds.includes(session.session_id),
                                )}
                                onKeyDown={(event) => {
                                    if (event.key === "Enter" || event.key === " ") {
                                        event.preventDefault();
                                        toggleSessionSelection(
                                            session.session_id,
                                            !selectedSessionIds.includes(session.session_id),
                                        );
                                    }
                                }}
                            >
                                <Checkbox
                                    checked={selectedSessionIds.includes(session.session_id)}
                                    onClick={(event) => event.stopPropagation()}
                                    onChange={(event) => toggleSessionSelection(session.session_id, event.target.checked)}
                                />
                                <div className="settings-session-bulk-list__copy">
                                    <Typography.Text strong ellipsis>
                                        {session.title || "未命名会话"}
                                    </Typography.Text>
                                    <Typography.Text type="secondary">
                                        最近更新：{formatDateTime(session.updated_at)}
                                    </Typography.Text>
                                </div>
                            </List.Item>
                        )}
                    />
                </Space>
            </Card>
        </div>
    );

    const providerTab = (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <div className="settings-provider-toolbar">
                <Button icon={<CloudServerOutlined />} onClick={() => void handleSetActiveProvider(BUILTIN_PROVIDER_REF)}>
                    切回默认云端
                </Button>
                <Button icon={<PlusOutlined />} onClick={() => setProviderDraft(buildOllamaDeepSeekDraft())}>
                    一键填充 Ollama / DeepSeek-R1 8B
                </Button>
                <Button icon={<PlusOutlined />} onClick={() => setProviderDraft(buildBlankProviderDraft())}>
                    新建账号 Provider
                </Button>
                <Tag color="blue">当前：{settings.active_provider_ref}</Tag>
            </div>

            <div className="settings-provider-columns">
                <Card className="settings-section-card" title="当前可用 Provider">
                    <List
                        dataSource={[
                            { key: BUILTIN_PROVIDER_REF, label: "CarbonRag 默认云端", type: "builtin" as const },
                            ...providerList.profiles.map((item) => ({ key: `account:${item.profile_id}`, label: item.display_name, type: "account" as const, profile: item })),
                        ]}
                        renderItem={(item) => (
                            <List.Item
                                actions={[
                                    <Button key="use" size="small" type={settings.active_provider_ref === item.key ? "primary" : "default"} onClick={() => void handleSetActiveProvider(item.key)}>
                                        启用
                                    </Button>,
                                    item.type === "account" ? (
                                        <Button key="edit" size="small" onClick={() => editAccountProfile(item.profile as ProviderProfile)}>编辑</Button>
                                    ) : null,
                                    item.type === "account" ? (
                                        <Button key="delete" size="small" danger onClick={() => void deleteAccountProviderProfile((item.profile as ProviderProfile).profile_id)}>删除</Button>
                                    ) : null,
                                ].filter(Boolean)}
                            >
                                <List.Item.Meta
                                    title={item.label}
                                    description={item.type === "builtin" ? "内置开箱即用" : item.key}
                                />
                            </List.Item>
                        )}
                    />
                </Card>

                <Card className="settings-section-card" title="Provider 编辑器">
                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                        <Alert
                            type="info"
                            showIcon
                            message="Provider 配置按账号隔离保存"
                            description="本地设备级 Provider 已停用。API Key 只会加密保存到当前账号，不会在其他账号中显示。"
                        />
                        <Select
                            value={providerDraft.providerType}
                            options={providerTypeOptions.map((item) => ({ value: item.value, label: item.label }))}
                            onChange={(value) => setProviderDraft((current) => ({ ...current, providerType: value }))}
                        />
                        <Input value={providerDraft.displayName} placeholder="显示名称" onChange={(event) => setProviderDraft((current) => ({ ...current, displayName: event.target.value }))} />
                        <Input value={providerDraft.baseUrl} placeholder="Base URL（可选）" onChange={(event) => setProviderDraft((current) => ({ ...current, baseUrl: event.target.value }))} />
                        <Input.Password value={providerDraft.apiKey} placeholder="API Key（可选）" onChange={(event) => setProviderDraft((current) => ({ ...current, apiKey: event.target.value }))} />
                        <div className="settings-field">
                            <Typography.Text strong>模型</Typography.Text>
                            <AutoComplete
                                value={providerDraft.modelName}
                                options={providerDraft.models.map((item) => ({ label: item, value: item }))}
                                placeholder="选择或输入模型名"
                                filterOption={(inputValue, option) =>
                                    String(option?.value ?? "").toLowerCase().includes(inputValue.toLowerCase())
                                }
                                onChange={(value) => setProviderDraft((current) => ({ ...current, modelName: value }))}
                            />
                            <Typography.Text type="secondary">
                                先点“刷新模型”可自动发现；兼容服务也可以直接手动输入模型名。
                            </Typography.Text>
                        </div>
                        <Space wrap>
                            <Button loading={testingProvider} onClick={() => void handleDiscoverModels()}>
                                {providerDraft.providerType === "ollama" ? "刷新本地模型" : "刷新模型"}
                            </Button>
                            <Button loading={testingProvider} onClick={() => void handleTestProvider()}>
                                {providerDraft.providerType === "ollama" ? "测试 Ollama" : "测试连接"}
                            </Button>
                            <Button type="primary" loading={savingProvider} icon={<SaveOutlined />} onClick={() => void handleSaveProvider()}>
                                保存 Provider
                            </Button>
                        </Space>
                        {providerDraft.providerType === "ollama" ? (
                            <Alert
                                type="info"
                                showIcon
                                message="Ollama 本地模型只保证 local-dev"
                                description="后端必须和 Ollama 在同一台机器上，默认访问 http://localhost:11434。公网 VPS 不能直接访问你电脑上的 localhost。"
                            />
                        ) : null}
                    </Space>
                </Card>
            </div>
        </Space>
    );

    const privacyTab = (
        <div className="settings-section-grid">
            <Card className="settings-section-card" title="凭据保存">
                <Space direction="vertical" size={14}>
                    <SettingSwitch
                        checked={settings.data_privacy.allow_account_saved_provider_keys}
                        label="允许当前账号保存加密 Provider Key"
                        onChange={(checked) => void handleSaveDataPrivacy({ allow_account_saved_provider_keys: checked })}
                    />
                </Space>
            </Card>
            <Card className="settings-section-card" title="账号危险区">
                <Space direction="vertical" size={14} style={{ width: "100%" }}>
                    <Alert
                        type="warning"
                        showIcon
                        message="注销账号会删除当前登录账号，并使现有登录会话失效。历史业务记录不会在本轮级联清空。"
                    />
                    <Button danger onClick={() => setDeleteAccountModalOpen(true)}>
                        注销当前账号
                    </Button>
                </Space>
            </Card>
        </div>
    );

    const advancedTab = (
        <div className="settings-section-grid">
            <Card className="settings-section-card settings-section-card--wide" title="当前运行配置">
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Typography.Text type="secondary">
                        当前生效 Provider：{settings.active_provider_ref}
                    </Typography.Text>
                    <Typography.Text type="secondary">
                        Provider 配置仅按账号保存和读取。本地设备级 Provider 已关闭，避免不同账号之间串配置。
                    </Typography.Text>
                </Space>
            </Card>
        </div>
    );

    return (
        <div className="settings-console">
            <Card className="settings-console__hero">
                <div className="settings-console__hero-layout">
                    <div className="settings-console__hero-copy">
                        <Typography.Text className="settings-console__eyebrow">通用设置</Typography.Text>
                        <Typography.Title level={2}>把账号、外观和模型配置收进一个入口</Typography.Title>
                        <Typography.Paragraph type="secondary">
                            这里集中管理个人资料、主题、聊天偏好、模型提供方和数据保存策略。
                        </Typography.Paragraph>
                    </div>
                    <div className="settings-profile-card">
                        <div className="settings-profile-card__identity">
                            <Avatar size={70} src={profileAvatarDraft ?? undefined}>
                                {profileNameDraft.trim().slice(0, 1).toUpperCase() || getUserInitial(user)}
                            </Avatar>
                            <div className="settings-profile-card__copy">
                                <Typography.Text strong>{user.display_name || user.username}</Typography.Text>
                                <Tag color={user.role === "admin" ? "purple" : "blue"}>{user.role}</Tag>
                            </div>
                        </div>
                        <Space direction="vertical" size={10} style={{ width: "100%" }}>
                            <div className="settings-field">
                                <Typography.Text strong>账号</Typography.Text>
                                <Input value={user.username} disabled />
                            </div>
                            <div className="settings-field">
                                <Typography.Text strong>昵称</Typography.Text>
                                <Input
                                    value={profileNameDraft}
                                    maxLength={64}
                                    placeholder="输入昵称"
                                    onChange={(event) => setProfileNameDraft(event.target.value)}
                                    onPressEnter={() => void handleSaveProfile()}
                                />
                            </div>
                            <div className="settings-field">
                                <Typography.Text strong>密码</Typography.Text>
                                <Button onClick={() => navigate("/change-password")}>修改密码</Button>
                            </div>
                            <Space wrap>
                                <Button icon={<UploadOutlined />} onClick={() => avatarInputRef.current?.click()}>
                                    上传头像
                                </Button>
                                <Button onClick={() => setProfileAvatarDraft(null)}>移除头像</Button>
                                <Button type="primary" loading={profileSaving} onClick={() => void handleSaveProfile()}>
                                    保存资料
                                </Button>
                            </Space>
                            <Typography.Text type="secondary">昵称不可重复；admin / user 仅作为身份标签显示。</Typography.Text>
                            <input
                                ref={avatarInputRef}
                                type="file"
                                accept="image/*"
                                hidden
                                onChange={handleAvatarFileChange}
                            />
                        </Space>
                    </div>
                </div>
            </Card>

            <Card className="settings-console__tabs">
                <Tabs
                    items={[
                        { key: "appearance", label: "外观", children: appearanceTab },
                        { key: "chat", label: "聊天", children: chatTab },
                        { key: "sessions", label: "会话管理", children: sessionManagementTab },
                        { key: "provider", label: "模型与提供方", children: providerTab },
                        { key: "privacy", label: "数据与隐私", children: privacyTab },
                        { key: "advanced", label: "高级", children: advancedTab },
                    ]}
                />
            </Card>

            <Modal
                title="注销当前账号"
                open={deleteAccountModalOpen}
                okText="确认注销"
                okButtonProps={{ danger: true, loading: deletingAccount }}
                onOk={() => void handleDeleteOwnAccount()}
                onCancel={() => {
                    if (deletingAccount) {
                        return;
                    }
                    setDeleteAccountModalOpen(false);
                    setDeleteAccountPassword("");
                }}
            >
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Alert
                        type="error"
                        showIcon
                        message="请再次输入当前账号密码。注销后需要重新注册或由管理员创建账号。"
                    />
                    <Input.Password
                        value={deleteAccountPassword}
                        placeholder="当前账号密码"
                        onChange={(event) => setDeleteAccountPassword(event.target.value)}
                        onPressEnter={() => void handleDeleteOwnAccount()}
                    />
                </Space>
            </Modal>
        </div>
    );
}

function SettingSwitch({
    checked,
    label,
    onChange,
}: {
    checked: boolean;
    label: string;
    onChange: (checked: boolean) => void;
}) {
    return (
        <div className="settings-switch-row">
            <Switch checked={checked} onChange={onChange} />
            <Typography.Text>{label}</Typography.Text>
        </div>
    );
}

function getUserInitial(user: { display_name?: string | null; username: string }) {
    const value = user.display_name || user.username;
    return value.slice(0, 1).toUpperCase();
}

function formatDateTime(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { response?: { data?: { detail?: unknown } }; detail?: unknown };
    const detail = candidate.response?.data?.detail ?? candidate.detail;
    return typeof detail === "string" ? detail : null;
}
