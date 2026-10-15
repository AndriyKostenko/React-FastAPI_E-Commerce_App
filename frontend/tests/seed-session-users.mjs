// Creates the two verified accounts the session tests sign in with.
//
// Local development only. It talks to user-service directly (the gateway
// limits registrations to five an hour per client) and marks the accounts
// verified in the local database through its Unix socket, as the emailed
// link would. Safe to run again: existing accounts are kept.
//
//   node tests/seed-session-users.mjs
//
// Needs the stack up: `backend/local/dev.sh up`.

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const SOCKET_DIR = process.env.LOCAL_PG_SOCKET_DIR
    ?? path.resolve(here, "../../backend/local/run");
const PG_USER = process.env.LOCAL_PG_USER ?? "postgres";
const USER_SERVICE = process.env.USER_SERVICE_URL ?? "http://127.0.0.1:8001";

const ACCOUNTS = [
    {
        name: "Session Tester A",
        email: process.env.SESSION_TEST_A ?? "session.a@example-shop.com",
        password: process.env.SESSION_TEST_A_PASSWORD ?? "CorrectHorse1",
    },
    {
        name: "Session Tester B",
        email: process.env.SESSION_TEST_B ?? "session.b@example-shop.com",
        password: process.env.SESSION_TEST_B_PASSWORD ?? "CorrectHorse2",
    },
];

const register = async ({ name, email, password }) => {
    const response = await fetch(`${USER_SERVICE}/api/v1/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
    });
    if (response.status === 201) {
        console.log(`registered ${email}`);
    } else if (response.status === 409 || response.status === 400) {
        console.log(`${email} already exists`);
    } else {
        throw new Error(`register ${email} failed with ${response.status}: ${await response.text()}`);
    }
};

const verify = (email) => {
    // A query with the value passed as a psql variable, never spliced into SQL.
    // psql interpolates :'email' only in input it reads, not in -c strings.
    const out = execFileSync(
        "psql",
        ["-h", SOCKET_DIR, "-U", PG_USER, "-d", "user_service_db", "-v", `email=${email}`, "-tA", "-q"],
        {
            encoding: "utf8",
            input: "update users set is_verified = true where email = :'email' returning id;\n",
        },
    ).trim();
    if (!out) {
        throw new Error(`no user row for ${email} to verify`);
    }
    console.log(`verified ${email} (${out})`);
};

for (const account of ACCOUNTS) {
    await register(account);
    verify(account.email);
}
