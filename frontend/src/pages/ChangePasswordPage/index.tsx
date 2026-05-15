import { LockOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Typography } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useFeedback } from "../../hooks/useFeedback";

interface ChangePasswordFormValues {
    current_password: string;
    new_password: string;
    confirm_password: string;
}

export function ChangePasswordPage() {
    const navigate = useNavigate();
    const { user, loading, changePassword } = useAuth();
    const feedback = useFeedback();
    const [submitting, setSubmitting] = useState(false);
    const [form] = Form.useForm<ChangePasswordFormValues>();

    useEffect(() => {
        if (loading) {
            return;
        }
        if (!user) {
            navigate("/login", { replace: true });
            return;
        }
        if (!user.password_must_change) {
            navigate("/", { replace: true });
        }
    }, [loading, navigate, user]);

    async function handleSubmit(values: ChangePasswordFormValues) {
        setSubmitting(true);
        try {
            await changePassword({
                current_password: values.current_password,
                new_password: values.new_password,
            });
            feedback.success({ title: "密码已更新。" });
            navigate("/", { replace: true });
        } catch (error) {
            feedback.error({
                title: "修改密码失败",
                description: extractDetailMessage(error) ?? "请稍后重试。",
                source: "ChangePasswordPage",
            });
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="auth-shell">
            <Card className="auth-card">
                <Typography.Title level={2}>修改密码</Typography.Title>
                <Typography.Paragraph type="secondary">
                    初始管理员账号和被重置密码的账号，都必须先完成这一步，才能进入工作台。
                </Typography.Paragraph>
                <Form<ChangePasswordFormValues> form={form} layout="vertical" onFinish={handleSubmit}>
                    <Form.Item
                        label="当前密码"
                        name="current_password"
                        rules={[{ required: true, message: "请输入当前密码。" }]}
                    >
                        <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
                    </Form.Item>
                    <Form.Item
                        label="新密码"
                        name="new_password"
                        rules={[{ required: true, message: "请输入新密码。" }]}
                    >
                        <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
                    </Form.Item>
                    <Form.Item
                        label="确认新密码"
                        name="confirm_password"
                        dependencies={["new_password"]}
                        rules={[
                            { required: true, message: "请再次输入新密码。" },
                            ({ getFieldValue }) => ({
                                validator(_, value) {
                                    if (!value || value === getFieldValue("new_password")) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject(new Error("两次输入的新密码不一致。"));
                                },
                            }),
                        ]}
                    >
                        <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" block loading={submitting}>
                        更新密码
                    </Button>
                </Form>
            </Card>
        </div>
    );
}

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { detail?: unknown };
    return typeof candidate.detail === "string" ? candidate.detail : null;
}
