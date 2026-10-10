import { AdminJSOptions, ResourceOptions, ResourceWithOptions } from 'adminjs';
import { dark, light, noSidebar } from '@adminjs/themes';

import type { AdminConfig } from '../config.js';
import { AdminGateway } from '../gateway/admin-gateway.js';
import { ApiResource } from '../resources/api-resource.js';
import { RESOURCE_CATALOGUE, ResourceEntry } from '../resources/catalogue.js';
import componentLoader from './component-loader.js';
import { schemaRegistry } from './schema-registry.js';

/** AdminJS's built-in actions, allowed only where the resource's write policy allows them. */
const builtInActions = (resource: ApiResource): ResourceOptions['actions'] => {
    const { writes } = resource.spec;
    return {
        new: { isAccessible: writes.create },
        edit: { isAccessible: writes.update },
        delete: { isAccessible: writes.delete },
        bulkDelete: { isAccessible: false },
    };
};

const toResource = (entry: ResourceEntry, api: AdminGateway): ResourceWithOptions => {
    const resource = new ApiResource(entry.spec, api);
    if (entry.spec.schemaPath) schemaRegistry.register(resource);
    const extra = entry.options?.({ api, resource }) ?? {};
    return {
        resource,
        options: {
            navigation: { name: entry.navigation },
            ...(entry.list ? { listProperties: [...entry.list] } : {}),
            ...extra,
            actions: { ...builtInActions(resource), ...extra.actions },
        },
    };
};

export const buildAdminOptions = (config: AdminConfig, api: AdminGateway): AdminJSOptions => ({
    defaultTheme: light.id,
    availableThemes: [dark, light, noSidebar],
    componentLoader,
    rootPath: '/admin',
    branding: { companyName: 'Admin panel', logo: false, withMadeWithLove: false },
    resources: RESOURCE_CATALOGUE.map((entry) => toResource(entry, api)),
    env: { ADMIN_ROLE: config.adminRole },
});
