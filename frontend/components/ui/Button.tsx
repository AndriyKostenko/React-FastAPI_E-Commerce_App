"use client";

import { ButtonProps } from "@/types/components";

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
    const isKeyboard = variant === "keyboard";
    const isSecondary = variant === "secondary";

    const baseStyles =
        "disabled:opacity-70 disabled:cursor-not-allowed transition-all w-full flex items-center justify-center gap-2 font-label-bold";

    const iconSize = {
        sm: 16,
        md: 24,
        lg: 28,
    } as const;

    const variantBaseStyles = {
        default: `rounded-md hover:opacity-80 border-primary ${
            outline ? "bg-white text-primary" : "bg-primary text-on-primary"
        }`,
        keyboard:
            "rounded-2xl bg-brand-lime text-primary shadow-[0_4px_0_0_rgba(132,204,22,1)] hover:shadow-[0_2px_0_0_rgba(132,204,22,1)] active:shadow-none active:translate-y-[4px]",
        secondary:
            "border border-primary/20 text-primary rounded-2xl w-auto hover:bg-white/40 active:scale-95",
    };

    const sizeClasses = {
        default: {
            sm: "text-sm font-light py-1 px-2 border-[1px]",
            md: "text-md font-semibold py-3 px-4 border-2",
            lg: "text-lg font-semibold py-4 px-6 border-2",
        },
        keyboard: {
            sm: "text-[10px] py-1 px-2",
            md: "text-xs py-1.5 md:py-2 px-2 md:px-4",
            lg: "text-sm md:text-base py-2.5 md:py-3 px-4 md:px-6",
        },
        secondary: {
            sm: "p-1.5",
            md: "p-2.5",
            lg: "p-3.5",
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
