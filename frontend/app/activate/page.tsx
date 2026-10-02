'use client';

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MdAutoAwesome, MdCheckCircle, MdError } from "react-icons/md";
import { useFragmentToken } from "@/hooks/useFragmentToken";
import { AuthApi } from "@/lib/auth-api";
import { ApiError } from "@/lib/api-error";

type Status = "loading" | "success" | "error";

const MISSING_TOKEN = "This activation link is incomplete. Open the link from your email again.";
const REDIRECT_DELAY_MS = 2500;

/**
 * Landing page of the verification email: `/activate#token=…`.
 *
 * The token is read from the URL fragment and posted in the request body,
 * so it never reaches a server log. Verifying does not sign the user in: the
 * backend returns no session, so the page sends them on to /login.
 */
export default function ActivatePage() {
    const token = useFragmentToken();
    const router = useRouter();
    const [status, setStatus] = useState<Status>("loading");
    const [message, setMessage] = useState("");
    // The token is single-use: StrictMode's second effect run (development)
    // would spend a second request and race the first one's answer.
    const submitted = useRef<string | null>(null);

    useEffect(() => {
        if (token === undefined) return; // fragment not read yet
        if (token === null) {
            setMessage(MISSING_TOKEN);
            setStatus("error");
            return;
        }
        if (submitted.current === token) return;
        submitted.current = token;

        AuthApi.activate(token)
            .then(result => {
                setMessage(`${result.email} is verified. Sign in to continue.`);
                setStatus("success");
                setTimeout(() => router.push("/login"), REDIRECT_DELAY_MS);
            })
            .catch((error: unknown) => {
                setMessage(ApiError.from(error, "Activation failed.").message);
                setStatus("error");
            });
    }, [token, router]);

    return (
        <div className="min-h-screen flex items-center justify-center p-6">
            <div className="liquid-glass max-w-[480px] w-full p-10 flex flex-col items-center gap-6 text-center">
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
                            <h1 className="font-display-lg text-headline-lg text-primary">Email Verified!</h1>
                            <p className="font-body-md text-sm text-secondary">{message}</p>
                        </div>
                        <Link
                            href="/login"
                            className="w-full bg-brand-lime text-primary py-4 px-8 rounded-2xl font-label-bold hover:shadow-xl transition-all active:scale-95"
                        >
                            Sign In
                        </Link>
                    </>
                )}

                {status === "error" && (
                    <>
                        <MdError className="text-red-400" size={56} />
                        <div className="space-y-2">
                            <h1 className="font-display-lg text-headline-lg text-primary">Activation Failed</h1>
                            <p className="font-body-md text-sm text-secondary">{message}</p>
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
