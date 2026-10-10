/** JSON as it crosses the wire, without falling back to `any`. */
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | JsonObject;
export interface JsonObject {
    [key: string]: JsonValue;
}

export const isJsonObject = (value: JsonValue | undefined): value is JsonObject =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

/** Parse a request/response body that must be a JSON object. */
export const parseJsonObject = (text: string): JsonObject => {
    const parsed: JsonValue = JSON.parse(text);
    if (!isJsonObject(parsed)) {
        throw new SyntaxError('Expected a JSON object');
    }
    return parsed;
};
