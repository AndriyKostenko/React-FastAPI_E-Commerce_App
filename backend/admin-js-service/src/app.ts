import express from 'express';
import session from 'express-session';
import { Redis } from 'ioredis';
import connectRedis from 'connect-redis';
import AdminJS from 'adminjs';
import { buildAuthenticatedRouter } from '@adminjs/express';

import { AdminTokenStore } from './auth/admin-token-store.js';
import { PasskeyAuthProvider } from './auth/passkey-auth-provider.js';
import { PasskeyRoutes } from './auth/passkey-routes.js';
import { AdminSessionGuard } from './auth/session-guard.js';
import { buildAdminOptions } from './admin/options.js';
import { AdminConfigError, loadConfig } from './config.js';
import { AdminGateway } from './gateway/admin-gateway.js';
import { GatewayClient } from './gateway/gateway-client.js';
import { returnPhotoRoute } from './http/return-photo-route.js';
import { securityHeaders } from './http/security-headers.js';

const SESSION_COOKIE = 'adminjs';

const start = async (): Promise<void> => {
    const config = loadConfig();
    const app = express();
    app.disable('x-powered-by');
    app.use(securityHeaders);

    const redisClient = new Redis({
        host: config.redis.host,
        port: config.redis.port,
        password: config.redis.password,
        db: config.redis.db,
    });
    const RedisStore = connectRedis(session);
    const redisStore = new RedisStore({
        client: redisClient,
        prefix: config.redis.prefix,
        // Server-side lifetime of a session: the idle limit, renewed on every request.
        ttl: Math.ceil(config.session.idleMs / 1000),
    });

    const gateway = new GatewayClient(config.gatewayApiUrl);
    const tokens = new AdminTokenStore(redisClient, config.redis.prefix, gateway, config.session.absoluteMs);

    const api = new AdminGateway(gateway, tokens);
    const admin = new AdminJS(buildAdminOptions(config, api));
    if (config.production) {
        await admin.initialize();
    } else {
        admin.watch();
    }

    // One session middleware for the whole app. The AdminJS router installs
    // its own too, but express-session steps aside when a session already
    // exists, so this configuration is the one in force.
    const sessionOptions: session.SessionOptions = {
        name: SESSION_COOKIE,
        store: redisStore,
        secret: config.cookieSecret,
        resave: false,
        saveUninitialized: false,
        // Every request pushes the expiry out: the idle limit.
        rolling: true,
        cookie: {
            httpOnly: true,
            secure: config.production,
            // Never sent on a request another site starts, which also covers
            // CSRF on AdminJS's own forms and its GET logout.
            sameSite: 'strict',
            maxAge: config.session.idleMs,
        },
    };
    app.use(admin.options.rootPath, session(sessionOptions));

    // Before the AdminJS router: these run before any session exists.
    app.use(admin.options.rootPath, new PasskeyRoutes(gateway).build());
    app.use(admin.options.rootPath, new AdminSessionGuard(tokens, config.session, admin.options.loginPath).middleware);
    app.use(admin.options.rootPath, returnPhotoRoute(api));

    const router = buildAuthenticatedRouter(
        admin,
        {
            cookiePassword: config.cookieSecret,
            cookieName: SESSION_COOKIE,
            provider: new PasskeyAuthProvider(gateway, tokens, config.adminRole),
            // AdminJS's own per-address limit on login posts, behind the gateway's.
            maxRetries: { count: 5, duration: 60 },
        },
        null,
        sessionOptions,
    );
    app.use(admin.options.rootPath, router);

    app.listen(config.port, config.listenHost, () => {
        console.log(`AdminJS available at http://${config.listenHost}:${config.port}${admin.options.rootPath}`);
    });
};

start().catch((error: unknown) => {
    // A configuration problem is the operator's to fix: say what, not a stack.
    console.error(error instanceof AdminConfigError ? error.message : error);
    process.exit(1);
});
