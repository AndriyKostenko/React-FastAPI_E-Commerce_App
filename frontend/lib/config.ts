import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

export const env = createEnv({
    client: {
        NEXT_PUBLIC_APP_URL: z.url().optional(),
        NEXT_PUBLIC_API_ORIGIN: z.url().optional(),
        NEXT_PUBLIC_API_VERSION: z.string().min(1).optional(),
        NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY: z.string().min(1),
        NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY: z.string().min(1).optional(),
        NEXT_PUBLIC_TURNSTILE_SITE_KEY: z.string().min(1).optional(),
    },
    runtimeEnv: {
        NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
        NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN,
        NEXT_PUBLIC_API_VERSION: process.env.NEXT_PUBLIC_API_VERSION,
        NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY,
        NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY,
        NEXT_PUBLIC_TURNSTILE_SITE_KEY: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY,
        },
    server: {},
});

class AppSettings {
    // ── Defaults ────────────────────────────────────────────────────────────
    private static readonly DEFAULT_APP_URL = "http://localhost:30000";
    private static readonly DEFAULT_API_ORIGIN = "http://localhost:8000";
    private static readonly DEFAULT_API_VERSION = "v1";
    // Cloudflare's always-pass test widget: it issues a dummy token that the
    // test secret dev.sh stores for user-service accepts. Development only.
    private static readonly TEST_TURNSTILE_SITE_KEY = "1x00000000000000000000AA";

    // ── Helpers ─────────────────────────────────────────────────────────────
    private static normalizeUrl(value: string): string {
        return value.replace(/\/+$/, "");
    }

    private static joinUrl(base: string, path: string): string {
        return `${AppSettings.normalizeUrl(base)}/${path.replace(/^\/+/, "")}`;
    }

    private static inferBrowserApiOrigin(): string | undefined {
        if (typeof window === "undefined") {
            return undefined;
        }
        const { protocol, hostname } = window.location;
        return `${protocol}//${hostname}:8000`;
    }

    // ── Public shape ─────────────────────────────────────────────────────────
    public readonly app: {
        url: string;
    };

    public readonly api: {
        origin: string;
        version: string;
        baseUrl: string;
        /** Build a versioned URL: /api/v1/<path> */
        versioned: (path: string) => string;
        /** Build an unversioned URL off the API origin */
        root: (path: string) => string;
        /** Gateway endpoints (go through /api/v1/) */
        endpoints: {
            authLogin: string;
            authRefresh: string;
            authLogout: string;
            authRegister: string;
            googleLogin: string;
            activate: string;
            forgotPassword: string;
            passwordReset: string;
            me: string;
            userById: (userId: string) => string;
            changePassword: string;
            avatar: string;
            wishlist: string;
            wishlistItems: string;
            wishlistItem: (itemId: string) => string;
            addresses: string;
            addressById: (addressId: string) => string;
            addressDefault: (addressId: string) => string;
            categories: string;
            customizationPricing: string;
            productsDetailed: string;
            productDetailed: (productId: string) => string;
            imageGenerations: string;
            imageGenerationsStatus: (jobId: string) => string;
            orders: string;
            orderById: (orderId: string) => string;
            orderDetails: (orderId: string) => string;
            cancelOrder: (orderId: string) => string;
            ordersByUserId: (userId: string) => string;
            checkoutQuote: string;
            cartPrices: string;
            checkout: string;
            productionJobs: string;
            productionJob: (jobId: string) => string;
            productionJobArtwork: (jobId: string) => string;
            productionJobPackingSlip: (jobId: string) => string;
            productionJobAction: (jobId: string, action: string) => string;
    };
    /** Direct backend endpoints (bypass versioned gateway) */
    backendEndpoints: {
        orders: string;
        users: string;
        products: string;
        updateProductAvailability: (id: string, inStock: boolean) => string;
        deleteProduct: (id: string) => string;
        orderById: (orderId: string) => string;
        updateOrder: (orderId: string) => string;
        reviewProduct: (productId: string) => string;
    };
    };

    public readonly stripe: {publishableKey: string;};

    /** Cloudflare Turnstile on sign-up, sign-in and forgot-password. */
    public readonly humanCheck: {siteKey: string;};

    constructor() {
        const origin  = env.NEXT_PUBLIC_API_ORIGIN  ?? AppSettings.inferBrowserApiOrigin() ?? AppSettings.DEFAULT_API_ORIGIN;
        const version = env.NEXT_PUBLIC_API_VERSION ?? AppSettings.DEFAULT_API_VERSION;
        const baseUrl = AppSettings.joinUrl(origin, `api/${version}`);

        this.app = {
            url: env.NEXT_PUBLIC_APP_URL ?? AppSettings.DEFAULT_APP_URL,
        };

        this.api = {
            origin,
            version,
            baseUrl,
            versioned: (path: string) => AppSettings.joinUrl(baseUrl, path),
            root:      (path: string) => AppSettings.joinUrl(origin,  path),
            endpoints: {
            authLogin:            AppSettings.joinUrl(baseUrl, "login"),
            authRefresh:          AppSettings.joinUrl(baseUrl, "refresh"),
            authLogout:           AppSettings.joinUrl(baseUrl, "logout"),
            authRegister:         AppSettings.joinUrl(baseUrl, "register"),
            googleLogin:          AppSettings.joinUrl(baseUrl, "google-login"),
            activate:             AppSettings.joinUrl(baseUrl, "activate"),
            forgotPassword:       AppSettings.joinUrl(baseUrl, "forgot-password"),
            passwordReset:        AppSettings.joinUrl(baseUrl, "password-reset"),
            me:                   AppSettings.joinUrl(baseUrl, "me"),
            userById:             (userId: string)    => AppSettings.joinUrl(baseUrl, `users/${userId}`),
            changePassword:       AppSettings.joinUrl(baseUrl, "users/me/password"),
            avatar:               AppSettings.joinUrl(baseUrl, "users/me/avatar"),
            wishlist:             AppSettings.joinUrl(baseUrl, "wishlists/me"),
            wishlistItems:        AppSettings.joinUrl(baseUrl, "wishlists/me/items"),
            wishlistItem:         (itemId: string) => AppSettings.joinUrl(baseUrl, `wishlists/me/items/${itemId}`),
            addresses:            AppSettings.joinUrl(baseUrl, "users/me/addresses"),
            addressById:          (addressId: string) => AppSettings.joinUrl(baseUrl, `users/me/addresses/${addressId}`),
            addressDefault:       (addressId: string) => AppSettings.joinUrl(baseUrl, `users/me/addresses/${addressId}/default`),
            categories:          AppSettings.joinUrl(baseUrl, "categories"),
            customizationPricing: AppSettings.joinUrl(baseUrl, "customization/pricing"),
            productsDetailed:     AppSettings.joinUrl(baseUrl, "products/detailed"),
            productDetailed:      (productId: string) => AppSettings.joinUrl(baseUrl, `products/${productId}/detailed`),
            imageGenerations: AppSettings.joinUrl(baseUrl, "images/generations"),
            imageGenerationsStatus: (jobId: string) => AppSettings.joinUrl(baseUrl, `images/generations/${jobId}/status`),
            orders:               AppSettings.joinUrl(baseUrl, "orders"),
            orderById:            (orderId: string)   => AppSettings.joinUrl(baseUrl, `orders/${orderId}`),
            orderDetails:         (orderId: string)   => AppSettings.joinUrl(baseUrl, `orders/${orderId}/details`),
            cancelOrder:          (orderId: string)   => AppSettings.joinUrl(baseUrl, `orders/${orderId}/cancel`),
            ordersByUserId:       (userId: string)    => AppSettings.joinUrl(baseUrl, `orders/user/${userId}`),
            checkoutQuote:        AppSettings.joinUrl(baseUrl, "checkout/quote"),
            cartPrices:           AppSettings.joinUrl(baseUrl, "cart/prices"),
            checkout:             AppSettings.joinUrl(baseUrl, "checkout"),
            productionJobs:           AppSettings.joinUrl(baseUrl, "admin/production/jobs"),
            productionJob:            (jobId: string) => AppSettings.joinUrl(baseUrl, `admin/production/jobs/${jobId}`),
            productionJobArtwork:     (jobId: string) => AppSettings.joinUrl(baseUrl, `admin/production/jobs/${jobId}/artwork`),
            productionJobPackingSlip: (jobId: string) => AppSettings.joinUrl(baseUrl, `admin/production/jobs/${jobId}/packing-slip`),
            productionJobAction:      (jobId: string, action: string) => AppSettings.joinUrl(baseUrl, `admin/production/jobs/${jobId}/${action}`),
            },
            backendEndpoints: {
            orders:                     AppSettings.joinUrl(origin, "orders"),
            users:                      AppSettings.joinUrl(origin, "admin/users"),
            products:                   AppSettings.joinUrl(origin, "products"),
            updateProductAvailability:  (id: string, inStock: boolean) => AppSettings.joinUrl(origin, `update_product_availability/${id}?in_stock=${inStock}`),
            deleteProduct:              (id: string)      => AppSettings.joinUrl(origin, `delete_product/${id}`),
            orderById:                  (orderId: string) => AppSettings.joinUrl(origin, `orders/${orderId}`),
            updateOrder:                (orderId: string) => AppSettings.joinUrl(origin, `orders/${orderId}`),
            reviewProduct:              (productId: string) => AppSettings.joinUrl(origin, `review/product/${productId}`),
            },
            };

        this.stripe = {
            publishableKey:
            process.env.NODE_ENV === "production"
            ? env.NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY ?? env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY
            : env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY,
        };

        this.humanCheck = { siteKey: AppSettings.turnstileSiteKey() };
    }

    /**
     * No test-key fallback in production: the test widget's dummy token is
     * refused by a real secret, so every sign-in would fail without a word.
     * Failing the build names the missing setting instead.
     */
    private static turnstileSiteKey(): string {
        if (env.NEXT_PUBLIC_TURNSTILE_SITE_KEY) return env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
        if (process.env.NODE_ENV === "production") {
            throw new Error("NEXT_PUBLIC_TURNSTILE_SITE_KEY is required in production (Cloudflare Turnstile site key)");
        }
        return AppSettings.TEST_TURNSTILE_SITE_KEY;
    }
}

export const settings = new AppSettings();
