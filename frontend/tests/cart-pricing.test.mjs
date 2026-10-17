// Cart pricing (`POST /api/v1/cart/prices`), against the running local stack.
//
// No mocks: requests go to the real gateway, order-service and product-service,
// and the products come from the live catalogue rather than fixed ids, so the
// suite works on any local data with at least one sellable CJ variant. The
// checkout comparison signs in through the real frontend and asks CJ for
// freight, so it needs CJ reachable.
//
// Needs the stack up (`backend/local/dev.sh up`) and the session test accounts
// (`node tests/seed-session-users.mjs`). Run with:
//
//   npm run test:cart-pricing
//
// Configuration (all optional):
//   FRONTEND_URL      default http://localhost:30000
//   GATEWAY_URL       default http://127.0.0.1:8000
//   SESSION_TEST_A    default session.a@example-shop.com  (password: SESSION_TEST_A_PASSWORD)

import { describe, it, before } from "node:test";
import assert from "node:assert/strict";

// The token Cloudflare's test widget issues. Locally user-service holds the
// always-pass test secret (dev.sh), so it is accepted; a real secret refuses it.
const CAPTCHA_TOKEN = "XXXX.DUMMY.TOKEN.XXXX";

const FRONTEND = process.env.FRONTEND_URL ?? "http://localhost:30000";
const GATEWAY = `${process.env.GATEWAY_URL ?? "http://127.0.0.1:8000"}/api/v1`;
const ACCOUNT = {
    email: process.env.SESSION_TEST_A ?? "session.a@example-shop.com",
    password: process.env.SESSION_TEST_A_PASSWORD ?? "CorrectHorse1",
};
// A real Canadian address (the shop sells in Canada only); CJ prices freight to it.
const ADDRESS = {
    street: "100 King St W",
    city: "Toronto",
    province: "ON",
    postal_code: "M5X 1A9",
    country: "CA",
    country_code: "CA",
    name: "Cart Pricing Test",
    phone: "+14165550123",
};
// A UUID no product or variant has.
const UNKNOWN_ID = "00000000-0000-4000-8000-000000000000";

const toCents = (amount) => Math.round(Number(amount) * 100);

const priceCart = (products, headers = {}) =>
    fetch(`${GATEWAY}/cart/prices`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ products }),
    });

/**
 * Up to three cart lines that can be sold right now, each with the unit price
 * the catalogue itself shows for it: CJ lines at their variant's retail price,
 * catalogue lines at the product price. That price is what the cart must match.
 */
const sellableLines = async () => {
    const response = await fetch(`${GATEWAY}/products/detailed`);
    assert.equal(response.status, 200, "could not read the catalogue");
    const products = await response.json();

    const lines = [];
    for (const product of products) {
        if (!product.in_stock || product.quantity < 2) continue;
        if (product.supplier_id === "cjdropshipping") {
            const variant = (product.variants ?? []).find(
                (candidate) =>
                    candidate.active &&
                    Number(candidate.retail_price) > 0 &&
                    (candidate.inventory_num === null || candidate.inventory_num >= 2),
            );
            if (!variant) continue;
            lines.push({
                line: { id: product.id, variant_id: variant.id, quantity: 2, fulfillment_type: "cj" },
                unitCents: toCents(variant.retail_price),
            });
        } else if (Number(product.price) > 0 && !lines.some((entry) => entry.line.fulfillment_type === "catalog")) {
            lines.push({
                line: { id: product.id, quantity: 1, fulfillment_type: "catalog" },
                unitCents: toCents(product.price),
            });
        }
        if (lines.length === 3) break;
    }
    assert.ok(
        lines.some((entry) => entry.line.fulfillment_type === "cj"),
        "the catalogue has no sellable CJ variant to price; sync one first",
    );
    return lines;
};

// ---- Signing in, as tests/session-isolation.test.mjs does ----

/** Cookie header built from every Set-Cookie a response sent. */
const cookieHeader = (response, previous = "") => {
    const jar = new Map(
        previous
            .split("; ")
            .filter(Boolean)
            .map((pair) => {
                const [name, ...rest] = pair.split("=");
                return [name, rest.join("=")];
            }),
    );
    for (const raw of response.headers.getSetCookie()) {
        const [pair] = raw.split(";");
        const [name, ...rest] = pair.split("=");
        if (rest.join("=") === "") {
            jar.delete(name);
        } else {
            jar.set(name, rest.join("="));
        }
    }
    return [...jar].map(([name, value]) => `${name}=${value}`).join("; ");
};

/** Signs in through NextAuth as the login form does; returns the cookie header. */
const signIn = async ({ email, password }) => {
    const csrfResponse = await fetch(`${FRONTEND}/api/auth/csrf`);
    let cookies = cookieHeader(csrfResponse);
    const { csrfToken } = await csrfResponse.json();
    const response = await fetch(`${FRONTEND}/api/auth/callback/credentials`, {
        method: "POST",
        redirect: "manual",
        headers: { "Content-Type": "application/x-www-form-urlencoded", Cookie: cookies },
        body: new URLSearchParams({ csrfToken, email, password, captchaToken: CAPTCHA_TOKEN, json: "true" }),
    });
    cookies = cookieHeader(response, cookies);
    assert.equal(
        response.status,
        200,
        `sign-in for ${email} failed with ${response.status} (seed the account, or wait out the login rate limit)`,
    );
    return cookies;
};

describe("cart pricing", { concurrency: false }, () => {
    let lines;

    before(async () => {
        lines = await sellableLines();
    });

    it("prices a guest's cart with no token, at the catalogue's current prices", async () => {
        // Each line carries a price as a stale cart line would; the server must
        // ignore it and price from the catalogue.
        const products = lines.map(({ line }) => ({ ...line, price: 0.01 }));
        const response = await priceCart(products);
        assert.equal(response.status, 200, `guest pricing answered ${response.status}`);
        const prices = await response.json();

        assert.equal(prices.currency, "cad");
        assert.equal(prices.items.length, lines.length, "a line is missing from the prices");
        prices.items.forEach((item, index) => {
            const { line, unitCents } = lines[index];
            // Same order as the request: the cart pairs prices with lines by position.
            assert.equal(item.product_id, line.id, `line ${index} came back out of order`);
            assert.equal(item.quantity, line.quantity);
            assert.equal(
                toCents(item.unit_price),
                unitCents,
                `line ${index} priced at ${item.unit_price}, the catalogue says ${unitCents / 100}`,
            );
        });
        const expectedSubtotal = lines.reduce((sum, { line, unitCents }) => sum + unitCents * line.quantity, 0);
        assert.equal(toCents(prices.subtotal_amount), expectedSubtotal, "subtotal is not the sum of the lines");
    });

    it("gives the same unit prices and subtotal as the checkout quote for the same lines", async () => {
        const products = lines.map(({ line }) => line);
        const cookies = await signIn(ACCOUNT);

        const [cartResponse, quoteResponse] = await Promise.all([
            priceCart(products),
            // The checkout quote goes through the same-origin proxy, as the checkout page does.
            fetch(`${FRONTEND}/api/gateway/api/v1/checkout/quote`, {
                method: "POST",
                headers: { Cookie: cookies, Origin: FRONTEND, "Content-Type": "application/json" },
                body: JSON.stringify({ products, address: ADDRESS, shipping_logistic_name: null }),
            }),
        ]);
        assert.equal(cartResponse.status, 200);
        assert.equal(
            quoteResponse.status,
            200,
            `checkout quote answered ${quoteResponse.status}: ${await quoteResponse.clone().text()}`,
        );
        const cart = await cartResponse.json();
        const quote = await quoteResponse.json();

        assert.equal(toCents(cart.subtotal_amount), toCents(quote.subtotal_amount), "cart and checkout subtotals differ");
        assert.equal(quote.products.length, cart.items.length);
        cart.items.forEach((item, index) => {
            assert.equal(quote.products[index].product_id, item.product_id);
            assert.equal(
                toCents(quote.products[index].unit_price),
                toCents(item.unit_price),
                `line ${index}: cart ${item.unit_price}, checkout ${quote.products[index].unit_price}`,
            );
        });
    });

    it("marks an unsellable line with product-service's reason and still prices the others", async () => {
        const cjLine = lines.find(({ line }) => line.fulfillment_type === "cj").line;
        const cases = [
            { name: "inactive variant", line: { ...cjLine, variant_id: UNKNOWN_ID }, reason: /not active/ },
            { name: "unknown product", line: { ...cjLine, id: UNKNOWN_ID }, reason: /not found/ },
        ];
        for (const { name, line, reason } of cases) {
            const response = await priceCart([lines[0].line, line]);
            assert.equal(response.status, 200, `${name}: answered ${response.status}`);
            const prices = await response.json();
            assert.equal(prices.items.length, 2, `${name}: a line is missing`);

            const [sellable, unsellable] = prices.items;
            assert.equal(sellable.available, true, `${name}: the sellable line was marked unavailable`);
            assert.equal(toCents(sellable.unit_price), lines[0].unitCents, `${name}: the sellable line lost its price`);

            assert.equal(unsellable.available, false, `${name}: the unsellable line was priced`);
            assert.equal(unsellable.unit_price, null);
            assert.equal(unsellable.product_id, line.id, `${name}: the unavailable line is not the one sent`);
            assert.match(unsellable.unavailable_reason ?? "", reason, `${name}: unexpected reason "${unsellable.unavailable_reason}"`);
            // The public route must not show where the services live.
            for (const leak of ["http", "127.0.0.1", "localhost", ":800", "order-quote"]) {
                assert.ok(!unsellable.unavailable_reason.includes(leak), `${name}: reason leaks "${leak}"`);
            }

            // The subtotal counts only what can be bought.
            assert.equal(
                toCents(prices.subtotal_amount),
                lines[0].unitCents * lines[0].line.quantity,
                `${name}: the subtotal includes the unavailable line`,
            );
        }
    });

    it("marks a custom line whose design the image service did not issue", async () => {
        // Well-formed but unsigned: the token is not the image service's signature.
        const forged = {
            quantity: 1,
            fulfillment_type: "custom",
            customization: {
                design_asset: {
                    key: `generated-designs/2026/10/${"a".repeat(32)}.png`,
                    width_px: 4096,
                    height_px: 4096,
                    embedded_dpi: 300,
                    sha256: "b".repeat(64),
                    token: "0".repeat(43),
                },
                prompt: "A mountain at sunrise",
                style: "Watercolor",
                size: "M",
                garment_color: "black",
                placement: "Full Back",
                gender: "X",
            },
        };
        const response = await priceCart([lines[0].line, forged]);
        assert.equal(response.status, 200, `answered ${response.status}: ${await response.clone().text()}`);
        const prices = await response.json();
        assert.equal(prices.items[0].available, true);
        assert.equal(prices.items[1].available, false, "a forged design was priced");
        assert.equal(prices.items[1].unit_price, null);
        assert.match(prices.items[1].unavailable_reason ?? "", /not issued by the image service/);
    });

    it("keeps the checkout quote all or nothing for the same unsellable line", async () => {
        const cjLine = lines.find(({ line }) => line.fulfillment_type === "cj").line;
        const cookies = await signIn(ACCOUNT);
        const response = await fetch(`${FRONTEND}/api/gateway/api/v1/checkout/quote`, {
            method: "POST",
            headers: { Cookie: cookies, Origin: FRONTEND, "Content-Type": "application/json" },
            body: JSON.stringify({
                products: [lines[0].line, { ...cjLine, variant_id: UNKNOWN_ID }],
                address: ADDRESS,
                shipping_logistic_name: null,
            }),
        });
        // An order cannot be placed without the line, so it is not quoted without it.
        assert.equal(response.status, 422, `the checkout quote answered ${response.status}`);
    });

    it("refuses an empty cart and a line without a product", async () => {
        const empty = await priceCart([]);
        assert.equal(empty.status, 422, "an empty cart was priced");

        const noProduct = await priceCart([{ quantity: 1, fulfillment_type: "cj" }]);
        assert.equal(noProduct.status, 422, "a line with no product id was priced");
    });
});
