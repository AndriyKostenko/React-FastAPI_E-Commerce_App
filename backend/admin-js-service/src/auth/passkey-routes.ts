import express, { NextFunction, Request, Response, Router } from 'express';
import { fileURLToPath } from 'node:url';

import { GatewayClient, GatewayError } from '../gateway/gateway-client.js';
import { isJsonObject, JsonObject } from '../gateway/json.js';

// The enrolment page's own script and markup, served as plain files.
const ENROL_PAGE = fileURLToPath(new URL('../../public/passkey-enrol.html', import.meta.url));
const ENROL_SCRIPT = fileURLToPath(new URL('../../public/passkey-enrol.js', import.meta.url));

/**
 * The browser half of passkeys talks only to admin-js, on admin-js's own
 * origin (passkeys are bound to it); admin-js forwards to the gateway.
 *
 * Mounted under the AdminJS root path, ahead of the AdminJS router: these
 * requests come before any session exists. JSON bodies are parsed here only —
 * AdminJS refuses requests a global body parser has already read.
 */
export class PasskeyRoutes {
    constructor(private readonly gateway: GatewayClient) {}

    build(): Router {
        const router = express.Router();
        const json = express.json({ limit: '32kb' });

        router.post('/passkey/options', this.sameOrigin, json, this.handle(async (body) => {
            const email = PasskeyRoutes.text(body, 'email');
            const password = PasskeyRoutes.text(body, 'password');
            return this.gateway.passkeySignInOptions(email, password);
        }));

        router.get('/passkeys/enrol', (_req: Request, res: Response) => {
            // The token is in the URL fragment, which the browser keeps to itself;
            // no Referer for the link the page might be opened from.
            res.set('Referrer-Policy', 'no-referrer');
            res.sendFile(ENROL_PAGE);
        });
        router.get('/passkeys/enrol.js', (_req: Request, res: Response) => res.sendFile(ENROL_SCRIPT));

        router.post('/passkeys/enrol/options', this.sameOrigin, json, this.handle(async (body) => (
            this.gateway.passkeyEnrolmentOptions(PasskeyRoutes.text(body, 'token'))
        )));

        router.post('/passkeys/enrol/verify', this.sameOrigin, json, this.handle(async (body) => {
            const { credential } = body;
            if (!isJsonObject(credential)) throw new GatewayError(400, 'Missing credential');
            return this.gateway.passkeyEnrolment(
                PasskeyRoutes.text(body, 'token'),
                PasskeyRoutes.text(body, 'challengeId'),
                credential,
                PasskeyRoutes.text(body, 'name'),
            );
        }));

        return router;
    }

    /** Refuse cross-site posts: only the panel's own pages call these. */
    private readonly sameOrigin = (req: Request, res: Response, next: NextFunction): void => {
        const origin = req.get('origin');
        if (origin && new URL(origin).host !== req.get('host')) {
            res.status(403).json({ detail: 'Cross-origin request refused' });
            return;
        }
        next();
    };

    private handle(action: (body: JsonObject) => Promise<JsonObject | { challengeId: string; options: JsonObject }>) {
        return async (req: Request, res: Response): Promise<void> => {
            try {
                if (!isJsonObject(req.body)) throw new GatewayError(400, 'Expected a JSON body');
                res.json(await action(req.body));
            } catch (error) {
                if (error instanceof GatewayError) {
                    // A server error's detail may describe internals; a client error's is meant for the user.
                    const detail = error.status >= 500 ? 'The backend is not reachable. Try again shortly.' : error.detail;
                    res.status(error.status).json({ detail });
                    return;
                }
                res.status(500).json({ detail: 'Something went wrong. Start again.' });
            }
        };
    }

    private static text(body: JsonObject, key: string): string {
        const value = body[key];
        if (typeof value !== 'string' || !value) throw new GatewayError(400, `Missing ${key}`);
        return value;
    }
}
