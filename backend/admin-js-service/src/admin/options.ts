import { AdminJSOptions } from 'adminjs';
import { dark, light, noSidebar } from '@adminjs/themes';

import { ApiResourceProvider } from '../resources/api-resource-provider.js';

import componentLoader from './component-loader.js';
import { schemaRegistry } from './schema-registry.js';

function buildDynamicResource(
    apiUrl: string,
    schemaUrl: string,
    name: string,
    usesFormData = false,
) {
    // The schema is admin-only, so it is loaded after login (see schemaRegistry);
    // the provider regenerates its property config when it arrives.
    const provider = schemaRegistry.register(
        new ApiResourceProvider(apiUrl, schemaUrl, name, 'PostgreSQL', usesFormData),
    );

    return {
        resource: provider,
        options: {
            navigation: { name: `${name} Management` },
            actions: {
                show: { isAccessible: true },
                edit: { isAccessible: ({ currentAdmin }) => currentAdmin?.role === process.env.SECRET_ROLE },
                delete: { isAccessible: ({ currentAdmin }) => currentAdmin?.role === process.env.SECRET_ROLE },
                new: { isAccessible: true }, // enable creation for all admins
            },
        },
    };
}

const [
	userResources,
	productResources,
	categoryResources,
	imageResources,
	reviewResources,
	orderResources
] = [
    buildDynamicResource(
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/users`,
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/users`,
        'User',
        false,
    ),
    buildDynamicResource(
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/products`,
        // eslint-disable-next-line max-len
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/products`,
        'Product',
        false,
    ),
    buildDynamicResource(
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/categories`,
        // eslint-disable-next-line max-len
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/categories`,
        'Categories',
        false,
    ),
    buildDynamicResource(
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/images`,
        // eslint-disable-next-line max-len
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/images`,
        'Images',
        false,
    ),
    buildDynamicResource(
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/reviews`,
        // eslint-disable-next-line max-len
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/reviews`,
        'Reviews',
        false,
	),
    buildDynamicResource(
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/orders`,
        // eslint-disable-next-line max-len
        `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/orders`,
        'Orders',
        false,
    ),
];

const options: AdminJSOptions = {
    defaultTheme: light.id,
    availableThemes: [dark, light, noSidebar],
    componentLoader,
    rootPath: '/admin',
    // Including the API Resource Provider for User management
    resources: [userResources, productResources, categoryResources, imageResources, reviewResources, orderResources],
};

export default options;
