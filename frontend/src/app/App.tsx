import { RouterProvider } from "react-router-dom";
import { App as AntdApp } from "antd";
import { AuthProvider } from "./AuthContext";
import { FeedbackProvider } from "./FeedbackProvider";
import { SettingsProvider } from "./SettingsContext";
import { ThemeProvider } from "./ThemeContext";
import { FeedbackCenterButton } from "../components/FeedbackCenterButton";
import { router } from "../router";

export function App() {
    return (
        <ThemeProvider>
            <AntdApp message={{ top: 72 }} notification={{ placement: "top" }}>
                <AuthProvider>
                    <SettingsProvider>
                        <FeedbackProvider>
                            <RouterProvider router={router} />
                            <FeedbackCenterButton />
                        </FeedbackProvider>
                    </SettingsProvider>
                </AuthProvider>
            </AntdApp>
        </ThemeProvider>
    );
}
