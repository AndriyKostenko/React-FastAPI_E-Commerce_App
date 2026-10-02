import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import type {
    ActivationRequest,
    EmailVerificationResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    PasswordUpdateResponse,
    ResetPasswordRequest,
} from "@/types/auth";

/**
 * The public account calls behind the email links: verify an email address,
 * ask for a password reset, set the new password.
 *
 * Tokens always travel in the JSON body, never the URL. Failures throw an
 * ApiError carrying the backend's own message.
 */
export class AuthApi {
    static activate(token: string): Promise<EmailVerificationResponse> {
        return AuthApi.post<ActivationRequest, EmailVerificationResponse>(
            settings.api.endpoints.activate,
            { token },
            "The activation link is invalid or has expired.",
        );
    }

    static requestPasswordReset(email: string): Promise<ForgotPasswordResponse> {
        return AuthApi.post<ForgotPasswordRequest, ForgotPasswordResponse>(
            settings.api.endpoints.forgotPassword,
            { email },
            "Could not send the reset email. Please try again.",
        );
    }

    static resetPassword(token: string, newPassword: string): Promise<PasswordUpdateResponse> {
        return AuthApi.post<ResetPasswordRequest, PasswordUpdateResponse>(
            settings.api.endpoints.passwordReset,
            { token, new_password: newPassword },
            "The reset link is invalid or has expired.",
        );
    }

    private static async post<TRequest, TResponse>(url: string, body: TRequest, fallback: string): Promise<TResponse> {
        let response: Response;
        try {
            response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
        } catch (error) {
            throw ApiError.from(error, fallback);
        }
        if (!response.ok) throw await ApiError.fromResponse(response, fallback);
        return (await response.json()) as TResponse;
    }
}
