import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

export const env = createEnv({
	client: {
		NEXT_PUBLIC_APP_URL: z.url().optional(),
		NEXT_PUBLIC_API_ORIGIN: z.url().optional(),
		NEXT_PUBLIC_API_VERSION: z.string().min(1).optional(),
		NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY: z.string().min(1),
		NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY: z.string().min(1).optional(),
	},
	runtimeEnv: {
		NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
		NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN,
		NEXT_PUBLIC_API_VERSION: process.env.NEXT_PUBLIC_API_VERSION,
		NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY,
		NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY,
		},
	server: {},
});

class AppSettings {
	// ── Defaults ────────────────────────────────────────────────────────────
	private static readonly DEFAULT_APP_URL = "http://localhost:30000";
	private static readonly DEFAULT_API_ORIGIN = "http://localhost:8000";
	private static readonly DEFAULT_API_VERSION = "v1";

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
			authRegister: string;
			googleLogin: string;
			activate: (token: string) => string;
			me: string;
			categories: string;
			customizationPricing: string;
			productsDetailed: string;
			productDetailed: (productId: string) => string;
			imageGenerations: string;
			imageGenerationsStatus: (jobId: string) => string;
			orders: string;
			orderById: (orderId: string) => string;
			cancelOrder: (orderId: string) => string;
			ordersByUserId: (userId: string) => string;
			paymentsCreateIntent: string;
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
			authRegister:         AppSettings.joinUrl(baseUrl, "register"),
			googleLogin:          AppSettings.joinUrl(baseUrl, "google-login"),
			activate:             (token: string) => AppSettings.joinUrl(baseUrl, `activate/${token}`),
			me:                   AppSettings.joinUrl(baseUrl, "me"),
			categories:           AppSettings.joinUrl(baseUrl, "categories"),
			customizationPricing: AppSettings.joinUrl(baseUrl, "customization/pricing"),
			productsDetailed:     AppSettings.joinUrl(baseUrl, "products/detailed"),
			productDetailed:      (productId: string) => AppSettings.joinUrl(baseUrl, `products/${productId}/detailed`),
			imageGenerations: AppSettings.joinUrl(baseUrl, "images/generations"),
			imageGenerationsStatus: (jobId: string) => AppSettings.joinUrl(baseUrl, `images/generations/${jobId}/status`),
			orders:               AppSettings.joinUrl(baseUrl, "orders"),
			orderById:            (orderId: string)   => AppSettings.joinUrl(baseUrl, `orders/${orderId}`),
			cancelOrder:          (orderId: string)   => AppSettings.joinUrl(baseUrl, `orders/${orderId}/cancel`),
			ordersByUserId:       (userId: string)    => AppSettings.joinUrl(baseUrl, `orders/user/${userId}`),
			paymentsCreateIntent: AppSettings.joinUrl(baseUrl, "payments/create-intent"),
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
	}
}

export const settings = new AppSettings();
