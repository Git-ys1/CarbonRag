import { Spin } from "antd";
import { createBrowserRouter, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { AppShell } from "../layouts/AppShell";
import { AdminPlaceholderPage } from "../pages/AdminPlaceholderPage";
import { AskPage } from "../pages/AskPage";
import { CarbonCalcPage } from "../pages/CarbonCalcPage";
import { CarbonFactorsPage } from "../pages/CarbonFactorsPage";
import { ChangePasswordPage } from "../pages/ChangePasswordPage";
import { LoginPage } from "../pages/LoginPage";
import { MyKnowledgePage } from "../pages/MyKnowledgePage";
import { KnowledgeBaseWorkbench } from "../pages/KnowledgeBaseWorkbench";
import { ReportPage } from "../pages/ReportPage";
import { SettingsPage } from "../pages/SettingsPage";
import { SuperAdminPage } from "../pages/SuperAdminPage";

function FullscreenLoading() {
    return (
        <div className="auth-shell">
            <div className="auth-loading">
                <Spin size="large" />
            </div>
        </div>
    );
}

function GuestOnlyRoute() {
    const { user, loading } = useAuth();

    if (loading) {
        return <FullscreenLoading />;
    }
    if (!user) {
        return <Outlet />;
    }
    return <Navigate to={user.password_must_change ? "/change-password" : "/"} replace />;
}

function PasswordChangeRoute() {
    const { user, loading } = useAuth();

    if (loading) {
        return <FullscreenLoading />;
    }
    if (!user) {
        return <Navigate to="/login" replace />;
    }
    if (!user.password_must_change) {
        return <Navigate to="/" replace />;
    }
    return <Outlet />;
}

function ProtectedRoute() {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) {
        return <FullscreenLoading />;
    }
    if (!user) {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }
    if (user.password_must_change) {
        return <Navigate to="/change-password" replace />;
    }
    return <Outlet />;
}

function AdminRoute() {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) {
        return <FullscreenLoading />;
    }
    if (!user) {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }
    if (user.password_must_change) {
        return <Navigate to="/change-password" replace />;
    }
    if (user.role !== "admin" && user.role !== "super_admin") {
        return <Navigate to="/" replace />;
    }
    return <Outlet />;
}

function SuperAdminRoute() {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) {
        return <FullscreenLoading />;
    }
    if (!user) {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }
    if (user.password_must_change) {
        return <Navigate to="/change-password" replace />;
    }
    if (user.role !== "super_admin") {
        return <Navigate to="/" replace />;
    }
    return <Outlet />;
}

export const router = createBrowserRouter([
    {
        element: <GuestOnlyRoute />,
        children: [
            { path: "/login", element: <LoginPage /> },
        ],
    },
    {
        element: <PasswordChangeRoute />,
        children: [
            { path: "/change-password", element: <ChangePasswordPage /> },
        ],
    },
    {
        element: <ProtectedRoute />,
        children: [
            {
                path: "/",
                element: <AppShell />,
                children: [
                    { index: true, element: <AskPage /> },
                    { path: "knowledge", element: <Navigate to="/kb" replace /> },
                    { path: "my-knowledge", element: <MyKnowledgePage /> },
                    { path: "kb", element: <KnowledgeBaseWorkbench /> },
                    { path: "carbon", element: <Navigate to="/carbon-factors" replace /> },
                    { path: "carbon-factors", element: <CarbonFactorsPage /> },
                    { path: "carbon-calc", element: <CarbonCalcPage /> },
                    { path: "report", element: <ReportPage /> },
                    { path: "settings", element: <SettingsPage /> },
                    { path: "rag-lab", element: <Navigate to="/kb" replace /> },
                    {
                        element: <AdminRoute />,
                        children: [
                            { path: "admin", element: <AdminPlaceholderPage /> },
                        ],
                    },
                    {
                        element: <SuperAdminRoute />,
                        children: [
                            { path: "super-admin", element: <SuperAdminPage /> },
                        ],
                    },
                ],
            },
        ],
    },
    { path: "*", element: <Navigate to="/" replace /> },
]);
