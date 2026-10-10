import type { NextFunction, Request, Response } from 'express';

import type { SessionPolicy } from '../config.js';
import { AdminSessionExpiredError, AdminTokenStore } from './admin-token-store.js';

/**
 * Runs before every AdminJS request of a signed-in admin.
 *
 * - Ends the session at the absolute limit, however active (the idle limit
 *   is the rolling cookie's own expiry).
 * - Makes sure the session's access token is fresh before AdminJS calls the
 *   gateway with it, refreshing it if it is about to expire; a refresh the
 *   backend refuses (revoked, demoted, deactivated) ends the session.
 *
 * Ending a session redirects to the login page. AdminJS's own API client
 * reads that redirect as "session expired" and sends the browser there too.
 */
export class AdminSessionGuard {
    constructor(
        private readonly tokens: AdminTokenStore,
        private readonly policy: SessionPolicy,
        private readonly loginPath: string,
    ) {}

    readonly middleware = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
        const admin = req.session?.adminUser;
        if (!admin) {
            next();
            return;
        }
        const signedInAt = req.session.signedInAt ?? 0;
        if (Date.now() - signedInAt > this.policy.absoluteMs) {
            await this.end(req, res);
            return;
        }
        try {
            await this.tokens.accessToken(admin.sessionRef);
        } catch (error) {
            if (error instanceof AdminSessionExpiredError) {
                await this.end(req, res);
                return;
            }
            next(error);
            return;
        }
        next();
    };

    private async end(req: Request, res: Response): Promise<void> {
        const sessionRef = req.session.adminUser?.sessionRef;
        if (sessionRef) await this.tokens.close(sessionRef);
        req.session.destroy(() => res.redirect(this.loginPath));
    }
}
