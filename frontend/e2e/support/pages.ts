// Page objects: what a shopper can do on each page, in the shopper's terms,
// found the way assistive technology finds it (roles and accessible names).
import { expect, type Locator, type Page } from "@playwright/test";
import type { Credentials } from "./accounts";

/** "C$1,234.50" or "$12.00" -> 1234.5 */
export const priceOf = (text: string): number => Number(text.replace(/[^0-9.]/g, ""));

export class SignInPage {
    constructor(private readonly page: Page) {}

    async signIn(credentials: Pick<Credentials, "email" | "password">): Promise<void> {
        await this.attempt(credentials);
        await this.page.waitForURL("**/cart");
    }

    /** Signs in if these credentials still work; false when the page refuses them. */
    async trySignIn(credentials: Pick<Credentials, "email" | "password">): Promise<boolean> {
        await this.attempt(credentials);
        const outcome = await Promise.race([
            this.page.waitForURL("**/cart").then(() => true),
            this.page
                .getByText(/Incorrect email or password|User is not verified|Account is deactivated/)
                .waitFor()
                .then(() => false),
        ]);
        return outcome;
    }

    /** Fills the form and sends it, whatever the answer. */
    async attempt({ email, password }: Pick<Credentials, "email" | "password">): Promise<void> {
        await this.page.goto("/login");
        await this.page.getByLabel("Email").fill(email);
        await this.page.getByLabel("Password", { exact: true }).fill(password);
        await this.submit().click();
    }

    async signOut(): Promise<void> {
        await this.page.getByRole("button", { name: "Account" }).click();
        await this.page.getByRole("button", { name: "Logout" }).click();
        // Signed out once the menu offers to sign in again.
        await expect(async () => {
            await this.page.getByRole("button", { name: "Account" }).click();
            await expect(this.page.getByRole("link", { name: "Login" })).toBeVisible({ timeout: 2_000 });
        }).toPass();
    }

    /** Enabled once Cloudflare's test widget has handed over its token. */
    submit(): Locator {
        return this.page.getByRole("button", { name: "Sign In" });
    }
}

export class Shop {
    readonly section: Locator;

    constructor(private readonly page: Page) {
        this.section = page.getByRole("region", { name: "Featured Selection" });
    }

    async open(): Promise<void> {
        await this.page.goto("/");
        await expect(this.cards().first()).toBeVisible();
    }

    /** One link per product card shown. */
    cards(): Locator {
        return this.section.getByRole("heading", { level: 3 }).getByRole("link");
    }

    async openFilters(): Promise<void> {
        await this.section.getByRole("button", { name: "Filters" }).click();
    }

    /** "Showing 12 of 207" -> [12, 207] */
    async shownOfTotal(): Promise<[number, number]> {
        const text = await this.section.getByText(/^Showing \d+ of \d+$/).first().textContent();
        const [, shown, total] = /Showing (\d+) of (\d+)/.exec(text ?? "") ?? [];
        return [Number(shown), Number(total)];
    }
}

export class ProductPage {
    constructor(private readonly page: Page) {}

    async open(productId: string): Promise<void> {
        await this.page.goto(`/products/${productId}`);
        await expect(this.addToCart()).toBeVisible();
    }

    name(): Locator {
        return this.page.getByRole("heading", { level: 1 });
    }

    /** The option rows (Color, Size, ...), each a group named "<option> <chosen value>". */
    options(): Locator {
        return this.page.getByRole("group").filter({ has: this.page.locator("legend") });
    }

    option(name: string): Locator {
        return this.page.getByRole("group", { name: new RegExp(`^${name}\\b`) });
    }

    /** The units on offer, as the page states them (at most 100). */
    async availableUnits(): Promise<number> {
        const value = this.page.getByText("QUANTITY", { exact: true }).locator("xpath=following-sibling::p");
        return Number(await value.textContent());
    }

    quantity(): Locator {
        return this.page.getByRole("status", { name: "Quantity" });
    }

    increase(): Locator {
        return this.page.getByRole("button", { name: "Increase quantity" });
    }

    addToCart(): Locator {
        return this.page.getByRole("button", { name: "Add To Cart" });
    }

    wishlistToggle(): Locator {
        return this.page.getByRole("button", { name: /wishlist$/ });
    }
}

export class CartPage {
    constructor(private readonly page: Page) {}

    async open(): Promise<void> {
        await this.page.goto("/cart");
    }

    line(productName: string): Locator {
        return this.page.getByRole("group", { name: productName, exact: true });
    }

    async subtotal(): Promise<number> {
        const row = this.page.getByText("Subtotal", { exact: true }).locator("..");
        // The cart re-prices against the server; wait until that has finished.
        await expect(this.page.getByText("Checking current prices…")).toHaveCount(0);
        return priceOf((await row.locator("span").nth(1).textContent()) ?? "");
    }

    checkout(): Locator {
        return this.page.getByRole("button", { name: "Checkout", exact: true });
    }
}

/** A Canadian address the account page saves and checkout starts from. */
export interface TestAddress {
    label: string;
    name: string;
    street: string;
    city: string;
    province: string;
    postalCode: string;
    phone: string;
}

export class AccountPage {
    constructor(private readonly page: Page) {}

    async open(): Promise<void> {
        await this.page.goto("/account");
        await expect(this.page.getByRole("heading", { name: "Profile" })).toBeVisible();
    }

    address(label: string): Locator {
        return this.page.getByRole("listitem").filter({ hasText: label });
    }

    async addAddress(address: TestAddress): Promise<void> {
        await this.page.getByRole("button", { name: "Add", exact: true }).click();
        await this.page.getByLabel("Label (Home, Work)").fill(address.label);
        await this.page.getByLabel("Recipient name").fill(address.name);
        await this.page.getByLabel("Street address").fill(address.street);
        await this.page.getByLabel("City").fill(address.city);
        await this.page.getByLabel("Province or territory").selectOption(address.province);
        await this.page.getByLabel("Postal code").fill(address.postalCode);
        await this.page.getByLabel("Phone (optional)").last().fill(address.phone);
        await this.page.getByRole("button", { name: "Add address" }).click();
        await expect(this.page.getByText("Address saved")).toBeVisible();
        await expect(this.address(address.label)).toBeVisible();
    }
}

export class ProductPicker {
    constructor(private readonly page: Page) {}

    /**
     * The cheapest product the shop can sell now: shop sorted by price, then
     * the first product page whose Add To Cart is enabled, skipping `exclude`.
     */
    async cheapestBuyable(exclude: readonly string[] = [], maxTries = 10): Promise<{ id: string; name: string }> {
        const shop = new Shop(this.page);
        await shop.open();
        await shop.section.getByRole("combobox", { name: "Sort products" }).selectOption({ label: "Price: low to high" });
        const hrefs = await shop
            .cards()
            .evaluateAll((links) => links.slice(0, 40).map((link) => link.getAttribute("href") ?? ""));
        const product = new ProductPage(this.page);
        const candidates = hrefs.map((href) => href.split("/").pop() ?? "").filter((id) => !exclude.includes(id));
        for (const id of candidates.slice(0, maxTries)) {
            await product.open(id);
            if (await product.addToCart().isEnabled()) {
                return { id, name: (await product.name().textContent())?.trim() ?? "" };
            }
        }
        throw new Error(`None of the ${maxTries} cheapest products can be bought now`);
    }
}

export class CheckoutPage {
    constructor(private readonly page: Page) {}

    /** The order summary's figure for `term` (Subtotal, Shipping, Total). */
    async amount(term: string): Promise<number> {
        const value = this.page.locator("dt", { hasText: new RegExp(`^${term}$`) }).locator("xpath=following-sibling::dd");
        return priceOf((await value.textContent()) ?? "");
    }

    /** Stripe's card form, in its own frame. 4242... is Stripe's always-approved test card. */
    async payWithTestCard(postalCode: string): Promise<void> {
        const card = this.page.frameLocator('iframe[title="Secure payment input frame"]').first();
        await card.getByPlaceholder("1234 1234 1234 1234").fill("4242424242424242");
        await card.getByPlaceholder("MM / YY").fill("12 / 34");
        await card.getByPlaceholder("CVC").fill("123");
        const postal = card.getByLabel(/postal code/i);
        if (await postal.isVisible()) await postal.fill(postalCode);
        await this.page.getByRole("button", { name: "Place order" }).click();
    }
}
