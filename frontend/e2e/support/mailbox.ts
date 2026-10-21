// The local Mailpit inbox `dev.sh mail catch` sends every email to, read
// through its HTTP API (https://mailpit.axllent.org/docs/api-v1/).
import { existsSync } from "node:fs";
import path from "node:path";

interface MailpitSummary {
    ID: string;
    Subject: string;
    Created: string;
}

interface MailpitMessage extends MailpitSummary {
    HTML: string;
    Text: string;
}

export class Mailbox {
    static readonly URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
    // dev.sh writes this file while mail is caught; without it notification-
    // service sends through the real SMTP server.
    private static readonly CATCH_FLAG = path.resolve(__dirname, "../../../backend/local/run/mail-catch");

    /** Refuses to run while emails would leave the machine. */
    static async assertCatching(): Promise<void> {
        if (!existsSync(Mailbox.CATCH_FLAG)) {
            throw new Error(
                "Emails are not caught: the journeys would mail real inboxes. Run `./local/dev.sh mail catch` in backend/ first.",
            );
        }
        const info = await fetch(`${Mailbox.URL}/api/v1/info`).catch(() => null);
        if (!info?.ok) {
            throw new Error(`Mailpit does not answer at ${Mailbox.URL}: run \`./local/dev.sh mail catch\` in backend/.`);
        }
    }

    /**
     * The newest email to `to` whose subject contains `subject`, sent after
     * `since`; waits for it, as notification-service sends from a queue.
     */
    async waitFor(to: string, subject: string, since: Date, timeoutMs = 30_000): Promise<MailpitMessage> {
        const query = encodeURIComponent(`to:"${to}" subject:"${subject}"`);
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            const response = await fetch(`${Mailbox.URL}/api/v1/search?query=${query}`);
            const { messages } = (await response.json()) as { messages: MailpitSummary[] };
            const fresh = messages.find((message) => new Date(message.Created) >= since);
            if (fresh) {
                const full = await fetch(`${Mailbox.URL}/api/v1/message/${fresh.ID}`);
                return (await full.json()) as MailpitMessage;
            }
            await new Promise((resolve) => setTimeout(resolve, 500));
        }
        throw new Error(`No email "${subject}" reached ${to} within ${timeoutMs / 1000}s`);
    }

    /** The first link in the email whose path starts with `pathPrefix` ("/activate"). */
    static linkIn(message: MailpitMessage, pathPrefix: string): string {
        const links = (message.HTML || message.Text).match(/https?:\/\/[^\s"'<>]+/g) ?? [];
        const link = links
            .map((raw) => raw.replace(/&amp;/g, "&"))
            .find((candidate) => new URL(candidate).pathname.startsWith(pathPrefix));
        if (!link) throw new Error(`No ${pathPrefix} link in "${message.Subject}"`);
        return link;
    }
}
