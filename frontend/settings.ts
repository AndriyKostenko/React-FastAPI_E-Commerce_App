import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

const DEFAULT_APP_URL = "http://localhost:30000";
const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";
const DEFAULT_API_VERSION = "v1";

const normalizeUrl = (value: string) => value.replace(/\/+$/, "");
const joinUrl = (base: string, path: string) =>
	`${normalizeUrl(base)}/${path.replace(/^\/+/, "")}`;

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
		NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://127.0.0.1:8000",
		NEXT_PUBLIC_API_VERSION: process.env.NEXT_PUBLIC_API_VERSION,
		NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY,
		NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY,
	},
	server: {},
});

class AppSettings {
	public readonly appUrl: string;
	public readonly apiOrigin: string;
	public readonly apiVersion: string;
	public readonly apiBaseUrl: string;
	public readonly stripePublishableKey: string;

	public readonly api: {
		origin: string;
		version: string;
		baseUrl: string;
		versioned: (path: string) => string;
		root: (path: string) => string;
		endpoints: {
			authLogin: string;
			authRegister: string;
			categories: string;
			productsDetailed: string;
			productDetailed: (productId: string) => string;
			orders: string;
			orderById: (orderId: string) => string;
			cancelOrder: (orderId: string) => string;
			ordersByUserId: (userId: string) => string;
			paymentsCreateIntent: string;
		};
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

	public readonly stripe: {
		publishableKey: string;
	};

	constructor() {
		this.appUrl = env.NEXT_PUBLIC_APP_URL ?? DEFAULT_APP_URL;
		this.apiOrigin = env.NEXT_PUBLIC_API_ORIGIN ?? DEFAULT_API_ORIGIN;
		this.apiVersion = env.NEXT_PUBLIC_API_VERSION ?? DEFAULT_API_VERSION;
		this.apiBaseUrl = joinUrl(this.apiOrigin, `api/${this.apiVersion}`);
		this.stripePublishableKey =
			process.env.NODE_ENV === "production"
				? env.NEXT_PUBLIC_STRIPE_PROD_PUBLISHABLE_KEY ?? env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY
				: env.NEXT_PUBLIC_STRIPE_TEST_PUBLISHABLE_KEY;

		this.api = {
			origin: this.apiOrigin,
			version: this.apiVersion,
			baseUrl: this.apiBaseUrl,
			versioned: (path: string) => joinUrl(this.apiBaseUrl, path),
			root: (path: string) => joinUrl(this.apiOrigin, path),
			endpoints: {
				authLogin: joinUrl(this.apiBaseUrl, "login"),
				authRegister: joinUrl(this.apiBaseUrl, "register"),
				categories: joinUrl(this.apiBaseUrl, "categories"),
				productsDetailed: joinUrl(this.apiBaseUrl, "products/detailed"),
				productDetailed: (productId: string) => joinUrl(this.apiBaseUrl, `products/${productId}/detailed`),
				orders: joinUrl(this.apiBaseUrl, "orders"),
				orderById: (orderId: string) => joinUrl(this.apiBaseUrl, `orders/${orderId}`),
				cancelOrder: (orderId: string) => joinUrl(this.apiBaseUrl, `orders/${orderId}/cancel`),
				ordersByUserId: (userId: string) => joinUrl(this.apiBaseUrl, `orders/user/${userId}`),
				paymentsCreateIntent: joinUrl(this.apiBaseUrl, "payments/create-intent"),
			},
			backendEndpoints: {
				orders: joinUrl(this.apiOrigin, "orders"),
				users: joinUrl(this.apiOrigin, "admin/users"),
				products: joinUrl(this.apiOrigin, "products"),
				updateProductAvailability: (id: string, inStock: boolean) =>
					joinUrl(this.apiOrigin, `update_product_availability/${id}?in_stock=${inStock}`),
				deleteProduct: (id: string) => joinUrl(this.apiOrigin, `delete_product/${id}`),
				orderById: (orderId: string) => joinUrl(this.apiOrigin, `orders/${orderId}`),
				updateOrder: (orderId: string) => joinUrl(this.apiOrigin, `orders/${orderId}`),
				reviewProduct: (productId: string) => joinUrl(this.apiOrigin, `review/product/${productId}`),
			},
		};

		this.stripe = {
			publishableKey: this.stripePublishableKey,
		};
	}
}

export const settings = new AppSettings();
