// A guest browses the shop, picks a product's options and fills a cart.
import { expect, test } from "@playwright/test";
import { CartPage, priceOf, ProductPage, Shop } from "./support/pages";

test.describe("browsing and the cart, as a guest", () => {
    test("the shop shows more products as the shopper scrolls", async ({ page }) => {
        const shop = new Shop(page);
        await shop.open();
        await expect(shop.cards()).toHaveCount(20);

        // The first steps reveal themselves on scroll; after them a button takes over.
        await shop.cards().last().scrollIntoViewIfNeeded();
        await page.mouse.wheel(0, 4_000);
        await expect.poll(() => shop.cards().count()).toBeGreaterThan(20);
    });

    test("a colour filter narrows the shop and clearing it brings everything back", async ({ page }) => {
        const shop = new Shop(page);
        await shop.open();
        await shop.openFilters();
        const [, total] = await shop.shownOfTotal();

        await shop.section.getByRole("button", { name: "Black", exact: true }).click();
        const [shown] = await shop.shownOfTotal();
        expect(shown).toBeGreaterThan(0);
        expect(shown).toBeLessThan(total);
        await expect(shop.section.getByRole("button", { name: "Filters" })).toContainText("1");

        await shop.section.getByRole("button", { name: "Clear all" }).click();
        expect((await shop.shownOfTotal())[0]).toBe(total);
    });

    test("a product's options, stock cap and cart line", async ({ page }) => {
        const shop = new Shop(page);
        await shop.open();
        const card = shop.cards().first();
        await card.click();
        await page.waitForURL("**/products/**");

        const product = new ProductPage(page);
        const name = (await product.name().textContent())?.trim() ?? "";
        expect(name).not.toBe("");

        // Every option row names the value it has chosen, and the chosen value is pressed.
        for (const row of await product.options().all()) {
            await expect(row.getByRole("button", { pressed: true })).toHaveCount(1);
        }

        // The stepper stops at the units on offer, which the page shows as at most 100.
        const available = await product.availableUnits();
        expect(available).toBeGreaterThan(0);
        expect(available).toBeLessThanOrEqual(100);
        const steps = Math.min(available, 3);
        for (let i = 0; i < steps; i += 1) await product.increase().click();
        await expect(product.quantity()).toHaveText(String(Math.min(1 + steps, available)));

        const unitPrice = priceOf((await page.locator(".font-price-lg").first().textContent()) ?? "");
        await product.addToCart().click();
        await expect(page.getByText("Product added to cart").first()).toBeVisible();

        const cart = new CartPage(page);
        await cart.open();
        const line = cart.line(name);
        await expect(line).toBeVisible();
        const quantity = Math.min(1 + steps, available);
        await expect(line.getByRole("status", { name: "Quantity" })).toHaveText(String(quantity));
        expect(await cart.subtotal()).toBeCloseTo(unitPrice * quantity, 2);
        await expect(page.getByRole("button", { name: "Login to Checkout" })).toBeVisible();

        await line.getByRole("button", { name: "Decrease quantity" }).click();
        await expect(line.getByRole("status", { name: "Quantity" })).toHaveText(String(quantity - 1));
        expect(await cart.subtotal()).toBeCloseTo(unitPrice * (quantity - 1), 2);

        await line.getByRole("button", { name: "Remove" }).click();
        await expect(line).toHaveCount(0);
    });
});
