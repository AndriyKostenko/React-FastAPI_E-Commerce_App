"""The shared Stripe client must be given the key itself, not its masked wrapper."""

from types import SimpleNamespace

from pydantic import SecretStr

from resources import create_stripe_client


def test_the_client_authenticates_with_the_revealed_key() -> None:
    settings = SimpleNamespace(
        STRIPE_SECRET_KEY=SecretStr("sk_test_dummy_not_real"),
        STRIPE_API_KEY="sk_test_dummy_not_real",
        STRIPE_REQUEST_TIMEOUT_SECONDS=5.0,
        STRIPE_MAX_NETWORK_RETRIES=0,
    )

    client, _ = create_stripe_client(settings)  # type: ignore[arg-type]

    key = client._requestor._options.api_key
    # A SecretStr here was sent to Stripe as "**********": every call failed.
    assert isinstance(key, str) and key == "sk_test_dummy_not_real"
