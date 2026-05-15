import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Tabs } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { useFeedback } from "../../hooks/useFeedback";

type AuthTab = "login" | "register";

interface FormValues {
    username: string;
    display_name?: string;
    password: string;
}

export function LoginPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const { user, loading, login, register } = useAuth();
    const feedback = useFeedback();
    const [activeTab, setActiveTab] = useState<AuthTab>("login");
    const [submitting, setSubmitting] = useState(false);
    const [loginForm] = Form.useForm<FormValues>();
    const [registerForm] = Form.useForm<FormValues>();

    const redirectTarget = useMemo(() => {
        const state = location.state as { from?: { pathname?: string } } | null;
        return state?.from?.pathname && state.from.pathname !== "/login" ? state.from.pathname : "/";
    }, [location.state]);

    useEffect(() => {
        if (loading || !user) {
            return;
        }
        navigate(user.password_must_change ? "/change-password" : redirectTarget, { replace: true });
    }, [loading, navigate, redirectTarget, user]);

    async function handleLogin(values: FormValues) {
        setSubmitting(true);
        try {
            const loggedInUser = await login(values);
            feedback.success({ title: `欢迎回来，${loggedInUser.display_name || loggedInUser.username}。` });
            navigate(loggedInUser.password_must_change ? "/change-password" : redirectTarget, { replace: true });
        } catch (error) {
            feedback.error({
                title: "登录失败",
                description: extractDetailMessage(error) ?? "请检查账号和密码。",
                source: "LoginPage",
            });
        } finally {
            setSubmitting(false);
        }
    }

    async function handleRegister(values: FormValues) {
        setSubmitting(true);
        try {
            const createdUser = await register(values);
            if (createdUser.username === "admin" && createdUser.role === "super_admin") {
                feedback.success({ title: "初始超级管理员已恢复，请登录后立即修改密码。", history: true });
            } else {
                feedback.success({ title: `账号 ${createdUser.username} 已创建，请登录。` });
            }
            setActiveTab("login");
            loginForm.setFieldsValue({ username: createdUser.username, password: values.password });
            registerForm.resetFields();
        } catch (error) {
            feedback.error({
                title: "注册失败",
                description: extractDetailMessage(error) ?? "请稍后重试。",
                source: "LoginPage",
            });
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="auth-shell">
            <Card className="auth-card">
                <div className="auth-card__brand">
                    <img src="/brand/logo-lockup.png" alt="CarbonRag" />
                </div>
                <Tabs
                    activeKey={activeTab}
                    onChange={(key) => setActiveTab(key as AuthTab)}
                    items={[
                        {
                            key: "login",
                            label: "登录",
                            children: (
                                <Form<FormValues> form={loginForm} layout="vertical" onFinish={handleLogin}>
                                    <Form.Item
                                        label="账号"
                                        name="username"
                                        rules={[{ required: true, message: "请输入账号。" }]}
                                    >
                                        <Input prefix={<UserOutlined />} autoComplete="username" />
                                    </Form.Item>
                                    <Form.Item
                                        label="密码"
                                        name="password"
                                        rules={[{ required: true, message: "请输入密码。" }]}
                                    >
                                        <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
                                    </Form.Item>
                                    <Button type="primary" htmlType="submit" block loading={submitting}>
                                        登录
                                    </Button>
                                </Form>
                            ),
                        },
                        {
                            key: "register",
                            label: "注册",
                            children: (
                                <Form<FormValues> form={registerForm} layout="vertical" onFinish={handleRegister}>
                                    <Form.Item
                                        label="账号"
                                        name="username"
                                        rules={[{ required: true, message: "请输入账号。" }]}
                                        extra="用于登录，支持英文字母、数字、下划线和连字符；保存时统一为小写。管理员账号默认为 admin。"
                                    >
                                        <Input prefix={<UserOutlined />} autoComplete="username" />
                                    </Form.Item>
                                    <Form.Item
                                        label="昵称"
                                        name="display_name"
                                        extra="可选。不填写时系统会生成随机昵称。"
                                    >
                                        <Input prefix={<UserOutlined />} autoComplete="nickname" />
                                    </Form.Item>
                                    <Form.Item
                                        label="密码"
                                        name="password"
                                        rules={[{ required: true, message: "请输入密码。" }]}
                                        extra="至少 6 位字符。"
                                    >
                                        <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
                                    </Form.Item>
                                    <Button htmlType="submit" block loading={submitting}>
                                        创建账号
                                    </Button>
                                </Form>
                            ),
                        },
                    ]}
                />
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
