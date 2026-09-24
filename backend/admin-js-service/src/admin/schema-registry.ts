import type { ApiResourceProvider } from '../resources/api-resource-provider.js';

/**
 * Every API-backed resource whose field schema is admin-only.
 *
 * The schemas cannot be fetched at startup because no admin is signed in
 * yet, so the auth provider asks the registry to load them all with the
 * admin's token right after login — before the dashboard is rendered.
 */
class SchemaRegistry {
    private readonly providers: ApiResourceProvider[] = [];

    register(provider: ApiResourceProvider): ApiResourceProvider {
        this.providers.push(provider);
        return provider;
    }

    async loadAll(token: string): Promise<void> {
        // One failing schema must not block the others or the login itself.
        await Promise.allSettled(this.providers.map((provider) => provider.ensureSchema(token)));
    }
}

export const schemaRegistry = new SchemaRegistry();
