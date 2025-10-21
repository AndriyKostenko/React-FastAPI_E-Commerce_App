import {
    BaseResource,
    BaseRecord,
    BaseProperty,
    Filter,
    ActionContext,
    ParamsType,
} from 'adminjs';

export class ApiResourceProvider extends BaseResource {
    private endpoint: string;

    private resourceName: string;

    private databaseTypeValue: string;

    constructor(endpoint: string, resourceName: string, databaseType: string) {
        super();
        this.endpoint = endpoint;
        this.resourceName = resourceName;
        this.databaseTypeValue = databaseType;
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
        return [
            new BaseProperty({ path: 'id', type: 'string', isId: true }),
            new BaseProperty({ path: 'name', type: 'string' }),
            new BaseProperty({ path: 'email', type: 'string' }),
            new BaseProperty({ path: 'role', type: 'string' }),
            new BaseProperty({ path: 'phone_number', type: 'string' }),
            new BaseProperty({ path: 'image', type: 'string' }),
            new BaseProperty({ path: 'is_active', type: 'boolean' }),
            new BaseProperty({ path: 'is_verified', type: 'boolean' }),
            new BaseProperty({ path: 'date_created', type: 'datetime' }),
            new BaseProperty({ path: 'date_updated', type: 'datetime' }),
        ];
    }

    property(path: string): BaseProperty | null {
        return this.properties().find((p) => p.path() === path) || null;
    }

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

    // Correct method signature
    public async find(
        filter: Filter,
        options: { limit?: number; offset?: number; sort?: { sortBy?: string; direction?: 'asc' | 'desc' } },
        context?: ActionContext,
    ): Promise<BaseRecord[]> {
        try {
            const { limit, offset, sort, ...fetchOptions } = options;
            const url = new URL(this.endpoint);

            if (typeof limit === 'number') {
                url.searchParams.append('limit', limit.toString());
            }
            if (typeof offset === 'number') {
                url.searchParams.append('offset', offset.toString());
            }
            if (sort?.sortBy) {
                url.searchParams.append('sortBy', sort.sortBy);
                url.searchParams.append('direction', sort.direction || 'asc');
            }

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
            const users = Array.isArray(data) ? data : data.users || [];
            return users.map((item) => new BaseRecord(item, this));
        } catch (error) {
            console.error(`Error fetching ${this.resourceName}:`, error);
            return [];
        }
    }

    private buildResourceUrl(id?: string): string {
        // Don't strip the resource name - the endpoint already contains it
        // e.g., this.endpoint = "http://api-gateway:8000/api/v1/users"
        console.log('Building resource URL - Endpoint:', this.endpoint, 'ID:', id);
        return id ? `${this.endpoint}/id/${id}` : this.endpoint;
    }

    public async findOne(id: string, context?: ActionContext): Promise<BaseRecord | null> {
        try {
            const url = this.buildResourceUrl(id);
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
            const data = await this.fetchApi(this.endpoint, context, {
                method: 'POST',
                body: JSON.stringify(params),
            });
            console.log(`Creating the ${this.resourceName}:`, data);
            return data;
        } catch (error) {
            console.error(`Error creating ${this.resourceName}:`, error);
            // Throw with user-friendly message - AdminJS will show it as toast
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            throw new Error(`Failed to create ${this.resourceName}: ${errorMessage}`);
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
                method: 'PUT',
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
}
