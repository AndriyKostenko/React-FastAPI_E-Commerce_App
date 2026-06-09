"use client";

import { InputProps } from "@/types/inputs";

const Input: React.FC<InputProps> = ({
    id,
    label,
    type,
    disabled,
    required,
    register,
    errors,
    validationRules,
    glass,
}) => {
    if (glass) {
        return (
            <div className="w-full relative">
                <input
                    className={`peer
                                w-full
                                p-4
                                pt-6
                                outline-none
                                bg-white/40
                                font-light
                                border
                                rounded-2xl
                                transition
                                disabled:opacity-70
                                disabled:cursor-not-allowed
                                focus:ring-2
                                focus:ring-brand-lime
                                focus:ring-offset-0
                                ${errors[id] ? "border-rose-400 focus:ring-rose-400" : "border-white/30 focus:border-transparent"}`}
                    autoComplete="off"
                    id={id}
                    disabled={disabled}
                    {...register(id, { required, ...validationRules })}
                    placeholder=""
                    type={type}
                />
                <label
                    htmlFor={id}
                    className={`absolute
                                cursor-text
                                text-md
                                duration-150
                                transform
                                -translate-y-3
                                top-5
                                z-10
                                origin-[0]
                                left-4
                                peer-placeholder-shown:scale-100
                                peer-placeholder-shown:translate-y-0
                                peer-focus:scale-75
                                peer-focus:-translate-y-4
                                ${errors[id] ? "text-rose-500" : "text-secondary"}`}
                >
                    {label}
                </label>
            </div>
        );
    }

    return (
        <div className="w-full relative">
            <input
                className={`peer
                                w-full
                                p-4
                                pt-6
                                outline-none
                                bg-surface-container-low
                                font-light
                                border
                                rounded-lg
                                transition
                                disabled:opacity-70
                                disabled:cursor-not-allowed
                                ${errors[id] ? "border-rose-400" : "border-outline-variant"}
                                ${errors[id] ? "focus:border-rose-400" : "focus:border-primary"}`}
                autoComplete="off"
                id={id}
                disabled={disabled}
                {...register(id, { required, ...validationRules })}
                placeholder=""
                type={type}
            />
            <label
                htmlFor={id}
                className={`absolute
                                                cursor-text
                                                text-md
                                                duration-150
                                                transform
                                                -translate-y-3
                                                top-5
                                                z-10
                                                origin-[0]
                                                left-4
                                                peer-placeholder-shown:scale-100
                                                peer-placeholder-shown:translate-y-0
                                                peer-focus:scale-75
                                                peer-focus:-translate-y-4
                                                ${errors[id] ? "text-rose-500" : "text-secondary"}`}
            >
                {label}
            </label>
        </div>
    );
};

export default Input;
