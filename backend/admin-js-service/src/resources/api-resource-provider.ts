import { BaseResource, BaseRecord, BaseProperty, Filter, ActionContext, ParamsType } from 'adminjs';

export class ApiResourceProvider extends BaseResource {
    private endpoint: string;
    private resourceName: string;

    constructor(endpoint: string, resourceName: string) {
        super();
        this.endpoint = endpoint;
        this.resourceName = resourceName;
    }

    databaseName(): string {
        return 'API';
    }

    databaseType(): string {
        return 'REST API';
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

    private async fetchApi(url: string, context?: ActionContext, options: RequestInit = {}) {
        const token = context?.currentAdmin?.token;
        const headers = {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` }),
            ...options.headers,
        };

        const response = await fetch(url, { ...options, headers });
        if (!response.ok) throw new Error(`API request failed with status ${response.status}`);
        return response.json();
    }

    // Correct method signature
    public async find(
        filter: Filter,
        options: { limit?: number; offset?: number; sort?: { sortBy?: string; direction?: 'asc' | 'desc' } } = {},
        context?: ActionContext,
    ): Promise<BaseRecord[]> {
        try {
            const data = await this.fetchApi(this.endpoint, context);
            const users = Array.isArray(data) ? data : data.users || [];
            return users.map((item) => new BaseRecord(item, this));
        } catch (error) {
            console.error(`Error fetching ${this.resourceName}:`, error);
            return [];
        }
    }

    public async findOne(id: string, context?: ActionContext): Promise<BaseRecord | null> {
        try {
            const baseUrl = this.endpoint.replace(/\/users$/, '');
            const url = `${baseUrl}/users/id/${id}`;
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
        throw new Error('Creating users through AdminJS is not supported.');
    }

    public async update(id: string, params: Record<string, any>, context?: ActionContext): Promise<ParamsType> {
        throw new Error('Updating users through AdminJS is not yet implemented.');
    }

    public async delete(id: string, context?: ActionContext): Promise<void> {
        throw new Error('Deleting users through AdminJS is not supported.');
    }

    public static isAdapterFor(rawResource: any): boolean {
        return false;
    }
}
