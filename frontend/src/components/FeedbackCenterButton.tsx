import { BellOutlined } from "@ant-design/icons";
import { Badge, Button } from "antd";
import { useState } from "react";
import { useFeedback } from "../hooks/useFeedback";
import { FeedbackCenter } from "./FeedbackCenter";

export function FeedbackCenterButton() {
    const feedback = useFeedback();
    const [open, setOpen] = useState(false);
    const unreadCount = feedback.entries.filter((entry) => entry.severity === "error" || entry.severity === "warning").length;

    return (
        <>
            <Badge count={unreadCount} size="small" className="feedback-center-button__badge">
                <Button
                    className="feedback-center-button"
                    shape="circle"
                    icon={<BellOutlined />}
                    aria-label="打开消息中心"
                    onClick={() => setOpen(true)}
                />
            </Badge>
            <FeedbackCenter open={open} onClose={() => setOpen(false)} />
        </>
    );
}
