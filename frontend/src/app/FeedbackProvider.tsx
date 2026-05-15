import { App as AntdApp } from "antd";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

export type FeedbackSeverity = "success" | "info" | "warning" | "error";

export interface FeedbackEntry {
    id: string;
    severity: FeedbackSeverity;
    title: string;
    description?: string;
    page?: string;
    source?: string;
    createdAt: string;
    sticky?: boolean;
    raw?: unknown;
}

export interface FeedbackInput {
    title: string;
    description?: string;
    page?: string;
    source?: string;
    sticky?: boolean;
    raw?: unknown;
    history?: boolean;
    key?: string;
}

interface FeedbackContextValue {
    entries: FeedbackEntry[];
    push: (severity: FeedbackSeverity, input: FeedbackInput) => FeedbackEntry;
    success: (input: FeedbackInput) => FeedbackEntry;
    info: (input: FeedbackInput) => FeedbackEntry;
    warning: (input: FeedbackInput) => FeedbackEntry;
    error: (input: FeedbackInput) => FeedbackEntry;
    clear: () => void;
    remove: (id: string) => void;
}

const STORAGE_KEY = "carbonrag-feedback-center";
const MAX_HISTORY = 100;
const FeedbackContext = createContext<FeedbackContextValue | null>(null);

export function FeedbackProvider({ children }: { children: React.ReactNode }) {
    const { message } = AntdApp.useApp();
    const [entries, setEntries] = useState<FeedbackEntry[]>(() => loadEntries());
    const recentKeysRef = useRef<Record<string, number>>({});

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)));
    }, [entries]);

    const push = useCallback((severity: FeedbackSeverity, input: FeedbackInput) => {
        const dedupeKey = input.key ?? `${severity}:${input.source ?? ""}:${input.title}:${input.description ?? ""}`;
        const now = Date.now();
        const lastSeen = recentKeysRef.current[dedupeKey];
        if (lastSeen && now - lastSeen < 2500) {
            return {
                id: `deduped-${dedupeKey}`,
                severity,
                title: input.title,
                description: input.description,
                page: input.page,
                source: input.source,
                createdAt: new Date(now).toISOString(),
                sticky: input.sticky,
                raw: input.raw,
            };
        }
        recentKeysRef.current = { ...recentKeysRef.current, [dedupeKey]: now };

        const entry: FeedbackEntry = {
            id: `${severity}-${now}-${Math.random().toString(16).slice(2)}`,
            severity,
            title: input.title,
            description: input.description,
            page: input.page,
            source: input.source,
            createdAt: new Date(now).toISOString(),
            sticky: input.sticky,
            raw: input.raw,
        };

        const shouldSaveHistory = input.history ?? (severity === "error" || severity === "warning");
        if (shouldSaveHistory) {
            setEntries((current) => [entry, ...current.filter((item) => item.id !== entry.id)].slice(0, MAX_HISTORY));
        }

        const content = input.description ? `${input.title}：${input.description}` : input.title;
        message.open({
            type: severity,
            content,
            duration: input.sticky ? 0 : severity === "error" ? 5 : 3,
            key: dedupeKey,
        });
        return entry;
    }, [message]);

    const value = useMemo<FeedbackContextValue>(() => ({
        entries,
        push,
        success: (input) => push("success", input),
        info: (input) => push("info", input),
        warning: (input) => push("warning", input),
        error: (input) => push("error", input),
        clear: () => setEntries([]),
        remove: (id) => setEntries((current) => current.filter((item) => item.id !== id)),
    }), [entries, push]);

    return <FeedbackContext.Provider value={value}>{children}</FeedbackContext.Provider>;
}

export function useFeedbackContext() {
    const context = useContext(FeedbackContext);
    if (!context) {
        throw new Error("useFeedback must be used inside FeedbackProvider.");
    }
    return context;
}

function loadEntries(): FeedbackEntry[] {
    if (typeof window === "undefined") {
        return [];
    }
    try {
        const raw = window.sessionStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return [];
        }
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.slice(0, MAX_HISTORY) : [];
    } catch {
        return [];
    }
}
