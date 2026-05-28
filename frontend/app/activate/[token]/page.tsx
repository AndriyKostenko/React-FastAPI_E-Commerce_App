'use client';

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { settings } from "@/lib/config";
import Link from "next/link";
import { MdAutoAwesome, MdCheckCircle, MdError } from "react-icons/md";

type Status = "loading" | "success" | "error";

export default function ActivatePage() {
    const { token } = useParams<{ token: string }>();
    const router = useRouter();
    const [status, setStatus] = useState<Status>("loading");
    const [errorMessage, setErrorMessage] = useState("The activation link is invalid or has expired.");

    useEffect(() => {
        if (!token) return;

        async function activate() {
            try {
                const res = await fetch(settings.api.endpoints.activate(token), {
                    method: "POST",
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    setErrorMessage(data.detail ?? "Activation failed.");
                    setStatus("error");
                    return;
                }

                const data = await res.json();

                // Sign in automatically — the /me call inside the provider validates the token
                const result = await signIn("activation-token", {
                    redirect: false,
                    access_token: data.access_token,
                    user_role: data.user_role,
                    token_expiry: String(data.token_expiry),
                    user_id: data.user_id,
                    email: data.email,
                });

                if (result?.ok) {
                    setStatus("success");
                    setTimeout(() => router.push("/"), 2000);
                } else {
                    // Activation succeeded but session creation failed — still show success
                    setStatus("success");
                    setTimeout(() => router.push("/login"), 2000);
                }
            } catch {
                setErrorMessage("Could not reach the server. Please try again later.");
                setStatus("error");
            }
        }

        activate();
    }, [token, router]);

    return (
        <div className="min-h-screen flex items-center justify-center p-6">
            <div className="liquid-glass max-w-[480px] w-full p-10 flex flex-col items-center gap-6 text-center">
                {/* Brand badge */}
                <div className="inline-flex items-center bg-white/70 backdrop-blur rounded-full px-4 py-1.5 gap-2 border border-white/40">
                    <MdAutoAwesome className="text-[14px] text-primary" />
                    <span className="font-label-bold text-[11px] uppercase tracking-wider text-primary">
                        Email Verification
                    </span>
                </div>

                {status === "loading" && (
                    <>
                        <div className="w-12 h-12 rounded-full border-4 border-brand-lime border-t-transparent animate-spin" />
                        <p className="font-body-md text-sm text-secondary">Verifying your email...</p>
                    </>
                )}

                {status === "success" && (
                    <>
                        <MdCheckCircle className="text-brand-lime" size={56} />
                        <div className="space-y-2">
                            <h1 className="font-display-lg text-headline-lg text-primary">Account Activated!</h1>
                            <p className="font-body-md text-sm text-secondary">Signing you in automatically...</p>
                        </div>
                    </>
                )}

                {status === "error" && (
                    <>
                        <MdError className="text-red-400" size={56} />
                        <div className="space-y-2">
                            <h1 className="font-display-lg text-headline-lg text-primary">Activation Failed</h1>
                            <p className="font-body-md text-sm text-secondary">{errorMessage}</p>
                        </div>
                        <Link
                            href="/register"
                            className="w-full bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95"
                        >
                            Back to Register
                        </Link>
                    </>
                )}
            </div>
        </div>
    );
}
