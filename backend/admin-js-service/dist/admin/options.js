import { dark, light, noSidebar } from '@adminjs/themes';
import { ApiResource } from '../resources/api-resource.js';
import { RESOURCE_CATALOGUE } from '../resources/catalogue.js';
import componentLoader from './component-loader.js';
import { schemaRegistry } from './schema-registry.js';
const builtInActions = (resource) => {
    const { writes } = resource.spec;
    return {
        new: { isAccessible: writes.create },
        edit: { isAccessible: writes.update },
        delete: { isAccessible: writes.delete },
        bulkDelete: { isAccessible: false },
    };
};
const toResource = (entry, api) => {
    const resource = new ApiResource(entry.spec, api);
    if (entry.spec.schemaPath)
        schemaRegistry.register(resource);
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
export const buildAdminOptions = (config, api) => ({
    defaultTheme: light.id,
    availableThemes: [dark, light, noSidebar],
    componentLoader,
    rootPath: '/admin',
    branding: { companyName: 'Admin panel', logo: false, withMadeWithLove: false },
    resources: RESOURCE_CATALOGUE.map((entry) => toResource(entry, api)),
    env: { ADMIN_ROLE: config.adminRole },
});
