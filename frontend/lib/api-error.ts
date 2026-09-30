import type {
    ApiErrorDetail,
    ApiErrorPayload,
    ApiFieldError,
    ApiRateLimitDetail,
} from "@/types/api/error";

// ── Type guards (Validator) ──────────────────────────────────────────────────
// The body of a failed response is untrusted: it may be ours, the gateway's, or
// whatever else answered on that port, so every field is checked, never cast.

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value);

const isFieldError = (value: unknown): value is ApiFieldError =>
    isRecord(value) && typeof value.field === "string" && typeof value.message === "string";

const isRateLimitDetail = (value: unknown): value is ApiRateLimitDetail =>
    isRecord(value) && typeof value.message === "string" && typeof value.retry_after === "number";

const toPayload = (body: unknown): ApiErrorPayload => {
    if (!isRecord(body)) return {};
    const detail: ApiErrorDetail | undefined =
        typeof body.detail === "string" || isRateLimitDetail(body.detail) ? body.detail : undefined;
    const errors = Array.isArray(body.errors) ? body.errors.filter(isFieldError) : undefined;
    return { detail, errors };
};

// ── Status fallbacks (Strategy) ──────────────────────────────────────────────
// Used only when the body carries no message of its own.

const STATUS_FALLBACKS: Readonly<Record<number, string>> = {
    429: "Too many attempts. Please try again later.",
    502: "The service is temporarily unavailable. Please try again later.",
    503: "The service is temporarily unavailable. Please try again later.",
    504: "The service took too long to respond. Please try again later.",
};

const humanize = (field: string): string =>
    field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, " ");

/**
 * A failed backend call, carrying the message the backend itself produced.
 *
 * `message` is ready to show to the user; `fieldErrors` lets a form put each
 * validation message under its own input instead of in a toast.
 */
export class ApiError extends Error {
    readonly status: number;
    readonly fieldErrors: readonly ApiFieldError[];

    private constructor(message: string, status: number, fieldErrors: readonly ApiFieldError[] = []) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.fieldErrors = fieldErrors;
    }

    /** Build from a non-2xx response. `fallback` is used when the body says nothing usable. */
    static async fromResponse(response: Response, fallback: string): Promise<ApiError> {
        const body: unknown = await response.json().catch(() => null);
        const payload = toPayload(body);
        return new ApiError(ApiError.messageFor(payload, response.status, fallback), response.status, payload.errors);
    }

    /** fetch() itself threw: nothing answered, so there is no backend message. */
    static unreachable(): ApiError {
        return new ApiError("Cannot reach the server. Please check your connection and try again.", 0);
    }

    /** Normalise anything a `catch` receives into an ApiError. */
    static from(error: unknown, fallback: string): ApiError {
        if (error instanceof ApiError) return error;
        // A TypeError from fetch means the request never got a response.
        if (error instanceof TypeError) return ApiError.unreachable();
        return new ApiError(fallback, 0);
    }

    private static messageFor(payload: ApiErrorPayload, status: number, fallback: string): string {
        // 1. Validation: the per-field messages say far more than the generic
        //    "Validation request error" detail that accompanies them.
        if (payload.errors?.length) {
            return payload.errors.map(e => `${humanize(e.field)}: ${e.message}`).join("\n");
        }
        // 2. Rate limit: object detail with a wait time.
        if (isRateLimitDetail(payload.detail)) {
            const minutes = Math.ceil(payload.detail.retry_after / 60);
            return `Too many attempts. Please try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`;
        }
        // 3. Our own exceptions: the detail string is written for the user.
        if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
        return STATUS_FALLBACKS[status] ?? fallback;
    }
}
