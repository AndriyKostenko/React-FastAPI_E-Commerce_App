// Error bodies the backend sends (backend/shared/app/errors.py and the gateway).

/** One Pydantic validation failure, keyed by the offending field's name. */
export interface ApiFieldError {
    field: string;
    message: string;
}

/** The gateway's rate limiter sends an object detail instead of a string. */
export interface ApiRateLimitDetail {
    message: string;
    retry_after: number;
}

export type ApiErrorDetail = string | ApiRateLimitDetail;

export interface ApiErrorPayload {
    detail?: ApiErrorDetail;
    /** Present on 422 validation responses only. */
    errors?: ApiFieldError[];
    timestamp?: string;
    path?: string;
}
