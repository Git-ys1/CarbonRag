import type { UserRole } from "../types/auth";

export interface NavigationItem {
    key: string;
    path?: string;
    label: string;
    roles: UserRole[];
    children?: NavigationItem[];
}

const ALL_NAV_ITEMS: NavigationItem[] = [
    { key: "ask", path: "/", label: "问答工作台", roles: ["user", "admin", "super_admin"] },
    {
        key: "knowledge",
        label: "知识库",
        roles: ["user", "admin", "super_admin"],
        children: [
            { key: "knowledge-items", path: "/my-knowledge", label: "个人知识条目", roles: ["user", "admin", "super_admin"] },
            { key: "knowledge-ingest", path: "/kb", label: "入库与评测", roles: ["user", "admin", "super_admin"] },
        ],
    },
    {
        key: "carbon",
        label: "碳核算",
        roles: ["user", "admin", "super_admin"],
        children: [
            { key: "carbon-factors", path: "/carbon-factors", label: "碳因子库", roles: ["user", "admin", "super_admin"] },
            { key: "carbon-calculator", path: "/carbon-calc", label: "生活碳计算器", roles: ["user", "admin", "super_admin"] },
        ],
    },
    { key: "report", path: "/report", label: "报告生成", roles: ["user", "admin", "super_admin"] },
];

export const ADMIN_NAV_ITEM: NavigationItem = {
    key: "admin",
    path: "/admin",
    label: "管理员入口",
    roles: ["admin", "super_admin"],
};

export const SUPER_ADMIN_NAV_ITEM: NavigationItem = {
    key: "super-admin",
    path: "/super-admin",
    label: "超级管理员",
    roles: ["super_admin"],
};

export function getNavigationItems(role: UserRole) {
    return filterNavigationItems(ALL_NAV_ITEMS, role);
}

function filterNavigationItems(items: NavigationItem[], role: UserRole): NavigationItem[] {
    return items
        .filter((item) => item.roles.includes(role))
        .map((item) => ({
            ...item,
            children: item.children ? filterNavigationItems(item.children, role) : undefined,
        }))
        .filter((item) => !item.children || item.children.length > 0);
}
