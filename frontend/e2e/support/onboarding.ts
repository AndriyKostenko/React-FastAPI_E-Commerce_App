// An account ready to sign in, made the way a person makes one: signed up,
// then confirmed through the link in the email Mailpit caught.
import { expect, type Page } from "@playwright/test";
import { type Credentials, TestAccounts } from "./accounts";
import { Mailbox } from "./mailbox";

export class Onboarding {
    constructor(
        private readonly page: Page,
        private readonly mailbox = new Mailbox(),
    ) {}

    /** A moment just before now; Mailpit stamps each email with its own clock. */
    static since(): Date {
        return new Date(Date.now() - 1_000);
    }

    /** Opens the verification link sent to `email` after `since`. */
    async confirmEmail(email: string, since: Date): Promise<void> {
        const message = await this.mailbox.waitFor(email, "Email Verification", since);
        await this.page.goto(Mailbox.linkIn(message, "/activate"));
        await expect(this.page.getByRole("heading", { name: "Email Verified!" })).toBeVisible();
    }

    /** A new account, signed up through user-service and confirmed by email. */
    async verifiedAccount(role: string): Promise<Credentials> {
        const account = TestAccounts.fresh(role);
        const since = Onboarding.since();
        await TestAccounts.register(account);
        await this.confirmEmail(account.email, since);
        return account;
    }
}
