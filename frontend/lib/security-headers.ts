import type { NextResponse } from "next/server";

type Directive =
  | "default-src"
  | "script-src"
  | "style-src"
  | "img-src"
  | "font-src"
  | "connect-src"
  | "frame-src"
  | "worker-src"
  | "object-src"
  | "base-uri"
  | "form-action"
  | "frame-ancestors"
  | "upgrade-insecure-requests";

/** Builds a Content-Security-Policy header value one directive at a time (Builder). */
export class ContentSecurityPolicy {
  private readonly directives = new Map<Directive, string[]>();

  allow(directive: Directive, ...sources: readonly string[]): this {
    const current = this.directives.get(directive) ?? [];
    this.directives.set(directive, [
      ...current,
      ...sources.filter((source) => !current.includes(source)),
    ]);
    return this;
  }

  toString(): string {
    return Array.from(this.directives, ([directive, sources]) =>
      sources.length ? `${directive} ${sources.join(" ")}` : directive,
    ).join("; ");
  }
}

/** What the policy needs to know about where the page runs. */
export interface SecurityHeaderOptions {
  /** The gateway's origin as the browser calls it; same-origin in production. */
  apiOrigin: string;
  development: boolean;
}

// Third parties the storefront embeds. Stripe: card fields and 3-D Secure run
// in its frames, its script talks to its API. Cloudflare: the Turnstile widget.
const STRIPE_FRAMES = ["https://js.stripe.com", "https://hooks.stripe.com"];
const STRIPE_API = ["https://api.stripe.com"];
const TURNSTILE = "https://challenges.cloudflare.com";

// Local origins the browser reaches directly in development: the gateway
// (as localhost or 127.0.0.1, whichever the page was opened on) and the S3
// server holding catalogue images.
const LOCAL_API_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"];
const LOCAL_IMAGE_ORIGINS = ["http://localhost:8333", "http://127.0.0.1:8333"];

/**
 * The security headers of one page response.
 *
 * Scripts are allowed by a nonce made for this request ('strict-dynamic'):
 * Next.js puts it on its own scripts when it sees the policy on the request,
 * and scripts those load (Stripe.js, Turnstile) inherit the trust. Injected
 * markup carries no nonce, so it cannot run.
 *
 * Styles are not nonce-based: MUI (emotion) writes <style> tags and components
 * use style attributes, and a nonce in style-src would make browsers ignore
 * 'unsafe-inline'. Inline styles cannot run code.
 *
 * Production's Traefik sends HSTS, nosniff, the referrer policy and
 * frame-deny as well; they are repeated here so development looks the same and
 * a page served without the edge proxy is still covered.
 */
export class SecurityHeaders {
  static readonly NONCE_HEADER = "x-nonce";
  private static readonly CSP_HEADER = "Content-Security-Policy";

  private constructor(
    readonly nonce: string,
    private readonly policy: string,
  ) {}

  static forRequest(options: SecurityHeaderOptions): SecurityHeaders {
    const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
    return new SecurityHeaders(
      nonce,
      SecurityHeaders.policyFor(nonce, options).toString(),
    );
  }

  private static policyFor(
    nonce: string,
    { apiOrigin, development }: SecurityHeaderOptions,
  ): ContentSecurityPolicy {
    const policy = new ContentSecurityPolicy()
      .allow("default-src", "'self'")
      // React's dev tooling evaluates code; production never does.
      .allow(
        "script-src",
        "'self'",
        `'nonce-${nonce}'`,
        "'strict-dynamic'",
        ...(development ? ["'unsafe-eval'"] : []),
      )
      .allow("style-src", "'self'", "'unsafe-inline'")
      // Product images come from the catalogue CDN, CJ's CDN until copied,
      // and Google avatars: any HTTPS host, never script.
      .allow(
        "img-src",
        "'self'",
        "data:",
        "blob:",
        "https:",
        ...(development ? LOCAL_IMAGE_ORIGINS : []),
      )
      .allow("font-src", "'self'", "data:")
      .allow("connect-src", "'self'", ...STRIPE_API, TURNSTILE)
      .allow("frame-src", ...STRIPE_FRAMES, TURNSTILE)
      .allow("worker-src", "'self'", "blob:")
      .allow("object-src", "'none'")
      .allow("base-uri", "'self'")
      .allow("form-action", "'self'")
      .allow("frame-ancestors", "'none'");

    if (apiOrigin) policy.allow("connect-src", apiOrigin);
    if (development) {
      // The dev server's hot reload socket, and the gateway on either local name.
      policy.allow("connect-src", "ws:", ...LOCAL_API_ORIGINS);
    } else {
      policy.allow("upgrade-insecure-requests");
    }
    return policy;
  }

  /** What the page being rendered reads: Next.js takes the nonce from the policy. */
  applyToRequest(headers: Headers): void {
    headers.set(SecurityHeaders.NONCE_HEADER, this.nonce);
    headers.set(SecurityHeaders.CSP_HEADER, this.policy);
  }

  applyToResponse(response: NextResponse): NextResponse {
    response.headers.set(SecurityHeaders.CSP_HEADER, this.policy);
    response.headers.set("X-Content-Type-Options", "nosniff");
    response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
    response.headers.set("X-Frame-Options", "DENY");
    // Stripe's popups (wallets, Link) need an opener; nothing else does.
    response.headers.set(
      "Cross-Origin-Opener-Policy",
      "same-origin-allow-popups",
    );
    // Features the storefront never uses are off; payment only for Stripe.
    response.headers.set(
      "Permissions-Policy",
      'camera=(), microphone=(), geolocation=(), usb=(), payment=(self "https://js.stripe.com")',
    );
    return response;
  }
}
