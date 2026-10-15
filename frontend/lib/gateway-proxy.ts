import { settings } from "@/lib/config";

/**
 * Browser code calls the gateway through this same-origin path. The proxy
 * route adds the signed-in user's token on the server, so the token never
 * reaches the page's JavaScript.
 */
export const GATEWAY_PROXY_PATH = "/api/gateway";

/**
 * The proxy URL for a gateway URL, e.g. `https://gateway/api/v1/orders/1` becomes
 * `/api/gateway/api/v1/orders/1`. Only URLs under the gateway's API are allowed.
 */
export const proxied = (gatewayUrl: string): string => {
    const url = new URL(gatewayUrl);
    const apiPrefix = `/api/${settings.api.version}/`;
    if (!url.pathname.startsWith(apiPrefix)) {
        throw new Error(`not a gateway API URL: ${url.pathname}`);
    }
    return `${GATEWAY_PROXY_PATH}${url.pathname}${url.search}`;
};
