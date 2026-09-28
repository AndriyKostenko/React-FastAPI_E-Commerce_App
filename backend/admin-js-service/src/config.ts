/**
 * admin-js configuration, checked once at startup.
 *
 * Every value comes from backend/.env (compose's env_file, or node's
 * --env-file under dev.sh). A missing one used to surface later and far from
 * its cause: an unset Redis DB became `SELECT NaN`, an unset cookie secret an
 * unsigned session. Now the process refuses to start and names what is missing.
 */

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
] as const;

type RequiredKey = (typeof REQUIRED_KEYS)[number];

export interface AdminConfig {
    readonly port: number;
    readonly gatewayApiUrl: string;
    readonly adminRole: string;
    readonly cookieSecret: string;
    readonly production: boolean;
    readonly redis: {
        readonly host: string;
        readonly port: number;
        readonly password: string;
        readonly db: number;
        readonly prefix: string;
    };
}

export class AdminConfigError extends Error {}

const toInteger = (key: RequiredKey, value: string): number => {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < 0) {
        throw new AdminConfigError(`${key} must be a non-negative integer, got "${value}"`);
    }
    return parsed;
};

export const loadConfig = (env: NodeJS.ProcessEnv = process.env): AdminConfig => {
    const missing = REQUIRED_KEYS.filter((key) => !env[key]);
    if (missing.length > 0) {
        throw new AdminConfigError(
            `admin-js cannot start: ${missing.join(', ')} ${missing.length === 1 ? 'is' : 'are'} not set (add to backend/.env)`,
        );
    }
    const value = (key: RequiredKey): string => env[key] as string;
    return {
        port: toInteger('ADMIN_JS_PORT', value('ADMIN_JS_PORT')),
        gatewayApiUrl: value('API_GATEWAY_SERVICE_URL') + value('API_GATEWAY_SERVICE_URL_API_VERSION'),
        adminRole: value('SECRET_ROLE'),
        cookieSecret: value('COOKIE_SECRET'),
        production: env.NODE_ENV === 'production',
        redis: {
            host: value('REDIS_HOST'),
            port: toInteger('REDIS_PORT', value('REDIS_PORT')),
            password: value('REDIS_PASSWORD'),
            db: toInteger('ADMINJS_SERVICE_REDIS_DB', value('ADMINJS_SERVICE_REDIS_DB')),
            prefix: value('ADMINJS_SERVICE_REDIS_PREFIX'),
        },
    };
};
