/**
 * The few checks lib/config.ts makes on public environment variables, written
 * to the Standard Schema interface that createEnv accepts.
 *
 * Instead of zod: config.ts runs in the browser on every page, and even
 * zod/mini added 17 KB (gzipped) to check six strings.
 */

/** The part of Standard Schema v1 (standardschema.dev) createEnv reads. */
export interface EnvSchema<Output> {
    readonly "~standard": {
        readonly version: 1;
        readonly vendor: string;
        readonly validate: (value: unknown) => { value: Output } | { issues: ReadonlyArray<{ message: string }> };
        readonly types?: { readonly input: unknown; readonly output: Output };
    };
}

type Check = (value: string) => string | null;

const schema = <Output>(validate: (value: unknown) => Output | { error: string }): EnvSchema<Output> => ({
    "~standard": {
        version: 1,
        vendor: "aigen-env",
        validate: (value) => {
            const result = validate(value);
            return typeof result === "object" && result !== null && "error" in result
                ? { issues: [{ message: result.error }] }
                : { value: result as Output };
        },
    },
});

const isUrl: Check = (value) => {
    try {
        new URL(value);
        return null;
    } catch {
        return "must be a URL";
    }
};

const isNonEmpty: Check = (value) => (value.length > 0 ? null : "must not be empty");

const required = (check: Check): EnvSchema<string> =>
    schema((value) => {
        if (typeof value !== "string") return { error: "is required" };
        const problem = check(value);
        return problem ? { error: problem } : value;
    });

const optional = (check: Check): EnvSchema<string | undefined> =>
    schema((value) => {
        if (value === undefined || value === "") return undefined;
        if (typeof value !== "string") return { error: "must be a string" };
        const problem = check(value);
        return problem ? { error: problem } : value;
    });

export const env = {
    url: () => required(isUrl),
    optionalUrl: () => optional(isUrl),
    text: () => required(isNonEmpty),
    optionalText: () => optional(isNonEmpty),
};
