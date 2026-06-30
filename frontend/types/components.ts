import type { MouseEvent, ReactNode } from "react";
import type { IconType } from "react-icons";

export interface ContainerProps {
    children: ReactNode;
}

export interface HeadingProps {
    title: string;
    center?: boolean;
}

export interface AvatarProps {
    src?: string | null | undefined;
}

export interface ActionBtnProps {
    icon: IconType;
    
    variant?: "default" | "keyboard" | "secondary";
    
}

export interface StatusProps {
    text: string;
    icon: IconType;
    background: string;
    color: string;
}

export interface NullDataProps {
    title: string;
}

import type { ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    label?: string;
    children?: ReactNode;

    outline?: boolean;
    /** @deprecated Use `size="sm"` instead. */
    small?: boolean;
    custom?: string;
    icon?: IconType;

    variant?: "default" | "keyboard" | "secondary";
    size?: "sm" | "md" | "lg";
}

export interface CartProviderProps {
    children: ReactNode;
}
