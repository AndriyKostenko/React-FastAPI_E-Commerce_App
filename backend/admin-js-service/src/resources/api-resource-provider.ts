import AdminJS, {
    BaseResource,
    BaseRecord,
    BaseProperty,
    Filter,
    ActionContext,
    ParamsType,
    PropertyType,
    ResourceOptions,
} from 'adminjs';

/** One field as returned by the services' admin-only /admin/schema/* routes. */
interface AdminSchemaField {
    path: string;
    type: PropertyType;
    isId: boolean;
}

interface AdminSchemaResponse {
    fields?: AdminSchemaField[];
}

export class ApiResourceProvider extends BaseResource {
    private dataEndpoint: string;

    private schemaEndpoint: string;

    private resourceName: string;

    private databaseTypeValue: string;

    // Until an admin's token lets us read the real schema, expose only the id.
    private cachedProperties: BaseProperty[] = [
        new BaseProperty({ path: 'id', type: 'string', isId: true }),
    ];

    private usesFormData: boolean;

    private schemaLoaded = false;

    private schemaLoading: Promise<void> | null = null;

    // Kept so the resource can be re-decorated once its schema arrives:
    // AdminJS reads properties() only when the decorator is built.
    private adminInstance: AdminJS | null = null;

    private resourceOptions: ResourceOptions = {};

    constructor(
        dataEndpoint: string,
        schemaEndpoint: string,
        resourceName: string,
        databaseType: string,
        usesFormData = false,
    ) {
        super();
        this.dataEndpoint = dataEndpoint;
        this.schemaEndpoint = schemaEndpoint;
        this.resourceName = resourceName;
        this.databaseTypeValue = databaseType;
        this.usesFormData = usesFormData;
    }

    override assignDecorator(admin: AdminJS, options: ResourceOptions = {}): void {
        this.adminInstance = admin;
        this.resourceOptions = options;
        super.assignDecorator(admin, this.withSchemaProperties(options));
    }

    /**
     * Load the admin-only field schema with the given admin token, once.
     *
     * Concurrent callers share one request; a failure leaves the id-only
     * fallback in place and lets the next call retry.
     */
    public async ensureSchema(token: string): Promise<void> {
        if (this.schemaLoaded) return;
        if (!this.schemaLoading) {
            this.schemaLoading = this.loadSchema(token).finally(() => {
                this.schemaLoading = null;
            });
        }
        await this.schemaLoading;
    }

    private async loadSchema(token: string): Promise<void> {
        try {
            const schema: AdminSchemaResponse = await this.fetchApi(this.schemaEndpoint, undefined, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!schema.fields?.length) {
                console.warn(`No fields for ${this.resourceName}`);
                return;
            }

            this.cachedProperties = schema.fields.map((field) => new BaseProperty({
                path: field.path,
                type: field.type,
                isId: field.isId,
            }));
            this.schemaLoaded = true;
            this.redecorate();
        } catch (error) {
            console.error(`Failed to load schema for ${this.resourceName}:`, error);
        }
    }

    /** Rebuild the AdminJS decorator so the freshly loaded properties are used. */
    private redecorate(): void {
        if (this.adminInstance) {
            super.assignDecorator(this.adminInstance, this.withSchemaProperties(this.resourceOptions));
        }
    }

    /** Generated per-field config, with any explicitly configured overrides on top. */
    private withSchemaProperties(options: ResourceOptions): ResourceOptions {
        return {
            ...options,
            properties: { ...this.generateAdminPropertiesConfig(), ...options.properties },
        };
    }

    /** Fallback for sessions that outlived a restart and so skipped the login hook. */
    private async ensureSchemaFor(context?: ActionContext): Promise<void> {
        const token = context?.currentAdmin?.token;
        if (typeof token === 'string' && token) {
            await this.ensureSchema(token);
        }
    }

    databaseName(): string {
        return this.resourceName;
    }

    databaseType(): string {
        return this.databaseTypeValue;
    }

    name(): string {
        return this.resourceName;
    }

    id(): string {
        return this.resourceName;
    }

    properties(): BaseProperty[] {
        return this.cachedProperties;
    }

    property(path: string): BaseProperty | null {
        return this.cachedProperties.find((p) => p.path() === path) || null;
    }

    // eslint-disable-next-line class-methods-use-this
    private async fetchApi(
        endpoint: string,
        context?: ActionContext,
        options: RequestInit & {
            limit?: number;
            offset?: number;
            sort?: { sortBy?: string; direction?: 'asc' | 'desc' };
        } = {},
    ): Promise<any> {
        const token = context?.currentAdmin?.token;
        const url = `${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` }),
            ...options.headers,
        };
        try {
            const response = await fetch(url, { ...options, headers });
            console.log(`Fetching API at ${url} - Status: ${response.status}`);

            if (!response.ok) {
                // Try to extract error message from response
                let errorMessage = `API request failed with status ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch {
                    // If response is not JSON, use status text
                    errorMessage = `${errorMessage}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }
            // Handle 204 No Content (common for DELETE)
            if (response.status === 204) {
                return null;
            }
            return await response.json();
        } catch (error) {
            // Re-throw with more context if it's a network error
            if (error instanceof TypeError) {
                throw new Error(`Network error: Unable to reach ${url}`);
            }
            throw error;
        }
    }

    public async find(
        filter: Filter,
        options: { limit?: number; offset?: number; sort?: { sortBy?: string; direction?: 'asc' | 'desc' } },
        context?: ActionContext,
    ): Promise<BaseRecord[]> {
        try {
            await this.ensureSchemaFor(context);
            const {
                limit,
                offset,
                sort, ...fetchOptions
            } = options;
            const url = new URL(this.dataEndpoint);

            if (typeof limit === 'number') {
                url.searchParams.append('limit', limit.toString());
            }
            if (typeof offset === 'number') {
                url.searchParams.append('offset', offset.toString());
            }
            // if (sort?.sortBy) {
            //     url.searchParams.append('sort_by', sort.sortBy);
            //     url.searchParams.append('sort_order', sort.direction || 'asc');
            // }

            // eslint-disable-next-line max-len
            const rawFilters = (filter as unknown as { filters?: Record<string, {path: string; value: unknown}>}).filters ?? {};

            Object.values(rawFilters).forEach(({ path, value }) => {
                if (value === undefined || value === null || value === '') return;

                if (typeof value === 'object' && value !== null) {
                    const { from, to } = value as { from?: string; to?: string };
                    if (from) url.searchParams.append(`${path}_from`, from);
                    if (to) url.searchParams.append(`${path}_to`, to);
                    return;
                }

                url.searchParams.append(path, String(value));
            });

            console.log(`Fetching ${this.resourceName} with URL:`, url.toString());

            const data = await this.fetchApi(url.toString(), context, fetchOptions);

            // Handle different response formats
            let items: any[] = [];

            if (Array.isArray(data)) {
                items = data;
            } else if (data) {
                // Try to find array in response object using resource name
                const resourceKey = `${this.resourceName.toLowerCase()}s`; // e.g., "users", "products"
                items = data[resourceKey] || data.items || data.data || [];
            }

            console.log(`Found ${items.length} ${this.resourceName} records`);

            // DEBUG: Log the first item structure
            if (items.length > 0) {
                console.log(`Sample ${this.resourceName} record structure:`, JSON.stringify(items[0], null, 2));
                console.log('Available keys:', Object.keys(items[0]));
                // Add specific check for date fields
                console.log(`Date fields for ${this.resourceName}:`, {
                    date_created: items[0].date_created,
                    date_updated: items[0].date_updated,
                    date_created_type: typeof items[0].date_created,
                    date_updated_type: typeof items[0].date_updated,
                });
            }
            // Validate that each item has the required id field
            const validItems = items.filter((item) => {
                if (!item || typeof item !== 'object') {
                    console.warn(`Invalid item in ${this.resourceName}:`, item);
                    return false;
                }
                // Check if item has an ID field
                const hasId = 'id' in item || 'Id' in item || '_id' in item;
                if (!hasId) {
                    console.warn(`${this.resourceName} record missing ID field:`, item);
                    return false;
                }

                return true;
            });

            if (validItems.length !== items.length) {
                console.warn(`Filtered out ${items.length - validItems.length} invalid ${this.resourceName} records`);
            }

            return validItems.map((item) => new BaseRecord(item, this));
        } catch (error) {
            console.error(`Error fetching ${this.resourceName}:`, error);
            return [];
        }
    }

    private buildResourceUrl(id?: string): string {
        // Don't strip the resource name - the endpoint already contains it
        // e.g., this.endpoint = "http://api-gateway:8000/api/v1/users"
        console.log('Building resource URL - Endpoint:', this.dataEndpoint, 'ID:', id);
        return id ? `${this.dataEndpoint}/${id}` : this.dataEndpoint;
    }

    public async findOne(id: string, context?: ActionContext): Promise<BaseRecord | null> {
        try {
            await this.ensureSchemaFor(context);
            const url = this.buildResourceUrl(id);
            console.log(`Fetching single ${this.resourceName} from URL:`, url);
            const data = await this.fetchApi(url, context);
            return new BaseRecord(data, this);
        } catch (error) {
            console.error(`Error fetching ${this.resourceName} with id ${id}:`, error);
            return null;
        }
    }

    public async count(filter: Filter, context?: ActionContext): Promise<number> {
        try {
            const records = await this.find(filter, {}, context);
            return records.length;
        } catch (error) {
            console.error(`Error counting ${this.resourceName}:`, error);
            return 0;
        }
    }

    public async create(params: Record<string, any>, context?: ActionContext): Promise<ParamsType> {
        try {
            console.log(`Creating ${this.resourceName} with params:`, params);
            console.log('Context admin:', context?.currentAdmin);

            const token = context?.currentAdmin?.token;
            if (!token) {
                console.warn('No authentication token available for create operation');
            }
            // using FormData if specified
            if (this.usesFormData) {
                // Special handling for Form APIs
                const formData = new FormData();
                Object.entries(params).forEach(([key, value]) => {
                    if (value !== null && value !== undefined && value !== '') {
                        formData.append(key, String(value));
                    }
                });

                const headers: Record<string, string> = {};
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
                    console.log('Added Authorization header to FormData request');
                }

                const response = await fetch(this.dataEndpoint, {
                    method: 'POST',
                    headers,
                    body: formData,
                });

                if (!response.ok) {
                    throw new Error(`Failed: ${response.statusText}`);
                }

                return await response.json();
            }
            // Standard JSON approach
            const data = await this.fetchApi(this.dataEndpoint, context, {
                method: 'POST',
                body: JSON.stringify(params),
            });
            return data;
        } catch (error) {
            console.error(`Error creating ${this.resourceName}:`, error);
            // eslint-disable-next-line max-len
            throw new Error(`Failed to create ${this.resourceName}: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    public async update(id: string, params: Record<string, any>, context?: ActionContext): Promise<ParamsType> {
        try {
            const { id: _id, ...updateData } = params;

            // filtering out empty strings, nulls, undefined values and read-only fields
            const cleanedData = Object.entries(updateData).reduce((acc, [key, value]) => {
                const skipFields = ['date_created', 'date_updated', 'id', 'is_verified', 'is_active', 'email'];
                if (!skipFields.includes(key) && value !== undefined && value !== null && value !== '') {
                    acc[key] = value;
                }
                return acc;
            }, {} as Record<string, any>);
            console.log(`Updating ${this.resourceName} with id ${id}:`, cleanedData);

            if (Object.keys(cleanedData).length === 0) {
                console.log(`No valid fields to update for ${this.resourceName} with id ${id}. Skipping API call.`);
                // Fetch and return current record instead of throwing error
                const current = await this.findOne(id, context);
                return current?.params || params;
            }

            const url = this.buildResourceUrl(id);
            const data = await this.fetchApi(url, context, {
                method: 'PATCH',
                body: JSON.stringify(cleanedData),
            });
            return data;
        } catch (error) {
            console.error(`Error updating ${this.resourceName} with id ${id}:`, error);
            // eslint-disable-next-line max-len
            throw new Error(`Failed to update ${this.resourceName}: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    public async delete(id: string, context?: ActionContext): Promise<void> {
        try {
            const url = this.buildResourceUrl(id);
            await this.fetchApi(url, context, {
                method: 'DELETE',
            });
            console.log(`Successfully deleted ${this.resourceName} with id ${id}`);
        } catch (error) {
            console.error(`Error deleting ${this.resourceName} with id ${id}:`, error);
            // eslint-disable-next-line max-len
            throw new Error(`Failed to delete ${this.resourceName}: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    public static isAdapterFor(rawResource: any): boolean {
        return false;
    }

    // Generates AdminJS properties configuration based on cached properties
    public generateAdminPropertiesConfig(): Record<string, any> {
        if (!this.cachedProperties || this.cachedProperties.length === 0) {
            console.warn(`No cached properties found for ${this.resourceName}.`);
            return {};
        }

        const config: Record<string, any> = {};

        // eslint-disable-next-line no-restricted-syntax
        for (const prop of this.cachedProperties) {
            const path = prop.path();

            config[path] = {
                isTitle: ['name', 'title', 'email'].includes(path),
                isVisible: {
                    list: true,
                    filter: true,
                    show: true,
                    edit: !prop.isId(),
                },
                isEditable: !prop.isId(),
            };

            // Optionally tweak special fields
            if (prop.type() === 'datetime' || path.includes('date')) {
                config[path].type = 'datetime';
                config[path].isEditable = false;
                config[path].isVisible = {
                    list: true, filter: true, show: true, edit: false,
                };
            }

            if (path === 'id') {
                config[path].isVisible = {
                    list: true, filter: true, show: true, edit: false,
                };
            }
        }
        return config;
    }
}
