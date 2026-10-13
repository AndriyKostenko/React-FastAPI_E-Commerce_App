"use client";

import { ButtonProps } from "@/types/components";

type ButtonSize = NonNullable<ButtonProps["size"]>;

const KEYBOARD_SIZE_CLASSES: Record<ButtonSize, string> = {
    sm: "text-[10px] py-1 px-2",
    md: "text-xs py-1.5 md:py-2 px-2 md:px-4",
    lg: "text-sm md:text-base py-2.5 md:py-3 px-4 md:px-6",
    xl: "text-base py-4 px-8",
};

/**
 * The keycap look (see `.keycap` in globals.css) as a class string, for
 * elements that cannot be a <Button> -- e.g. a next/link CTA that has to look
 * like one.
 */
export const keycapClassName = (size: ButtonSize = "lg"): string =>
    `keycap w-full flex items-center justify-center gap-2 font-label-bold text-center ${KEYBOARD_SIZE_CLASSES[size]}`;

const Button: React.FC<ButtonProps> = ({
    label,
    disabled,
    outline,
    small,
    custom,
    icon: Icon,
    type,
    onClick,
    variant = "default",
    size,
    children,
    ...props
}) => {
    const resolvedSize = size ?? (small ? "sm" : "md");
    const isSecondary = variant === "secondary";

    const baseStyles =
        "disabled:opacity-70 disabled:cursor-not-allowed transition-all w-full flex items-center justify-center gap-2 font-label-bold";

    const iconSize = {
        sm: 16,
        md: 24,
        lg: 28,
        xl: 32,
    } as const;

    const variantBaseStyles = {
        default: `rounded-md hover:opacity-80 border-primary ${
            outline ? "bg-white text-primary" : "bg-primary text-on-primary"
        }`,
        keyboard: "keycap",
        secondary:
            "border border-primary/20 text-primary rounded-2xl w-auto hover:bg-white/40 active:scale-95",
    };

    const sizeClasses = {
        default: {
            sm: "text-sm font-light py-1 px-2 border-[1px]",
            md: "text-md font-semibold py-3 px-4 border-2",
            lg: "text-lg font-semibold py-4 px-6 border-2",
            xl: "text-xl font-semibold py-5 px-8 border-2",
        },
        keyboard: KEYBOARD_SIZE_CLASSES,
        secondary: {
            sm: "p-1.5",
            md: "p-2.5",
            lg: "p-3.5",
            xl: "p-4",
        },
    };

    return (
        <button
            {...props}
            className={`${isSecondary ? "" : baseStyles} ${variantBaseStyles[variant]} ${sizeClasses[variant][resolvedSize]} ${custom ? custom : ""}`}
            type={type || "button"}
            disabled={disabled}
            onClick={onClick}
        >
            {Icon && <Icon size={iconSize[resolvedSize]} />}
            {label}
            {children}
        </button>
    );
};

export default Button;
