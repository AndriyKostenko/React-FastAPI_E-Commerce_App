import express from 'express';
import session from 'express-session';
import { Redis } from 'ioredis';
import RedisStore from 'connect-redis';
import AdminJS from 'adminjs';
import { buildAuthenticatedRouter } from '@adminjs/express';
import provider from './admin/auth-provider.js';
import options from './admin/options.js';
import initializeDb from './db/index.js';
const start = async () => {
    const app = express();
    const redisClient = new Redis({
        host: process.env.REDIS_HOST,
        port: Number(process.env.REDIS_PORT),
        password: process.env.REDIS_PASSWORD,
        db: Number(process.env.ADMINJS_SERVICE_REDIS_DB),
    });
    const redisStore = new RedisStore({
        client: redisClient,
        prefix: process.env.ADMINJS_SERVICE_REDIS_PREFIX,
    });
    app.use(session({
        store: redisStore,
        secret: process.env.COOKIE_SECRET,
        resave: false,
        saveUninitialized: false,
        cookie: {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            maxAge: 1000 * 60 * 60,
        },
    }));
    await initializeDb();
    const admin = new AdminJS(options);
    if (process.env.NODE_ENV === 'production') {
        await admin.initialize();
    }
    else {
        admin.watch();
    }
    const router = buildAuthenticatedRouter(admin, {
        cookiePassword: process.env.COOKIE_SECRET,
        cookieName: 'adminjs',
        provider,
    }, app);
    app.use(admin.options.rootPath, router);
    app.listen(process.env.ADMIN_JS_PORT, () => {
        console.log(`AdminJS available at http://localhost:${process.env.ADMIN_JS_PORT}${admin.options.rootPath}`);
    });
};
start();
