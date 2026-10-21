// Before any journey: the stack answers and catches mail, and a shopper is
// signed in. The journeys start from that shopper's cookies
// (TestAccounts.SHOPPER_STATE).
import { existsSync } from "node:fs";
import { expect, type Page, test as setup } from "@playwright/test";
import { TestAccounts } from "../support/accounts";
import { Mailbox } from "../support/mailbox";
import { Onboarding } from "../support/onboarding";
import { SignInPage } from "../support/pages";

setup("the local stack is up and catches every email", async ({ request }) => {
    await Mailbox.assertCatching();
    const home = await request.get("/");
    expect(home.ok(), "the frontend answers: ./local/dev.sh up").toBe(true);
    const gateway = await request.get(process.env.GATEWAY_URL ?? "http://127.0.0.1:8000/health");
    expect(gateway.ok(), "the gateway answers: ./local/dev.sh up").toBe(true);
});

setup("nothing else answers for the gateway on localhost", async () => {
    // The pages call http://localhost:8000, which resolves to ::1 first. The
    // local gateway listens on 127.0.0.1 only, so anything on [::1]:8000 (an
    // old compose stack under Docker/OrbStack, say) takes those requests and
    // the journeys fail at random with empty responses.
    const squatter = await fetch("http://[::1]:8000/health", { signal: AbortSignal.timeout(2_000) }).then(
        () => true,
        () => false,
    );
    expect(squatter, "something listens on [::1]:8000 besides the local gateway: stop it (docker ps)").toBe(false);
});

/**
 * Whether these cookies still sign the shopper in. The NextAuth cookie lasts a
 * month while the gateway token behind it does not, so a page that needs the
 * token answers: /wishlist, not /account, whose profile reads the gateway
 * allows only ten a minute and the journeys need.
 */
const isSignedIn = async (page: Page): Promise<boolean> => {
    await page.goto("/wishlist");
    await expect(page.getByRole("heading", { level: 1 }).or(page.getByText(/^Sign in to see your wishlist/))).toBeVisible();
    return (await page.getByText(/^Sign in to see your wishlist/).count()) === 0;
};

setup("a shopper is signed in", async ({ browser }) => {
    const kept = TestAccounts.kept("shopper");
    const context = await browser.newContext(
        kept && existsSync(TestAccounts.SHOPPER_STATE) ? { storageState: TestAccounts.SHOPPER_STATE } : {},
    );
    const page = await context.newPage();
    try {
        if (kept && (await isSignedIn(page))) return;

        const signIn = new SignInPage(page);
        if (kept && (await signIn.trySignIn(kept))) {
            await context.storageState({ path: TestAccounts.SHOPPER_STATE });
            return;
        }
        // First run, or the kept shopper is gone (the database was reset).
        const shopper = await new Onboarding(page).verifiedAccount("shopper");
        await signIn.signIn(shopper);
        await context.storageState({ path: TestAccounts.SHOPPER_STATE });
        TestAccounts.keep("shopper", shopper);
        TestAccounts.forgetShopperReviews();
    } finally {
        await context.close();
    }
});
