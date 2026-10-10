import type { ApiResource } from '../resources/api-resource.js';

/**
 * Every API-backed resource whose field schema is admin-only.
 *
 * The schemas cannot be fetched at startup because no admin is signed in
 * yet, so the auth provider asks the registry to load them all with the
 * admin's token right after login — before the dashboard is rendered.
 */
class SchemaRegistry {
    private readonly resources: ApiResource[] = [];

    register(resource: ApiResource): ApiResource {
        this.resources.push(resource);
        return resource;
    }

    async loadAll(accessToken: string): Promise<void> {
        // One failing schema must not block the others or the login itself.
        await Promise.allSettled(this.resources.map((resource) => resource.ensureSchema(accessToken)));
    }
}

export const schemaRegistry = new SchemaRegistry();
