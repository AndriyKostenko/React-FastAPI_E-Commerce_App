import type { NextRequest } from "next/server";
import { GatewayAuthClient } from "@/lib/gateway-auth-client";
import { SessionCookie } from "@/lib/session-cookie";
import { SessionProxy } from "@/lib/session-proxy";
import { SessionRefresher } from "@/lib/session-refresher";
import { settings } from "@/lib/config";

const nowInSeconds = (): number => Math.floor(Date.now() / 1000);

// Refresh two minutes before the 20-minute access token expires. Overridable
// only to watch refreshes happen locally without waiting for it.
const REFRESH_MARGIN_SECONDS = Number(process.env.SESSION_REFRESH_MARGIN_SECONDS ?? 120);
const REFRESH_GRACE_SECONDS = 120;

const createSessionProxy = (): SessionProxy =>
    new SessionProxy(
        new SessionRefresher(
            new GatewayAuthClient({
                refresh: settings.api.endpoints.authRefresh,
                logout: settings.api.endpoints.authLogout,
            }),
            { marginSeconds: REFRESH_MARGIN_SECONDS, graceSeconds: REFRESH_GRACE_SECONDS, now: nowInSeconds },
        ),
        SessionCookie,
        nowInSeconds,
    );

// One instance for the life of the process: the refresher's memory is what
// keeps a refresh token from being used twice (see SessionRefresher). Kept on
// globalThis because the dev server re-evaluates this module on every edit.
const holder = globalThis as typeof globalThis & { __sessionProxy?: SessionProxy };
const sessionProxy = (holder.__sessionProxy ??= createSessionProxy());

export function proxy(request: NextRequest) {
    return sessionProxy.handle(request);
}

export const config = {
    // Every page, server action and route handler; not build assets or images.
    matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
