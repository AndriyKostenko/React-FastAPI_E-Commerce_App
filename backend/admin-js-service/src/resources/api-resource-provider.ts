import { BaseResource, BaseRecord, BaseProperty, Filter, ParamsType } from 'adminjs';

export class ApiResourceProvider extends BaseResource {
    private endpoint: string;

    private resourceName: string;

    constructor(endpoint: string, resourceName: string) {
        super();
        this.endpoint = endpoint;
        this.resourceName = resourceName;
    }

    public databaseName(): string {
        return 'API';
    }

    public databaseType(): string {
        return 'REST API';
    }

    public name(): string {
        return this.resourceName;
    }

    public id(): string {
        return this.resourceName;
    }

    public properties(): BaseProperty[] {
    // Define properties based on your User schema
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

    public property(path: string): BaseProperty | null {
        return this.properties().find((p) => p.path() === path) || null;
    }

    private async fetchApi(url: string, context: any, options: RequestInit = {}): Promise<any> {
        const token = context?.currentAdmin?.token;
        const headers = {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` }),
            ...options.headers,
        };

        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            console.error(`API request failed: ${response.status} ${response.statusText}`);
            throw new Error(`API request failed with status ${response.status}`);
        }
        return response.json();
    }

    public async find(filter: Filter, options: { limit?: number; offset?: number; sort?: any }): Promise<BaseRecord[]> {
        try {
            const data = await this.fetchApi(this.endpoint);
            // Handle if data is wrapped in an object or is direct array
            const users = Array.isArray(data) ? data : data.users || [];
            return users.map((item: any) => new BaseRecord(item, this));
        } catch (error) {
            console.error(`Error fetching ${this.resourceName}:`, error);
            return [];
        }
    }

    public async findOne(id: string): Promise<BaseRecord | null> {
        try {
            // Extract base URL without /users
            const baseUrl = this.endpoint.replace(/\/users$/, '');
            const url = `${baseUrl}/users/id/${id}`;
            const data = await this.fetchApi(url);
            return new BaseRecord(data, this);
        } catch (error) {
            console.error(`Error fetching ${this.resourceName} with id ${id}:`, error);
            return null;
        }
    }

    public async count(filter: Filter): Promise<number> {
        try {
            const records = await this.find(filter, {});
            return records.length;
        } catch (error) {
            console.error(`Error counting ${this.resourceName}:`, error);
            return 0;
        }
    }

    public async create(params: Record<string, any>): Promise<ParamsType> {
        throw new Error('Creating users through AdminJS is not supported. Use the registration endpoint.');
    }

    public async update(id: string, params: Record<string, any>): Promise<ParamsType> {
        throw new Error('Updating users through AdminJS is not yet implemented');
    }

    public async delete(id: string): Promise<void> {
        throw new Error('Deleting users through AdminJS is not supported');
    }

    public static isAdapterFor(rawResource: any): boolean {
        return false;
    }
}
