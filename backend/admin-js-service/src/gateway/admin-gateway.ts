import type { CurrentAdmin } from 'adminjs';

import { isAdminIdentity } from '../auth/admin-session.js';
import { AdminTokenStore } from '../auth/admin-token-store.js';
import { GatewayClient, GatewayError, GatewayRequest } from './gateway-client.js';
import { JsonValue } from './json.js';

/**
 * The gateway, called as the signed-in admin.
 *
 * Every call carries that admin's own fresh access token, so the gateway and
 * services check the admin like any other caller and admin-js holds no
 * privileges of its own. A 401 means the backend no longer accepts the
 * session (passkey revoked, sessions ended, account demoted): the session's
 * tokens are dropped, and the session guard sends the admin to the login page
 * on their next request.
 */
export class AdminGateway {
    constructor(
        readonly client: GatewayClient,
        private readonly tokens: AdminTokenStore,
    ) {}

    async send(admin: CurrentAdmin | undefined, path: string, request: Omit<GatewayRequest, 'accessToken'> = {}): Promise<JsonValue | null> {
        const sessionRef = AdminGateway.sessionRef(admin);
        const accessToken = await this.tokens.accessToken(sessionRef);
        return this.endSessionOn401(sessionRef, () => this.client.send(path, { ...request, accessToken }));
    }

    async download(admin: CurrentAdmin | undefined, path: string): Promise<Response> {
        const sessionRef = AdminGateway.sessionRef(admin);
        const accessToken = await this.tokens.accessToken(sessionRef);
        return this.endSessionOn401(sessionRef, () => this.client.download(path, accessToken));
    }

    /** For the one call made with a bare token: the post-login schema load. */
    async accessTokenFor(admin: CurrentAdmin | undefined): Promise<string> {
        return this.tokens.accessToken(AdminGateway.sessionRef(admin));
    }

    private async endSessionOn401<T>(sessionRef: string, call: () => Promise<T>): Promise<T> {
        try {
            return await call();
        } catch (error) {
            if (error instanceof GatewayError && error.status === 401) {
                await this.tokens.close(sessionRef);
            }
            throw error;
        }
    }

    private static sessionRef(admin: CurrentAdmin | undefined): string {
        if (!isAdminIdentity(admin)) throw new GatewayError(401, 'Not signed in');
        return admin.sessionRef;
    }
}
