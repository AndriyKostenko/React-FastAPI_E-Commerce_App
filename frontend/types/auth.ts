import type { components } from "@/types/api/user";

// Request/response bodies of the email-link flows, from user-service's OpenAPI
// (regenerate with `npm run gen:api`).
type UserSchemas = components["schemas"];
export type ActivationRequest = UserSchemas["ActivationRequest"];
export type EmailVerificationResponse = UserSchemas["EmailVerificationResponse"];
export type ForgotPasswordRequest = UserSchemas["ForgotPasswordRequest"];
export type ForgotPasswordResponse = UserSchemas["ForgotPasswordResponse"];
export type ResetPasswordRequest = UserSchemas["ResetPasswordRequest"];
export type PasswordUpdateResponse = UserSchemas["PasswordUpdateResponse"];

export type CurrentUserShape = {
    name?: string | null | undefined;
    email?: string | null | undefined;
    image?: string | null | undefined;
};

export interface LoginFormProps {
    currentUser?: CurrentUserShape | null;
    /** A failed sign-in redirected here with this message (login page only). */
    authError?: string;
}

export type SearchParams = Record<string, string | string[] | undefined>;

export interface ReviewAuthorProps {
    id: string;
    name: string;
    email: string;
    role: string;
    image: string;
    createdAt: string;
}
