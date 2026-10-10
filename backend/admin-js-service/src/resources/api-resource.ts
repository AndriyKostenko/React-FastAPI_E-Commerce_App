import AdminJS, {
    ActionContext,
    BaseProperty,
    BaseRecord,
    BaseResource,
    Filter,
    ParamsType,
    PropertyType,
    ResourceOptions,
} from 'adminjs';

import { AdminGateway } from '../gateway/admin-gateway.js';
import { GatewayRequest } from '../gateway/gateway-client.js';
import { isJsonObject, JsonObject, JsonValue } from '../gateway/json.js';

/** One field, as the services' admin-only /admin/schema/* routes describe it. */
export interface FieldSpec {
    readonly path: string;
    readonly type: PropertyType;
    readonly isId?: boolean;
}

export interface WritePolicy {
    readonly create: boolean;
    readonly update: boolean;
    readonly delete: boolean;
}

export const READ_ONLY: WritePolicy = { create: false, update: false, delete: false };

export interface ApiResourceSpec {
    // AdminJS's id and label for the resource, e.g. "Orders".
    readonly name: string;
    // Gateway path of the list, e.g. "/orders"; one record is `${listPath}/${id}`.
    readonly listPath: string;
    readonly recordPath?: (id: string) => string;
    // Either a schema endpoint (fields come from the service's model) ...
    readonly schemaPath?: string;
    // ... or fields declared here.
    readonly fields?: readonly FieldSpec[];
    // Key of the array in a list response that is an object, when not the default ones.
    readonly listKey?: string;
    // Query parameter names for paging; null when the endpoint does not page.
    readonly paging?: { readonly limit: string; readonly offset: string } | null;
    readonly writes: WritePolicy;
    readonly updateMethod?: 'PATCH' | 'PUT';
    // Never sent on update (server-managed or identity fields).
    readonly readOnlyFields?: readonly string[];
}

/** Thrown into AdminJS, which shows the message to the admin. */
export class ApiResourceError extends Error {}

/**
 * An AdminJS resource backed by the API gateway rather than a database,
 * called as the signed-in admin (see AdminGateway).
 */
export class ApiResource extends BaseResource {
    private properties_: BaseProperty[];

    private schemaLoaded = false;

    private schemaLoading: Promise<void> | null = null;

    // Kept so the resource can be re-decorated once its schema arrives:
    // AdminJS reads properties() only when the decorator is built.
    private adminInstance: AdminJS | null = null;

    private resourceOptions: ResourceOptions = {};

    constructor(
        readonly spec: ApiResourceSpec,
        readonly api: AdminGateway,
    ) {
        super();
        this.properties_ = ApiResource.toProperties(spec.fields ?? [{ path: 'id', type: 'string', isId: true }]);
        this.schemaLoaded = !spec.schemaPath;
    }

    // ------------------------------ identity ------------------------------

    databaseName(): string {
        return 'api-gateway';
    }

    databaseType(): string {
        return 'API';
    }

    id(): string {
        return this.spec.name;
    }

    name(): string {
        return this.spec.name;
    }

    properties(): BaseProperty[] {
        return this.properties_;
    }

    property(path: string): BaseProperty | null {
        return this.properties_.find((property) => property.path() === path) ?? null;
    }

    static isAdapterFor(): boolean {
        return false;
    }

    override assignDecorator(admin: AdminJS, options: ResourceOptions = {}): void {
        this.adminInstance = admin;
        this.resourceOptions = options;
        super.assignDecorator(admin, this.withFieldOptions(options));
    }

    // ------------------------------- schema -------------------------------

    /** Load the admin-only field schema once (after sign-in; see SchemaRegistry). */
    async ensureSchema(accessToken: string): Promise<void> {
        if (this.schemaLoaded || !this.spec.schemaPath) return;
        if (!this.schemaLoading) {
            this.schemaLoading = this.loadSchema(this.spec.schemaPath, accessToken).finally(() => {
                this.schemaLoading = null;
            });
        }
        await this.schemaLoading;
    }

    private async loadSchema(schemaPath: string, accessToken: string): Promise<void> {
        try {
            const schema = await this.api.client.send(schemaPath, { accessToken });
            const fields = isJsonObject(schema) ? schema.fields : null;
            if (!Array.isArray(fields) || fields.length === 0) return;
            this.properties_ = ApiResource.toProperties(fields.filter(isJsonObject).map((field) => ({
                path: String(field.path),
                type: String(field.type) as PropertyType,
                isId: field.isId === true,
            })));
            this.schemaLoaded = true;
            if (this.adminInstance) {
                super.assignDecorator(this.adminInstance, this.withFieldOptions(this.resourceOptions));
            }
        } catch (error) {
            console.error(`admin-js: could not load the ${this.spec.name} schema: ${(error as Error).message}`);
        }
    }

    // -------------------------------- reads -------------------------------

    async find(
        filter: Filter,
        options: { limit?: number; offset?: number },
        context?: ActionContext,
    ): Promise<BaseRecord[]> {
        await this.ensureSchemaFor(context);
        const query = this.filterQuery(filter);
        if (this.spec.paging !== null) {
            const paging = this.spec.paging ?? { limit: 'limit', offset: 'offset' };
            if (typeof options.limit === 'number') query.set(paging.limit, String(options.limit));
            if (typeof options.offset === 'number') query.set(paging.offset, String(options.offset));
        }
        const body = await this.call(context, this.spec.listPath, { query });
        return this.items(body).map((item) => new BaseRecord(item, this));
    }

    async findOne(id: string, context?: ActionContext): Promise<BaseRecord | null> {
        await this.ensureSchemaFor(context);
        const body = await this.call(context, this.recordPath(id));
        return isJsonObject(body) ? new BaseRecord(body, this) : null;
    }

    async findMany(ids: (string | number)[], context?: ActionContext): Promise<BaseRecord[]> {
        const records = await Promise.all(ids.map((id) => this.findOne(String(id), context)));
        return records.filter((record): record is BaseRecord => record !== null);
    }

    /**
     * The list endpoints return a page, not a total, so the count is what one
     * page of up to 100 holds: exact for small lists, a floor for longer ones.
     */
    async count(filter: Filter, context?: ActionContext): Promise<number> {
        const query = this.filterQuery(filter);
        if (this.spec.paging !== null) query.set((this.spec.paging ?? { limit: 'limit' }).limit, '100');
        return this.items(await this.call(context, this.spec.listPath, { query })).length;
    }

    // ------------------------------- writes -------------------------------

    async create(params: ParamsType, context?: ActionContext): Promise<ParamsType> {
        this.require('create');
        const body = await this.call(context, this.spec.listPath, { method: 'POST', body: ApiResource.toJson(params) });
        return isJsonObject(body) ? body : {};
    }

    async update(id: string, params: ParamsType, context?: ActionContext): Promise<ParamsType> {
        this.require('update');
        const skip = new Set(['id', 'date_created', 'date_updated', ...(this.spec.readOnlyFields ?? [])]);
        const changes = Object.fromEntries(
            Object.entries(ApiResource.toJson(params)).filter(([key, value]) => !skip.has(key) && value !== '' && value !== null),
        );
        if (Object.keys(changes).length === 0) {
            return (await this.findOne(id, context))?.params ?? {};
        }
        const body = await this.call(context, this.recordPath(id), { method: this.spec.updateMethod ?? 'PATCH', body: changes });
        return isJsonObject(body) ? body : {};
    }

    async delete(id: string, context?: ActionContext): Promise<void> {
        this.require('delete');
        await this.call(context, this.recordPath(id), { method: 'DELETE' });
    }

    // ------------------------------- helpers ------------------------------

    /** Sessions that outlived a restart skipped the post-login schema load. */
    private async ensureSchemaFor(context?: ActionContext): Promise<void> {
        if (this.schemaLoaded || !context?.currentAdmin) return;
        await this.ensureSchema(await this.api.accessTokenFor(context.currentAdmin));
    }

    recordPath(id: string): string {
        return this.spec.recordPath ? this.spec.recordPath(id) : `${this.spec.listPath}/${encodeURIComponent(id)}`;
    }

    private async call(
        context: ActionContext | undefined,
        path: string,
        request: Omit<GatewayRequest, 'accessToken'> = {},
    ): Promise<JsonValue | null> {
        try {
            return await this.api.send(context?.currentAdmin, path, request);
        } catch (error) {
            throw new ApiResourceError(`${this.spec.name}: ${(error as Error).message}`);
        }
    }

    private require(write: keyof WritePolicy): void {
        if (!this.spec.writes[write]) throw new ApiResourceError(`${this.spec.name} cannot be changed with "${write}" here`);
    }

    private filterQuery(filter: Filter): URLSearchParams {
        const query = new URLSearchParams();
        Object.values(filter.filters ?? {}).forEach(({ path, value }) => {
            if (value === undefined || value === null || value === '') return;
            if (typeof value === 'object') {
                const range = value as { from?: string; to?: string };
                if (range.from) query.append(`${path}_from`, range.from);
                if (range.to) query.append(`${path}_to`, range.to);
                return;
            }
            query.append(path, String(value));
        });
        return query;
    }

    private items(body: JsonValue | null): JsonObject[] {
        let list: JsonValue | undefined;
        if (Array.isArray(body)) {
            list = body;
        } else if (isJsonObject(body)) {
            const key = this.spec.listKey;
            list = (key && body[key]) || body.items || body.data || body.jobs || body.results;
        }
        return Array.isArray(list) ? list.filter(isJsonObject).filter((item) => 'id' in item) : [];
    }

    /** Generated per-field options, with anything configured explicitly on top. */
    private withFieldOptions(options: ResourceOptions): ResourceOptions {
        const generated: NonNullable<ResourceOptions['properties']> = {};
        this.properties_.forEach((property) => {
            const path = property.path();
            const isDate = property.type() === 'datetime' || path.startsWith('date_') || path.endsWith('_at');
            generated[path] = {
                isTitle: ['name', 'title', 'email'].includes(path),
                type: isDate ? 'datetime' : undefined,
                isVisible: { list: true, filter: true, show: true, edit: !property.isId() && !isDate },
            };
        });
        return { ...options, properties: { ...generated, ...options.properties } };
    }

    private static toProperties(fields: readonly FieldSpec[]): BaseProperty[] {
        return fields.map((field) => new BaseProperty({ path: field.path, type: field.type, isId: field.isId ?? field.path === 'id' }));
    }

    /** AdminJS's flat params, as JSON for the gateway. */
    private static toJson(params: ParamsType): JsonObject {
        return JSON.parse(JSON.stringify(params)) as JsonObject;
    }
}
