"""
EmailAddressPolicy's rules, against real DNS and the real disposable-domain list.

Needs network access for the DNS lookups. The domains are chosen for answers
that do not change: gmail.com receives mail, example.com publishes a "null MX"
(RFC 7505, it accepts no mail), and the made-up domain is not registered.
"""
import pytest
from fastapi.exceptions import RequestValidationError

from service_layer.email_policy import (
    DisposableDomainRule,
    EmailAddressPolicy,
    MailDomainRule,
)


@pytest.fixture
def mail_domain_rule() -> MailDomainRule:
    return MailDomainRule(timeout_seconds=5)


async def test_a_domain_that_receives_mail_passes(mail_domain_rule: MailDomainRule) -> None:
    assert await mail_domain_rule.refusal("someone@gmail.com") is None


@pytest.mark.parametrize("email", ["someone@example.com", "someone@no-such-domain-4b1d9e.com"])
async def test_a_domain_that_cannot_receive_mail_is_refused(mail_domain_rule: MailDomainRule, email: str) -> None:
    assert await mail_domain_rule.refusal(email) == MailDomainRule.MESSAGE


@pytest.mark.parametrize("email", ["a@mailinator.com", "a@inbox.mailinator.com", "a@MAILINATOR.com"])
async def test_disposable_domains_and_their_subdomains_are_refused(email: str) -> None:
    assert await DisposableDomainRule().refusal(email) == DisposableDomainRule.MESSAGE


async def test_an_ordinary_domain_is_not_disposable() -> None:
    assert await DisposableDomainRule().refusal("someone@gmail.com") is None


async def test_the_policy_reports_the_first_refusal_against_the_email_field(mail_domain_rule: MailDomainRule) -> None:
    policy = EmailAddressPolicy([DisposableDomainRule(), mail_domain_rule])
    await policy.check("someone@gmail.com")
    with pytest.raises(RequestValidationError) as refused:
        await policy.check("someone@mailinator.com")
    assert refused.value.errors() == [
        {"loc": ("body", "email"), "msg": DisposableDomainRule.MESSAGE, "type": "value_error"}
    ]
