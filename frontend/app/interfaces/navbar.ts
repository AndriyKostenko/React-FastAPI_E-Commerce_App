import type { ReactNode } from "react";
import type { IconType } from "react-icons";
import type { CurrentUserShape } from "@/app/interfaces/auth";

export interface BackDropProps {
    onClick: () => void;
}

export interface MenuItemProps {
    children: ReactNode;
    onClick: () => void;
}

export interface UserMenuProps {
    currentUser?: CurrentUserShape | null;
    currentUserRole?: string | null | undefined;
}

export interface NavCategoryProps {
    id: string;
    name: string;
    image_url: string;
    selected?: boolean;
}

export interface CategoriesProps {
    categories: Array<{
        id: string;
        name: string;
        image_url?: string | null;
        selected?: boolean;
    }>;
}

export interface FooterListProps {
    children: ReactNode;
}

export interface AdminNavItemProps {
    selected?: boolean;
    icon: IconType;
    label: string;
}
