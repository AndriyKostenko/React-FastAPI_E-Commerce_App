# End-to-end journeys (Playwright)

The storefront driven through Google Chrome against the **local stack**, with
nothing mocked: the real frontend, gateway and services, Stripe test mode, a
CJ **sandbox** order, and every email caught by Mailpit. They do not run in CI,
which has no stack; CI runs lint, types, unit and component tests and the build.

## Before a run

From `backend/`:

```bash
./local/dev.sh up                 # the stack
./local/dev.sh mail catch         # every email to Mailpit (http://127.0.0.1:8025), none sent
./local/dev.sh cj-sandbox mode    # must print "sandbox" (CJ_DROPSHIPPING_SANDBOX=true)
stripe listen --forward-to http://127.0.0.1:8000/api/v1/payments/webhook   # own terminal
```

The run refuses to start when mail is not caught. The checkout journey refuses
to pay unless CJ orders are sandbox ones and Stripe webhooks are forwarded.
Without the webhooks an order stays pending.

Nothing else may listen on port 8000. The pages call `localhost:8000`, which
resolves to `::1` first, and the gateway listens on `127.0.0.1`. An old compose
stack under Docker or OrbStack that publishes 8000 takes some requests and the
journeys fail at random. `docker ps` shows it.

## Running

```bash
cd frontend
npm run test:e2e                          # everything
npx playwright test e2e/checkout.spec.ts  # one journey
npm run test:e2e:report                   # the last HTML report, with traces of failures
```

| Journey           | What it proves                                                                                                                                                                                                                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `setup/`          | Checks that the stack is up, mail is caught and nothing else holds port 8000. Then signs in the shopper the other journeys use.                                                                                                                                                                                    |
| `browse-and-cart` | Covers what a guest does:<ul><li>scroll-loading</li><li>a colour filter</li><li>a product's options and the cap of 100 on stock</li><li>cart quantities and the subtotal</li></ul>                                                                                                                                 |
| `auth`            | Covers the account lifecycle:<ul><li>sign up on the page; sign-in is refused until the emailed link is opened</li><li>sign in, then delete the account, after which sign-in is refused</li><li>forgot password, through to the emailed reset link</li><li>a forged sign-in error in the URL is not shown</li></ul> |
| `account`         | Covers the profile name, the picture (S3), the address book and the wishlist.                                                                                                                                                                                                                                      |
| `checkout`        | Covers buying and receiving an order:<ul><li>saved address, delivery quote, Stripe test card</li><li>order confirmed by email, CJ sandbox order paid</li><li>shipped and delivered (through `dev.sh cj-sandbox`), each with its email</li><li>a review, which only a delivered order allows</li></ul>              |

## Accounts and limits

The gateway limits each client per hour to:

- 5 sign-ups
- 5 email confirmations
- 3 password-reset emails
- 3 resets

It also limits sign-ins to 5 a minute, and a user's own profile reads to 10 a minute.

So the shopper and the password-reset account are kept between runs, in `e2e/.auth/` (git-ignored, with the shopper's cookies). They're recreated only when they stop working. Each run makes one new visitor, which deletes itself.

About three runs an hour fit. Beyond that, the pages answer "Too many attempts". To start over with new accounts, delete `e2e/.auth/`.

Every address is `e2e.<role>.<run>@example-shop.com`. The domain has to pass user-service's mail-domain check, and its mail never leaves the machine while `mail catch` is on.

Each checkout run leaves behind one paid, delivered sandbox order and one review on the cheapest product that can be bought.
