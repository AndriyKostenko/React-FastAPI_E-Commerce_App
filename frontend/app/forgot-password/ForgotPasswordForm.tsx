'use client';

import { useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import { MdAutoAwesome, MdMarkEmailRead } from "react-icons/md";
import Input from "@/components/ui/Input";
import { AuthApi } from "@/lib/auth-api";
import { ApiError } from "@/lib/api-error";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Asks for a password-reset email. The answer is the same whether or not the
 * address has an account (the backend never says), so the form cannot be used
 * to find out who is registered.
 */
const ForgotPasswordForm = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [sentTo, setSentTo] = useState<string | null>(null);
    const { register, handleSubmit, formState: { errors } } = useForm<FieldValues>({
        defaultValues: { email: "" },
    });

    const onSubmit: SubmitHandler<FieldValues> = async (data) => {
        const email = String(data.email).trim();
        setIsLoading(true);
        try {
            await AuthApi.requestPasswordReset(email);
            setSentTo(email);
        } catch (error) {
            toast.error(ApiError.from(error, "Could not send the reset email. Please try again.").message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <div className="inline-flex items-center bg-white/70 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
                <MdAutoAwesome className="text-[14px] text-primary" />
                <span className="font-label-bold text-[11px] uppercase tracking-wider text-primary">Password Reset</span>
            </div>

            {sentTo ? (
                <>
                    <MdMarkEmailRead className="text-brand-lime" size={56} />
                    <div className="text-center space-y-1.5">
                        <h1 className="font-display-lg text-headline-lg text-primary">Check Your Email</h1>
                        <p className="font-body-md text-sm text-secondary">
                            If an account exists for {sentTo}, a link to reset the password is on its way.
                            It expires soon, so use it shortly.
                        </p>
                    </div>
                </>
            ) : (
                <>
                    <div className="text-center space-y-1.5">
                        <h1 className="font-display-lg text-headline-lg text-primary">Forgot Password?</h1>
                        <p className="font-body-md text-sm text-secondary">
                            Enter your account email and we&apos;ll send you a reset link.
                        </p>
                    </div>

                    <div className="w-full">
                        <Input
                            id="email"
                            label="Email"
                            type="email"
                            disabled={isLoading}
                            register={register}
                            errors={errors}
                            validationRules={{ pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address" } }}
                            required
                            glass
                        />
                    </div>

                    <button
                        onClick={handleSubmit(onSubmit)}
                        disabled={isLoading}
                        className="w-full bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100"
                    >
                        {isLoading ? "Sending..." : "Send Reset Link"}
                    </button>
                </>
            )}

            <p className="font-body-md text-sm text-secondary">
                Remembered it?{' '}
                <Link href="/login" className="text-primary font-semibold underline underline-offset-2 hover:opacity-70 transition-opacity">
                    Back to Sign In
                </Link>
            </p>
        </>
    );
};

export default ForgotPasswordForm;
