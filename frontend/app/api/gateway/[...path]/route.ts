import { NextRequest, NextResponse } from "next/server";
import { settings } from "@/lib/config";
import { sessionManagaer } from "@/actions/getCurrentUser";

/**
 * Same-origin proxy to the API gateway. The browser calls it with its session
 * cookie; this route looks up the access token on the server and forwards the
 * request with `Authorization: Bearer`, so the token never reaches the page.
 *
 * Only the versioned API is reachable, and the upstream response is passed
 * back as it is, minus any cookies (the gateway's cookies belong to the
 * server-side sign-in, not to the browser).
 */

// x-forwarded-for: the browser's address, so the gateway rate-limits the caller, not the proxy.
const FORWARDED_REQUEST_HEADERS = ["content-type", "accept", "x-forwarded-for"] as const;
const FORWARDED_RESPONSE_HEADERS = ["content-type", "content-disposition"] as const;
const SAFE_METHODS = new Set(["GET", "HEAD"]);
const API_PREFIX = `api/${settings.api.version}/`;

const forward = async (
    request: NextRequest,
    segments: string[],
): Promise<Response> => {
    // Only the versioned API, and no path tricks.
    if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
        return NextResponse.json({ detail: "Not found" }, { status: 404 });
    }
    const upstreamPath = segments.join("/");
    if (!`${upstreamPath}/`.startsWith(API_PREFIX)) {
        return NextResponse.json({ detail: "Not found" }, { status: 404 });
    }

    // Session cookies are SameSite=Lax, which already blocks cross-site writes;
    // this rejects any write whose Origin says it came from another site.
    if (!SAFE_METHODS.has(request.method)) {
        const origin = request.headers.get("origin");
        if (origin && origin !== request.nextUrl.origin) {
            return NextResponse.json({ detail: "Cross-site request refused" }, { status: 403 });
        }
    }

    const headers = new Headers();
    for (const name of FORWARDED_REQUEST_HEADERS) {
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
    }
    const token = await sessionManagaer.getCurrentUserJWT();
    if (token) {
        headers.set("authorization", `Bearer ${token}`);
    }

    const upstream = await fetch(
        `${settings.api.origin}/${upstreamPath}${request.nextUrl.search}`,
        {
            method: request.method,
            headers,
            body: SAFE_METHODS.has(request.method) ? undefined : await request.arrayBuffer(),
            cache: "no-store",
            redirect: "manual",
        },
    );

    const responseHeaders = new Headers();
    for (const name of FORWARDED_RESPONSE_HEADERS) {
        const value = upstream.headers.get(name);
        if (value) responseHeaders.set(name, value);
    }
    return new NextResponse(upstream.body, { status: upstream.status, headers: responseHeaders });
};

type Context = RouteContext<"/api/gateway/[...path]">;

export async function GET(request: NextRequest, context: Context) {
    return forward(request, (await context.params).path);
}

export async function HEAD(request: NextRequest, context: Context) {
    return forward(request, (await context.params).path);
}

export async function POST(request: NextRequest, context: Context) {
    return forward(request, (await context.params).path);
}

export async function PUT(request: NextRequest, context: Context) {
    return forward(request, (await context.params).path);
}

export async function PATCH(request: NextRequest, context: Context) {
    return forward(request, (await context.params).path);
}

export async function DELETE(request: NextRequest, context: Context) {
    return forward(request, (await context.params).path);
}
