import { BaseAuthProvider, LoginHandlerOptions } from 'adminjs';
import type { Request, Response } from 'express';

import { GatewayClient, GatewayError } from '../gateway/gateway-client.js';
import { isJsonObject, parseJsonObject } from '../gateway/json.js';
import { schemaRegistry } from '../admin/schema-registry.js';
import { AdminTokenStore } from './admin-token-store.js';
import { AdminIdentity, regenerateSession } from './admin-session.js';

interface ExpressContext {
    req: Request;
    res: Response;
}

/**
 * Signs admins in with password + passkey, through user-service.
 *
 * The login page (components/PasskeyLogin.tsx) does the browser half: it
 * sends the password to /admin/passkey/options, has the device sign the
 * challenge, and posts the signed answer here as `challengeId` + `credential`.
 * The password is never posted to this handler, and no session exists until
 * the signature has been verified by user-service.
 */
export class PasskeyAuthProvider extends BaseAuthProvider<ExpressContext> {
    constructor(
        private readonly gateway: GatewayClient,
        private readonly tokens: AdminTokenStore,
        private readonly adminRole: string,
    ) {
        super();
    }

    override async handleLogin(opts: LoginHandlerOptions, context?: ExpressContext): Promise<AdminIdentity | null> {
        if (!context) throw new Error('No request context');
        const { challengeId, credential } = opts.data;
        if (typeof challengeId !== 'string' || typeof credential !== 'string') {
            throw new Error(LoginMessage.START_AGAIN);
        }
        let parsedCredential;
        try {
            parsedCredential = parseJsonObject(credential);
        } catch {
            throw new Error(LoginMessage.START_AGAIN);
        }
        if (!isJsonObject(parsedCredential.response)) throw new Error(LoginMessage.START_AGAIN);

        let admin;
        try {
            admin = await this.gateway.passkeySignIn(challengeId, parsedCredential);
        } catch (error) {
            throw new Error(PasskeyAuthProvider.messageFor(error));
        }
        // user-service only signs admins in this way; checked again regardless.
        if (admin.role !== this.adminRole) throw new Error(LoginMessage.NOT_ADMIN);

        await regenerateSession(context.req);
        context.req.session.signedInAt = Date.now();
        const sessionRef = await this.tokens.open(admin.tokens);
        // The field schemas are admin-only; load them before the dashboard renders.
        await schemaRegistry.loadAll(admin.tokens.accessToken);
        return { id: admin.userId, email: admin.email, role: admin.role, title: admin.role, sessionRef };
    }

    override async handleLogout(context?: ExpressContext): Promise<void> {
        const sessionRef = context?.req.session.adminUser?.sessionRef;
        if (!sessionRef) return;
        const tokens = await this.tokens.close(sessionRef);
        if (tokens) {
            // Revoke the refresh token too; a failure here must not keep the admin signed in.
            await this.gateway.logout(tokens).catch(() => undefined);
        }
    }

    /**
     * The login page embeds the message inside a JavaScript string literal
     * (AdminJS's login template), so only fixed messages ever reach it, never
     * text that came from elsewhere.
     */
    private static messageFor(error: unknown): string {
        if (error instanceof GatewayError) {
            if (error.status === 429) return LoginMessage.TOO_MANY;
            if (error.status === 401 || error.status === 400) return LoginMessage.FAILED;
            if (error.status === 403) return LoginMessage.NOT_ADMIN;
            if (error.status >= 500) return LoginMessage.UNAVAILABLE;
        }
        return LoginMessage.FAILED;
    }
}

enum LoginMessage {
    FAILED = 'Sign-in failed. Start again.',
    START_AGAIN = 'Sign-in was interrupted. Start again.',
    NOT_ADMIN = 'This account cannot sign in to the admin panel.',
    TOO_MANY = 'Too many attempts. Wait a minute and try again.',
    UNAVAILABLE = 'The backend is not reachable. Try again shortly.',
}
