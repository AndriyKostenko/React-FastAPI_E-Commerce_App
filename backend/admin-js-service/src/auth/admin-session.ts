import type { CurrentAdmin } from 'adminjs';
import type { Request } from 'express';

/**
 * The signed-in admin as AdminJS keeps it in the session (and renders into
 * every page as `currentAdmin`). Deliberately free of anything secret: the
 * tokens stay in AdminTokenStore under `sessionRef`.
 */
export interface AdminIdentity extends CurrentAdmin {
    id: string;
    email: string;
    role: string;
    sessionRef: string;
}

declare module 'express-session' {
    interface SessionData {
        adminUser?: AdminIdentity;
        // Unix ms; with the policy's absolute limit, when the session ends however busy.
        signedInAt?: number;
    }
}

export const isAdminIdentity = (value: CurrentAdmin | null | undefined): value is AdminIdentity =>
    !!value &&
    typeof value.id === 'string' &&
    typeof value.role === 'string' &&
    typeof value.sessionRef === 'string';

/** Issue a fresh session id at sign-in, so an id planted before it (fixation) is worthless. */
export const regenerateSession = (req: Request): Promise<void> =>
    new Promise((resolve, reject) => {
        req.session.regenerate((error?: Error) => (error ? reject(error) : resolve()));
    });
