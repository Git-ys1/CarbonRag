import { CopyOutlined, DeleteOutlined } from "@ant-design/icons";
import { Button, Descriptions, Drawer, Empty, List, Segmented, Space, Tag, Typography } from "antd";
import { useMemo, useState } from "react";
import type { FeedbackEntry, FeedbackSeverity } from "../app/FeedbackProvider";
import { useFeedback } from "../hooks/useFeedback";

const severityOptions: Array<FeedbackSeverity | "all"> = ["all", "error", "warning", "info", "success"];
const severityLabel: Record<FeedbackSeverity | "all", string> = {
    all: "全部",
    error: "错误",
    warning: "警告",
    info: "信息",
    success: "成功",
};
const severityColor: Record<FeedbackSeverity, string> = {
    error: "red",
    warning: "gold",
    info: "blue",
    success: "green",
};

export function FeedbackCenter({ open, onClose }: { open: boolean; onClose: () => void }) {
    const feedback = useFeedback();
    const [filter, setFilter] = useState<FeedbackSeverity | "all">("all");
    const [selected, setSelected] = useState<FeedbackEntry | null>(null);

    const entries = useMemo(() => {
        return feedback.entries.filter((entry) => filter === "all" || entry.severity === filter);
    }, [feedback.entries, filter]);

    return (
        <Drawer
            title="消息中心"
            placement="right"
            width={520}
            open={open}
            onClose={onClose}
            extra={(
                <Space>
                    <Segmented
                        size="small"
                        value={filter}
                        options={severityOptions.map((value) => ({ label: severityLabel[value], value }))}
                        onChange={(value) => setFilter(value as FeedbackSeverity | "all")}
                    />
                    <Button size="small" icon={<DeleteOutlined />} onClick={feedback.clear}>
                        清空
                    </Button>
                </Space>
            )}
        >
            {entries.length ? (
                <List
                    dataSource={entries}
                    split
                    renderItem={(entry) => (
                        <List.Item
                            className="feedback-center__item"
                            actions={[
                                <Button key="detail" type="link" onClick={() => setSelected(entry)}>
                                    详情
                                </Button>,
                                <Button
                                    key="copy"
                                    type="text"
                                    icon={<CopyOutlined />}
                                    onClick={() => void copyEntry(entry)}
                                />,
                            ]}
                        >
                            <List.Item.Meta
                                title={(
                                    <Space size={8}>
                                        <Tag color={severityColor[entry.severity]}>{severityLabel[entry.severity]}</Tag>
                                        <Typography.Text>{entry.title}</Typography.Text>
                                    </Space>
                                )}
                                description={(
                                    <Space direction="vertical" size={2}>
                                        {entry.description ? (
                                            <Typography.Text type="secondary">{entry.description}</Typography.Text>
                                        ) : null}
                                        <Typography.Text type="secondary" className="feedback-center__time">
                                            {new Date(entry.createdAt).toLocaleString()}
                                            {entry.source ? ` · ${entry.source}` : ""}
                                        </Typography.Text>
                                    </Space>
                                )}
                            />
                        </List.Item>
                    )}
                />
            ) : (
                <Empty description="暂无消息记录" />
            )}
            <Drawer
                title="消息详情"
                placement="right"
                width={480}
                open={Boolean(selected)}
                onClose={() => setSelected(null)}
            >
                {selected ? (
                    <Space direction="vertical" size={16} style={{ width: "100%" }}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="级别">{severityLabel[selected.severity]}</Descriptions.Item>
                            <Descriptions.Item label="标题">{selected.title}</Descriptions.Item>
                            <Descriptions.Item label="描述">{selected.description || "-"}</Descriptions.Item>
                            <Descriptions.Item label="页面">{selected.page || "-"}</Descriptions.Item>
                            <Descriptions.Item label="来源">{selected.source || "-"}</Descriptions.Item>
                            <Descriptions.Item label="时间">{new Date(selected.createdAt).toLocaleString()}</Descriptions.Item>
                        </Descriptions>
                        <Button icon={<CopyOutlined />} onClick={() => void copyEntry(selected)}>
                            复制详情
                        </Button>
                        {selected.raw ? (
                            <pre className="feedback-center__raw">{safeStringify(selected.raw)}</pre>
                        ) : null}
                    </Space>
                ) : null}
            </Drawer>
        </Drawer>
    );
}

async function copyEntry(entry: FeedbackEntry) {
    const text = [
        `[${entry.severity}] ${entry.title}`,
        entry.description,
        entry.page ? `page: ${entry.page}` : "",
        entry.source ? `source: ${entry.source}` : "",
        `time: ${entry.createdAt}`,
        entry.raw ? safeStringify(entry.raw) : "",
    ].filter(Boolean).join("\n");
    await navigator.clipboard.writeText(text);
}

function safeStringify(value: unknown) {
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
}
