import type { FieldValues, RegisterOptions } from "react-hook-form";

// Field rules shared by the forms, each mirroring the backend schema it is
// sent to, so a value the server would refuse is caught before it is sent.
// The server still checks everything: these only save a round trip.

type Rules = RegisterOptions<FieldValues, string>;

const trimmed = (value: unknown): unknown => (typeof value === "string" ? value.trim() : value);

/** One "@", something on each side, a dot in the domain; 254 is the longest address mail allows. */
export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const EMAIL_RULES: Rules = {
    setValueAs: trimmed,
    pattern: { value: EMAIL_PATTERN, message: "Enter a valid email address" },
    maxLength: { value: 254, message: "At most 254 characters" },
};

/** UserSignUp.name / UserUpdate.name in user-service. */
export const NAME_RULES: Rules = {
    setValueAs: trimmed,
    minLength: { value: 2, message: "At least 2 characters" },
    maxLength: { value: 50, message: "At most 50 characters" },
};

/** A password being set (sign-up, reset, change): user-service takes 8 to 100 characters. */
export const NEW_PASSWORD_RULES: Rules = {
    minLength: { value: 8, message: "At least 8 characters" },
    maxLength: { value: 100, message: "At most 100 characters" },
};

/** A password being entered to sign in: only bounded, so old passwords still work. */
export const PASSWORD_RULES: Rules = {
    maxLength: { value: 100, message: "At most 100 characters" },
};

/** The repeat of `field`: must equal it. */
export const repeatOf = (field: string): Rules => ({
    validate: (value, values) => value === values[field] || "Passwords do not match",
});

/** CreateReview.comment in product-service. */
export const REVIEW_COMMENT_RULES: Rules = {
    setValueAs: trimmed,
    maxLength: { value: 5000, message: "At most 5000 characters" },
};
