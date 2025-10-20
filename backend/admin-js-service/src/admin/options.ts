import { AdminJSOptions } from 'adminjs';
import { dark, light, noSidebar } from '@adminjs/themes';

import { ApiResourceProvider } from '../resources/api-resource-provider.js';

import componentLoader from './component-loader.js';

const options: AdminJSOptions = {
    defaultTheme: dark.id,
    availableThemes: [dark, light, noSidebar],
    componentLoader,
    rootPath: '/admin',
    // Including the API Resource Provider for User management
    resources: [
        {
            resource: new ApiResourceProvider(
                `${process.env.API_GATEWAY_SERVICE_URL}${process.env.API_GATEWAY_SERVICE_URL_API_VERSION}/users`,
                'User',
            ),
            options: {
                navigation: {
                    name: 'User Management',
                    icon: 'User',
                },
                properties: {
                    id: { isVisible: { list: true, filter: true, show: true, edit: false } },
                    name: { isTitle: true, isVisible: { list: true, filter: true, show: true, edit: true } },
                    email: { isVisible: { list: true, filter: true, show: true, edit: true } },
                    role: { isVisible: { list: true, filter: true, show: true, edit: true } },
                    phone_number: { isVisible: { list: false, filter: false, show: true, edit: true } },
                    image: { isVisible: { list: false, filter: false, show: true, edit: true } },
                    is_active: { isVisible: { list: true, filter: true, show: true, edit: true } },
                    is_verified: { isVisible: { list: true, filter: true, show: true, edit: true } },
                    date_created: { isVisible: { list: true, filter: true, show: true, edit: false } },
                    date_updated: { isVisible: { list: true, filter: true, show: true, edit: false } },
                },
                actions: { 
                    new: { isAccessible: true},
                    edit: { isAccessible: ({ currentAdmin }) => currentAdmin?.role === process.env.SECRET_ROLE},
                    delete: { isAccessible: true },
                    show: { isAccessible: true },
                    list: { isAccessible: true },
            },
        }
        },
    ],
    databases: [],
};

export default options;
