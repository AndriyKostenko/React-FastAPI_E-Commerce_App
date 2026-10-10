const REQUIRED_KEYS = [
    'ADMIN_JS_PORT',
    'API_GATEWAY_SERVICE_URL',
    'API_GATEWAY_SERVICE_URL_API_VERSION',
    'SECRET_ROLE',
    'COOKIE_SECRET',
    'REDIS_HOST',
    'REDIS_PORT',
    'REDIS_PASSWORD',
    'ADMINJS_SERVICE_REDIS_DB',
    'ADMINJS_SERVICE_REDIS_PREFIX',
];
export class AdminConfigError extends Error {
}
const toInteger = (key, value) => {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < 0) {
        throw new AdminConfigError(`${key} must be a non-negative integer, got "${value}"`);
    }
    return parsed;
};
const optionalInteger = (env, key, fallback) => {
    const value = env[key];
    return value ? toInteger(key, value) : fallback;
};
export const loadConfig = (env = process.env) => {
    const missing = REQUIRED_KEYS.filter((key) => !env[key]);
    if (missing.length > 0) {
        throw new AdminConfigError(`admin-js cannot start: ${missing.join(', ')} ${missing.length === 1 ? 'is' : 'are'} not set (add to backend/.env)`);
    }
    const value = (key) => env[key];
    const idleMinutes = optionalInteger(env, 'ADMIN_JS_SESSION_IDLE_MINUTES', 30);
    const maxHours = optionalInteger(env, 'ADMIN_JS_SESSION_MAX_HOURS', 8);
    if (idleMinutes < 1 || maxHours < 1) {
        throw new AdminConfigError('ADMIN_JS_SESSION_IDLE_MINUTES and ADMIN_JS_SESSION_MAX_HOURS must be at least 1');
    }
    return {
        port: toInteger('ADMIN_JS_PORT', value('ADMIN_JS_PORT')),
        listenHost: env.ADMIN_JS_LISTEN_HOST || '127.0.0.1',
        gatewayApiUrl: value('API_GATEWAY_SERVICE_URL') + value('API_GATEWAY_SERVICE_URL_API_VERSION'),
        adminRole: value('SECRET_ROLE'),
        cookieSecret: value('COOKIE_SECRET'),
        production: env.NODE_ENV === 'production',
        session: {
            idleMs: idleMinutes * 60_000,
            absoluteMs: maxHours * 3_600_000,
        },
        redis: {
            host: value('REDIS_HOST'),
            port: toInteger('REDIS_PORT', value('REDIS_PORT')),
            password: value('REDIS_PASSWORD'),
            db: toInteger('ADMINJS_SERVICE_REDIS_DB', value('ADMINJS_SERVICE_REDIS_DB')),
            prefix: value('ADMINJS_SERVICE_REDIS_PREFIX'),
        },
    };
};
