import { BaseResource, BaseRecord, BaseProperty } from 'adminjs';

export class ApiResourceProvider extends BaseResource {
    private endpoint: string;

    private resourceName: string;

    constructor(endpoint: string, resourceName: string, adminToken?: string) {
        super();
        this.endpoint = endpoint;
        this.resourceName = resourceName;
    }

    public static properties(): BaseProperty[] {
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
            throw new Error(`API request failed with status ${response.status}`);
        }
        return response.json();
    }

    public id(): string {
        return this.resourceName;
    }

    
}
