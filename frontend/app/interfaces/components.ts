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
    onClick: (event: MouseEvent<HTMLButtonElement>) => void;
    disabled?: boolean;
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

export interface ButtonProps {
    label: string;
    disabled?: boolean;
    outline?: boolean;
    small?: boolean;
    custom?: string;
    icon?: IconType;
    type?: "submit" | "button" | "reset";
    onClick: (event: MouseEvent<HTMLButtonElement>) => void;
}

export interface CartProviderProps {
    children: ReactNode;
}
