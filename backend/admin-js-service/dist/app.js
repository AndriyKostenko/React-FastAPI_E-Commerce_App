import express from 'express';
import session from 'express-session';
import { Redis } from 'ioredis';
import connectRedis from 'connect-redis';
import AdminJS from 'adminjs';
import { buildAuthenticatedRouter } from '@adminjs/express';
import provider from './admin/auth-provider.js';
import options from './admin/options.js';
import { AdminConfigError, loadConfig } from './config.js';
const start = async () => {
    const config = loadConfig();
    const app = express();
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
    });
    app.use(session({
        store: redisStore,
        secret: config.cookieSecret,
        resave: false,
        saveUninitialized: false,
        cookie: {
            httpOnly: true,
            secure: config.production,
            maxAge: 1000 * 60 * 60,
        },
    }));
    const admin = new AdminJS(options);
    if (config.production) {
        await admin.initialize();
    }
    else {
        admin.watch();
    }
    const router = buildAuthenticatedRouter(admin, {
        cookiePassword: config.cookieSecret,
        cookieName: 'adminjs',
        provider,
    }, null, {
        store: redisStore,
        secret: config.cookieSecret,
        resave: false,
        saveUninitialized: false,
    });
    app.use(admin.options.rootPath, router);
    app.listen(config.port, () => {
        console.log(`AdminJS available at http://localhost:${config.port}${admin.options.rootPath}`);
    });
};
start().catch((error) => {
    console.error(error instanceof AdminConfigError ? error.message : error);
    process.exit(1);
});
