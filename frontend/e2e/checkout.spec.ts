// Buying, receiving and reviewing, end to end: a saved address, Stripe test
// mode, the order saga, a CJ *sandbox* order (CJ simulates its payment and
// never ships), the shipped and delivered steps played through
// `dev.sh cj-sandbox`, and the review only a delivered order allows.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { TestAccounts } from "./support/accounts";
import { Mailbox } from "./support/mailbox";
import { Onboarding } from "./support/onboarding";
import { AccountPage, CartPage, CheckoutPage, ProductPage, ProductPicker, type TestAddress } from "./support/pages";

const BACKEND = path.resolve(__dirname, "../../backend");

/** `./local/dev.sh <args>` in backend/, its output; throws on a non-zero exit. */
const devSh = (...args: string[]): string =>
    execFileSync("./local/dev.sh", args, { cwd: BACKEND, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });

const HOME: TestAddress = {
    label: "Home",
    name: "E2E Shopper",
    street: "1 Yonge St",
    city: "Toronto",
    province: "ON",
    postalCode: "M5E 1E5",
    phone: "4165550100",
};

test.use({ storageState: TestAccounts.SHOPPER_STATE });

test.beforeAll(() => {
    // Paying places a CJ order. Only ever a sandbox one: a live order is paid
    // from the CJ wallet and shipped for real.
    const mode = devSh("cj-sandbox", "mode").trim().split("\n").pop();
    if (mode !== "sandbox") {
        throw new Error(`CJ orders are "${mode}", not "sandbox": set CJ_DROPSHIPPING_SANDBOX=true and restart supplier-service.`);
    }
    // Stripe tells payment-service a card was authorized by webhook; locally
    // only the Stripe CLI forwards them, and without it the order stays pending.
    try {
        execFileSync("pgrep", ["-f", "stripe listen"]);
    } catch {
        throw new Error("Stripe webhooks are not forwarded: run `stripe listen --forward-to http://127.0.0.1:8000/api/v1/payments/webhook`.");
    }
});

test("a shopper buys a shirt, receives it and reviews it", async ({ page }) => {
    // The saga, CJ's sandbox and two tracking polls take a while.
    test.setTimeout(6 * 60_000);
    const { email } = TestAccounts.shopper();
    const mailbox = new Mailbox();
    const since = Onboarding.since();

    await test.step("a default address is saved in the account", async () => {
        const account = new AccountPage(page);
        await account.open();
        if ((await account.address(HOME.label).count()) === 0) await account.addAddress(HOME);
    });

    const product = await test.step("the cheapest buyable product goes in the cart", async () => {
        // One the kept shopper has not reviewed yet: the journey ends with a review.
        const picked = await new ProductPicker(page).cheapestBuyable(TestAccounts.reviewedByShopper());
        await new ProductPage(page).addToCart().click();
        await expect(page.getByText("Product added to cart").first()).toBeVisible();
        return picked;
    });

    await test.step("checkout prices delivery to the saved address", async () => {
        const cart = new CartPage(page);
        await cart.open();
        await expect(cart.line(product.name)).toBeVisible();
        await cart.checkout().click();
        await page.waitForURL("**/checkout");

        // The saved default fills Stripe's address form, which starts the quote.
        await expect(page.getByRole("group", { name: "Shipping" })).toBeVisible({ timeout: 45_000 });
        const checkout = new CheckoutPage(page);
        const subtotal = await checkout.amount("Subtotal");
        const shipping = await checkout.amount("Shipping");
        expect(subtotal).toBeGreaterThan(0);
        expect(await checkout.amount("Total")).toBeGreaterThanOrEqual(subtotal + shipping);
    });

    const orderId = await test.step("the test card pays and the order is placed", async () => {
        await new CheckoutPage(page).payWithTestCard(HOME.postalCode);
        await expect(page.getByText(/^Order placed\. Your card is authorized/)).toBeVisible({ timeout: 60_000 });

        await page.getByRole("button", { name: "View Your Orders" }).click();
        await page.waitForURL("**/orders**");
        await page.getByRole("link", { name: /#[0-9a-f]{8}/ }).first().click();
        await page.waitForURL("**/order/**");
        await expect(page.getByRole("list", { name: "Order progress" })).toBeVisible();
        return new URL(page.url()).pathname.split("/").pop() ?? "";
    });

    await test.step("the order is confirmed by email and sent to CJ's sandbox", async () => {
        await mailbox.waitFor(email, "Order Confirmed", since, 90_000);
        // CJ ships only a paid order: wait until we have paid it (simulated in
        // the sandbox) and CJ holds it as UNSHIPPED. Until the CJ order exists
        // the tool refuses, which reads as not yet.
        const sandboxStatus = (): string => {
            try {
                return devSh("cj-sandbox", "status", orderId);
            } catch {
                return "";
            }
        };
        await expect
            .poll(sandboxStatus, { timeout: 3 * 60_000, intervals: [5_000] })
            .toMatch(/our_status\s+paid[\s\S]*cj_status\s+UNSHIPPED/);
    });

    await test.step("CJ ships and delivers it, and the shopper is told", async () => {
        devSh("cj-sandbox", "ship", orderId);
        await mailbox.waitFor(email, "Your Order Has Shipped", since, 60_000);
        devSh("cj-sandbox", "deliver", orderId);
        await mailbox.waitFor(email, "Your Order Has Been Delivered", since, 60_000);

        await page.reload();
        const progress = page.getByRole("list", { name: "Order progress" });
        await expect(progress.getByRole("listitem").filter({ hasText: "Delivered" })).toHaveAttribute("aria-current", "step");
    });

    await test.step("a delivered product can be reviewed", async () => {
        await new ProductPage(page).open(product.id);
        await expect(page.getByRole("heading", { name: "Rate this product" })).toBeVisible();
        const comment = `Soft, true to size. (e2e ${Date.now().toString(36)})`;
        await page.getByRole("radio", { name: "5 stars" }).click();
        await page.getByLabel("Comment").fill(comment);
        await page.getByRole("button", { name: "Review Product" }).click();
        await expect(page.getByText("Product rated/commented successfully")).toBeVisible();
        TestAccounts.recordShopperReview(product.id);
        await expect(page.getByText(comment)).toBeVisible();
    });
});
