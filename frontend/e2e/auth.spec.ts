// An account's life: signing up, confirming by email, signing in and out,
// getting back in after forgetting the password, and closing the account.
//
// Each run spends one of the gateway's five sign-ups and five confirmations
// an hour, and one of its three password-reset emails and resets an hour (all
// per client), so about three runs an hour fit; past that the pages show 429s.
import { expect, test } from "@playwright/test";
import { type Credentials, TestAccounts } from "./support/accounts";
import { Mailbox } from "./support/mailbox";
import { Onboarding } from "./support/onboarding";
import { AccountPage, SignInPage } from "./support/pages";

test.describe("an account's life", () => {
    test("a visitor signs up on the page, confirms by email, signs in, and closes the account", async ({ page }) => {
        const visitor = TestAccounts.fresh("visitor");
        const since = Onboarding.since();
        const signIn = new SignInPage(page);

        await test.step("signs up on the page", async () => {
            await page.goto("/register");
            await page.getByLabel("Full Name").fill(visitor.name);
            await page.getByLabel("Email").fill(visitor.email);
            await page.getByLabel("Password", { exact: true }).fill(visitor.password);
            await page.getByLabel("Repeat Password", { exact: true }).fill(visitor.password);
            await page.getByRole("button", { name: "Create Account" }).click();
            await expect(page.getByText("Check your email to finish creating your account.")).toBeVisible();
            await page.waitForURL("**/login");
        });

        await test.step("cannot sign in before opening the emailed link", async () => {
            await signIn.attempt(visitor);
            await expect(page.getByText("User is not verified")).toBeVisible();
        });

        await test.step("opens the link and signs in", async () => {
            await new Onboarding(page).confirmEmail(visitor.email, since);
            await signIn.signIn(visitor);
            const menu = page.getByRole("button", { name: "Account" });
            await menu.click();
            await expect(menu).toHaveAttribute("aria-expanded", "true");
            await expect(page.getByRole("link", { name: "Your Orders", exact: true })).toBeVisible();
        });

        await test.step("closes the account, which then cannot sign in", async () => {
            const account = new AccountPage(page);
            await account.open();
            const remove = page.getByRole("button", { name: "Delete my account" });
            await expect(remove).toBeDisabled();
            await page.getByLabel("Type DELETE to confirm").fill("DELETE");
            await remove.click();
            await page.waitForURL((url) => url.pathname === "/");

            // The same answer as a wrong password: the page never says an account is gone.
            await signIn.attempt(visitor);
            await expect(page.getByText("Incorrect email or password")).toBeVisible();
        });
    });

    test("a forgotten password is replaced through the emailed link", async ({ page }) => {
        // Kept between runs; made on the first one.
        let account: Credentials | null = TestAccounts.kept("forgetful");
        if (!account) {
            account = await new Onboarding(page).verifiedAccount("forgetful");
            TestAccounts.keep("forgetful", account);
        }
        const since = Onboarding.since();

        await page.goto("/forgot-password");
        await page.getByLabel("Email").fill(account.email);
        await page.getByRole("button", { name: "Send Reset Link" }).click();
        await expect(page.getByRole("heading", { name: "Check Your Email" })).toBeVisible();

        const email = await new Mailbox().waitFor(account.email, "Password Reset Request", since);
        await page.goto(Mailbox.linkIn(email, "/password-reset"));
        const renewed = { ...account, password: TestAccounts.newPassword() };
        await page.getByLabel("New Password", { exact: true }).fill(renewed.password);
        await page.getByLabel("Repeat New Password", { exact: true }).fill(renewed.password);
        await page.getByRole("button", { name: "Set New Password" }).click();
        await expect(page.getByText("Password updated. Sign in with your new password.")).toBeVisible();
        TestAccounts.keep("forgetful", renewed);

        const signIn = new SignInPage(page);
        await signIn.signIn(renewed);
        await signIn.signOut();
    });

    test("a sign-in error someone else wrote into the link is not shown", async ({ page }) => {
        // Only a message signed by the server is shown (lib/auth-error-link.ts);
        // a forged one would let anyone put words on our login page.
        await page.goto("/login?authError=Your%20account%20is%20locked.%20Call%20555-0100&authErrorSig=forged");
        // Sign In enables once the page is hydrated and its effects have run,
        // which is when a signed message would have been shown.
        await expect(new SignInPage(page).submit()).toBeEnabled();
        await expect(page.getByText("Your account is locked")).toHaveCount(0);
    });
});
