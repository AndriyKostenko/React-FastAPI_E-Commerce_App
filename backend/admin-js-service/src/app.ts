import express from 'express';
import session from 'express-session';
import Redis from 'ioredis';
import connectRedis from 'connect-redis';
import AdminJS from 'adminjs';
import { buildAuthenticatedRouter } from '@adminjs/express';


import provider from './admin/auth-provider.js';
import options from './admin/options.js';
import initializeDb from './db/index.js';


//
const port = process.env.ADMIN_JS_PORT || 3000;

// Setting up the Express app and AdminJS
const start = async () => {
    // Create express app
    const app = express();

    // Session setup
    const RedisStore = connectRedis(session);
    const redisClient = new Redis({
        host: process.env.REDIS_HOST,
        port: Number(process.env.REDIS_PORT),
        password: process.env.REDIS_PASSWORD,
    });

    // registaring the Redis adapter for AdminJS
    app.use(
        session({
            store: new RedisStore({ client: redisClient }),
            secret: process.env.COOKIE_SECRET,
            resave: false,
            saveUninitialized: false,
            cookie: {
                httpOnly: true, 
                secure: process.env.NODE_ENV === 'production',
                maxAge: 1000 * 60 * 60, // 1 hour
            },
    }));

    // Initialize database
    await initializeDb();

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
        app // attach to existing express app
    );

    // Serve AdminJS at /admin
    app.use(admin.options.rootPath, router);

    app.listen(port, () => {
        console.log(`AdminJS available at http://localhost:${port}${admin.options.rootPath}`);
    });
};

start();
