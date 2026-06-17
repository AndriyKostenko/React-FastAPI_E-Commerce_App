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
    children,
    ...props
}) => {
    const isKeyboard = variant === "keyboard";
    const isSecondary = variant === "secondary";

    const baseStyles = "disabled:opacity-70 disabled:cursor-not-allowed transition-all w-full flex items-center justify-center gap-2 font-label-bold";

    const defaultStyles = `
        rounded-md
        hover:opacity-80
        border-primary
        ${outline ? "bg-white text-primary" : "bg-primary text-on-primary"}
        ${small ? "text-sm font-light py-1 px-2 border-[1px]" : "text-md font-semibold py-3 px-4 border-2"}
    `;

    const keyboardStyles = `
        rounded-2xl
        text-xs
        bg-brand-lime
        text-primary
        py-1.5 md:py-2
        px-2 md:px-4
        shadow-[0_4px_0_0_rgba(132,204,22,1)]
        hover:shadow-[0_2px_0_0_rgba(132,204,22,1)]
        active:shadow-none
        active:translate-y-[4px]
    `;

    const secondaryStyles = "border border-primary/20 text-primary p-2.5 rounded-2xl w-auto hover:bg-white/40 active:scale-95";

    return (
        <button
            {...props}
            className={`${isSecondary ? "" : baseStyles} ${isKeyboard ? keyboardStyles : isSecondary ? secondaryStyles : defaultStyles} ${custom ? custom : ""}`}
            type={type || "button"}
            disabled={disabled}
            onClick={onClick}
        >
            {Icon && <Icon size={24} />}
            {label}
            {children}
        </button>
    );
};

export default Button;
