import { AdminJSOptions } from 'adminjs';
import { dark, light, noSidebar } from '@adminjs/themes';

import { ApiResourceProvider } from '../resources/api-resource-provider.js';

import componentLoader from './component-loader.js';

async function buildDynamicResource(apiUrl: string, schemaUrl: string, name: string) {
    const provider = new ApiResourceProvider(apiUrl, schemaUrl, name, 'PostgreSQL');
    await provider.initializeProperties();
    return {
        resource: provider,
        options: {
            navigation: { name: `${name} Management` },
            properties: provider.generateAdminPropertiesConfig(),
            actions: {
                list: { isAccessible: true },
                show: { isAccessible: true },
                edit: { isAccessible: ({ currentAdmin }) => currentAdmin?.role === process.env.SECRET_ROLE },
                delete: { isAccessible: ({ currentAdmin }) => currentAdmin?.role === process.env.SECRET_ROLE },
                new: { isAccessible: false },
            },
        },
    };
}

// creating resources
const userResources = await buildDynamicResource(
    `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/users`,
    `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/users`,
    'User',
);

const options: AdminJSOptions = {
    defaultTheme: light.id,
    availableThemes: [dark, light, noSidebar],
    componentLoader,
    rootPath: '/admin',
    // Including the API Resource Provider for User management
    resources: [userResources],
};

export default options;
