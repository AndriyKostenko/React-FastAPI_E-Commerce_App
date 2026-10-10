import { Action, ActionContext, ActionRequest, RecordActionResponse } from 'adminjs';

import { Components } from '../admin/component-loader.js';
import { GatewayError } from '../gateway/gateway-client.js';
import { isJsonObject, JsonObject, JsonValue } from '../gateway/json.js';
import { ApiResource } from './api-resource.js';

/** One input of a workflow form (rendered by components/WorkflowForm.tsx). */
export interface FormField {
    readonly name: string;
    readonly label: string;
    readonly kind: 'text' | 'textarea' | 'boolean' | 'number' | 'refund-lines';
    readonly required?: boolean;
    readonly help?: string;
}

/** What the gateway is asked to do for one record. */
export interface WorkflowCall {
    readonly method: 'POST' | 'PATCH';
    readonly path: string;
    readonly body?: JsonValue;
}

export interface WorkflowActionSpec {
    readonly name: string;
    readonly label: string;
    readonly icon?: string;
    readonly variant?: 'primary' | 'danger' | 'success';
    // Shown above the form: what the action does and what it sets off.
    readonly description: string;
    readonly fields?: readonly FormField[];
    // Offered only for records in a state where the service would accept it.
    readonly isVisible?: (record: JsonObject) => boolean;
    readonly call: (record: JsonObject, input: JsonObject) => WorkflowCall;
    // Data the form needs beyond the record, fetched when it opens (e.g. an order's lines).
    readonly load?: (record: JsonObject, resource: ApiResource, context: ActionContext) => Promise<JsonObject>;
    readonly success: string;
}

/**
 * A record action that runs one of a service's workflows through the
 * gateway (refund, approve a return, mark a print job shipped...).
 *
 * The service decides: it applies its own rules and state machine, emits its
 * events and sends its emails. admin-js only collects the input and shows the
 * outcome, refusals included, verbatim.
 *
 * Every workflow has a form and acts only on POST, even when the form is just
 * a confirmation: AdminJS calls actions without a component with GET, and a
 * GET must never move money or goods.
 */
export class WorkflowAction {
    constructor(private readonly spec: WorkflowActionSpec) {}

    build(resource: ApiResource): Partial<Action<RecordActionResponse>> {
        const { spec } = this;
        return {
            actionType: 'record',
            icon: spec.icon,
            variant: spec.variant ?? 'primary',
            component: Components.WorkflowForm,
            custom: { label: spec.label, description: spec.description, fields: spec.fields ?? [] },
            isVisible: ({ record }) => !!record && (spec.isVisible?.(record.params as JsonObject) ?? true),
            handler: async (request: ActionRequest, _response: unknown, context: ActionContext): Promise<RecordActionResponse> => {
                const { record, currentAdmin, h } = context;
                if (!record) throw new Error('No record');
                if (request.method !== 'post') {
                    const formData = spec.load ? await spec.load(record.params as JsonObject, resource, context) : {};
                    return { record: record.toJSON(currentAdmin), formData };
                }
                const input = WorkflowAction.input(request.payload);
                const missing = (spec.fields ?? []).filter((field) => field.required && WorkflowAction.blank(input[field.name]));
                if (missing.length > 0) {
                    return {
                        record: record.toJSON(currentAdmin),
                        notice: { message: `Fill in: ${missing.map((field) => field.label).join(', ')}`, type: 'error' },
                    };
                }
                const call = spec.call(record.params as JsonObject, input);
                try {
                    await resource.api.send(currentAdmin, call.path, { method: call.method, body: call.body });
                } catch (error) {
                    const message = error instanceof GatewayError ? error.detail : (error as Error).message;
                    return { record: record.toJSON(currentAdmin), notice: { message, type: 'error' } };
                }
                const refreshed = await resource.findOne(String(record.id()), context);
                return {
                    record: (refreshed ?? record).toJSON(currentAdmin),
                    notice: { message: spec.success, type: 'success' },
                    redirectUrl: h.recordActionUrl({ resourceId: resource.id(), recordId: String(record.id()), actionName: 'show' }),
                };
            },
        };
    }

    /** The form's fields arrive as one JSON string (see WorkflowForm.tsx). */
    private static input(payload: Record<string, unknown> | undefined): JsonObject {
        const raw = payload?.input;
        if (typeof raw !== 'string') return {};
        try {
            const parsed: JsonValue = JSON.parse(raw);
            return isJsonObject(parsed) ? parsed : {};
        } catch {
            return {};
        }
    }

    private static blank(value: JsonValue | undefined): boolean {
        return value === undefined || value === null || (typeof value === 'string' && value.trim() === '')
            || (Array.isArray(value) && value.length === 0);
    }
}

/** Trimmed text input, or null when left empty. */
export const text = (input: JsonObject, name: string): string | null => {
    const value = input[name];
    return typeof value === 'string' && value.trim() ? value.trim() : null;
};

export interface RecordViewSpec {
    readonly name: string;
    readonly label: string;
    readonly icon?: string;
    readonly component: string;
    readonly isVisible?: (record: JsonObject) => boolean;
    // Fetched when the view opens and handed to its component as `formData`.
    readonly load: (record: JsonObject, resource: ApiResource, context: ActionContext) => Promise<JsonObject>;
}

/**
 * A read-only record view with its own component (print file, packing slip,
 * return photos). Its handler only ever reads.
 */
export class RecordView {
    constructor(private readonly spec: RecordViewSpec) {}

    build(resource: ApiResource): Partial<Action<RecordActionResponse>> {
        const { spec } = this;
        return {
            actionType: 'record',
            icon: spec.icon,
            component: spec.component,
            isVisible: ({ record }) => !!record && (spec.isVisible?.(record.params as JsonObject) ?? true),
            handler: async (_request: ActionRequest, _response: unknown, context: ActionContext): Promise<RecordActionResponse> => {
                const { record, currentAdmin } = context;
                if (!record) throw new Error('No record');
                try {
                    const formData = await spec.load(record.params as JsonObject, resource, context);
                    return { record: record.toJSON(currentAdmin), formData };
                } catch (error) {
                    const message = error instanceof GatewayError ? error.detail : (error as Error).message;
                    return { record: record.toJSON(currentAdmin), formData: {}, notice: { message, type: 'error' } };
                }
            },
        };
    }
}
