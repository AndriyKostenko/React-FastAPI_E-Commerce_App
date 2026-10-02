'use client';

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import { MdAutoAwesome, MdError, MdVisibility, MdVisibilityOff } from "react-icons/md";
import Input from "@/components/ui/Input";
import { useFragmentToken } from "@/hooks/useFragmentToken";
import { AuthApi } from "@/lib/auth-api";
import { ApiError } from "@/lib/api-error";

// Mirrors ResetPasswordRequest.new_password in user-service.
const PASSWORD_RULES = {
    minLength: { value: 8, message: "At least 8 characters" },
    maxLength: { value: 100, message: "At most 100 characters" },
};

/**
 * Landing page of the password-reset email: `/password-reset#token=…`.
 * The token comes from the URL fragment and goes to the backend in the body.
 */
const ResetPasswordForm = () => {
    const token = useFragmentToken();
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const { register, handleSubmit, setError, formState: { errors } } = useForm<FieldValues>({
        defaultValues: { password: "", repeatedPassword: "" },
    });

    const onSubmit: SubmitHandler<FieldValues> = async (data) => {
        if (!token) return;
        if (data.password !== data.repeatedPassword) {
            setError("repeatedPassword", { type: "validate", message: "Passwords do not match" });
            return;
        }
        setIsLoading(true);
        try {
            await AuthApi.resetPassword(token, String(data.password));
            toast.success("Password updated. Sign in with your new password.");
            router.push("/login");
        } catch (error) {
            const apiError = ApiError.from(error, "The reset link is invalid or has expired.");
            // The backend names the field new_password; this form calls it password.
            const fieldError = apiError.fieldErrors.find(e => e.field === "new_password");
            if (fieldError) setError("password", { type: "server", message: fieldError.message });
            else toast.error(apiError.message);
        } finally {
            setIsLoading(false);
        }
    };

    const badge = (
        <div className="inline-flex items-center bg-white/70 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
            <MdAutoAwesome className="text-[14px] text-primary" />
            <span className="font-label-bold text-[11px] uppercase tracking-wider text-primary">Password Reset</span>
        </div>
    );

    if (token === undefined) {
        return (
            <>
                {badge}
                <div className="w-12 h-12 rounded-full border-4 border-brand-lime border-t-transparent animate-spin" />
            </>
        );
    }

    if (token === null) {
        return (
            <>
                {badge}
                <MdError className="text-red-400" size={56} />
                <div className="text-center space-y-1.5">
                    <h1 className="font-display-lg text-headline-lg text-primary">Link Incomplete</h1>
                    <p className="font-body-md text-sm text-secondary">
                        This reset link has no token. Open the link from your email again, or ask for a new one.
                    </p>
                </div>
                <Link
                    href="/forgot-password"
                    className="w-full text-center bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95"
                >
                    Send a New Link
                </Link>
            </>
        );
    }

    return (
        <>
            {badge}
            <div className="text-center space-y-1.5">
                <h1 className="font-display-lg text-headline-lg text-primary">Choose a New Password</h1>
                <p className="font-body-md text-sm text-secondary">You will sign in with it from now on.</p>
            </div>

            <div className="w-full relative">
                <Input
                    id="password"
                    label="New Password"
                    type={showPassword ? "text" : "password"}
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    validationRules={PASSWORD_RULES}
                    required
                    glass
                />
                <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-[30px] -translate-y-1/2 text-secondary hover:text-primary transition-colors"
                    tabIndex={-1}
                >
                    {showPassword ? <MdVisibilityOff size={20} /> : <MdVisibility size={20} />}
                </button>
            </div>

            <div className="w-full">
                <Input
                    id="repeatedPassword"
                    label="Repeat New Password"
                    type={showPassword ? "text" : "password"}
                    disabled={isLoading}
                    register={register}
                    errors={errors}
                    required
                    glass
                />
            </div>

            <button
                onClick={handleSubmit(onSubmit)}
                disabled={isLoading}
                className="w-full bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100"
            >
                {isLoading ? "Saving..." : "Set New Password"}
            </button>

            <p className="font-body-md text-sm text-secondary">
                <Link href="/login" className="text-primary font-semibold underline underline-offset-2 hover:opacity-70 transition-opacity">
                    Back to Sign In
                </Link>
            </p>
        </>
    );
};

export default ResetPasswordForm;
