// The signed-in shopper's own things: profile, picture, address book and
// wishlist. Closing an account is part of auth.spec.ts.
import path from "node:path";
import { expect, test } from "@playwright/test";
import { TestAccounts } from "./support/accounts";
import { AccountPage, ProductPage, Shop } from "./support/pages";

test.describe("the shopper's account", () => {
    test.use({ storageState: TestAccounts.SHOPPER_STATE });

    test("the profile keeps a changed name", async ({ page }) => {
        const account = new AccountPage(page);
        await account.open();
        const name = `E2E Shopper ${Date.now().toString(36)}`;
        await page.getByLabel("Name", { exact: true }).fill(name);
        await page.getByRole("button", { name: "Save profile" }).click();
        await expect(page.getByText("Profile saved")).toBeVisible();

        await page.reload();
        await expect(page.getByLabel("Name", { exact: true })).toHaveValue(name);
    });

    test("a profile picture is uploaded, shown and removed", async ({ page }) => {
        const account = new AccountPage(page);
        await account.open();
        await page.getByLabel("Choose a profile picture").setInputFiles(path.join(__dirname, "fixtures/avatar.png"));
        await expect(page.getByText("Picture updated")).toBeVisible();
        // Stored in S3 under avatars/ and served from the public catalogue bucket.
        const picture = page.locator('img[src*="avatars"]').first();
        await expect(picture).toBeVisible();
        await expect.poll(() => picture.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);

        await page.getByRole("button", { name: "Remove", exact: true }).click();
        await expect(page.getByText("Picture removed")).toBeVisible();
        await expect(page.locator('img[src*="avatars"]')).toHaveCount(0);
    });

    test("an address is added to the book and deleted after a second thought", async ({ page }) => {
        const account = new AccountPage(page);
        await account.open();
        await account.addAddress({
            label: "Work",
            name: "E2E Shopper",
            street: "100 Queen St W",
            city: "Toronto",
            province: "ON",
            postalCode: "M5H 2N2",
            phone: "4165550123",
        });
        const work = account.address("Work");
        await expect(work).toContainText("100 Queen St W");

        await work.getByRole("button", { name: "Delete" }).click();
        await work.getByRole("button", { name: "Keep" }).click();
        await expect(work).toBeVisible();

        await work.getByRole("button", { name: "Delete" }).click();
        await work.getByRole("button", { name: "Delete", exact: true }).click();
        await expect(page.getByText("Address deleted")).toBeVisible();
        await expect(account.address("Work")).toHaveCount(0);
    });

    test("a product is saved to the wishlist from its page and removed from the list", async ({ page }) => {
        const shop = new Shop(page);
        await shop.open();
        await shop.cards().first().click();
        await page.waitForURL("**/products/**");
        const product = new ProductPage(page);
        const name = (await product.name().textContent())?.trim() ?? "";

        await product.wishlistToggle().click();
        await expect(page.getByText("Saved to your wishlist")).toBeVisible();
        await expect(product.wishlistToggle()).toHaveAttribute("aria-pressed", "true");

        await page.goto("/wishlist");
        const saved = page.getByRole("listitem").filter({ hasText: name });
        await expect(saved).toBeVisible();
        await saved.getByRole("button", { name: "Remove" }).click();
        await expect(page.getByText("Removed from your wishlist")).toBeVisible();
        await expect(page.getByText("Tap the heart on any product to save it here for later.")).toBeVisible();
    });
});
