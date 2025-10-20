import express from 'express';
import session from 'express-session';
import { Redis } from 'ioredis';
import connectRedis from 'connect-redis';
import AdminJS from 'adminjs';
import { buildAuthenticatedRouter } from '@adminjs/express';

import provider from './admin/auth-provider.js';
import options from './admin/options.js';

// Setting up the Express app and AdminJS
const start = async () => {
    // Create express app
    const app = express();

    // Redis Session setup
    const redisClient = new Redis({
        host: process.env.REDIS_HOST,
        port: Number(process.env.REDIS_PORT),
        password: process.env.REDIS_PASSWORD,
        db: Number(process.env.ADMINJS_SERVICE_REDIS_DB),
    });

    // ✅ Correct way: call the connect-redis function with express-session
    const RedisStore = connectRedis(session);

    // ✅ Then create the store instance
    const redisStore = new RedisStore({
        client: redisClient,
        prefix: process.env.ADMINJS_SERVICE_REDIS_PREFIX,
    });

    // registaring the Redis adapter for AdminJS
    app.use(
        session({
            store: redisStore,
            secret: process.env.COOKIE_SECRET,
            resave: false,
            saveUninitialized: false,
            cookie: {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                maxAge: 1000 * 60 * 60, // 1 hour
            },
    }));

    // Initialize AdminJS
    const admin = new AdminJS(options);

    // Add resources to AdminJS
    if (process.env.NODE_ENV === 'production') {
        await admin.initialize();
    } else {
        admin.watch();
    }

    // Add User resource with customizations
    const router = buildAuthenticatedRouter(
        admin,
        {
            cookiePassword: process.env.COOKIE_SECRET,
            cookieName: 'adminjs',
            provider,
        },
    );

    // Serve AdminJS at /admin
    app.use(admin.options.rootPath, router);

    app.listen(process.env.ADMIN_JS_PORT, () => {
        console.log(`AdminJS available at http://localhost:${process.env.ADMIN_JS_PORT}${admin.options.rootPath}`);
    });
};

start();
