"""Which email addresses may open an account.

Syntax is already checked by the request schema (EmailStr). This adds what can
be known without sending anything: the domain must be able to receive mail, and
must not be a throwaway-inbox service. Whether the mailbox itself exists is
proven by the verification email, the only reliable test: asking a mail server
(SMTP "RCPT TO") is refused or answered "yes" for everyone by the big
providers, and outbound port 25 is blocked on our hosting anyway.
"""

from asyncio import to_thread
from collections.abc import Iterable, Sequence
from typing import Protocol, Self

from disposable_email_domains import blocklist as disposable_domains
from dns.resolver import Resolver
from email_validator import EmailNotValidError, caching_resolver, validate_email
from fastapi.exceptions import RequestValidationError

from settings import Settings


class EmailRule(Protocol):
    """One reason an address may be refused: the message to show, or None to allow it."""

    async def refusal(self, email: str) -> str | None: ...


class DisposableDomainRule:
    """Refuses throwaway-inbox services (mailinator.com and ~9,000 others), subdomains included."""

    MESSAGE = "Disposable email addresses can't be used. Please use a permanent address."

    def __init__(self, domains: Iterable[str] = disposable_domains) -> None:
        self._domains = frozenset(domain.lower() for domain in domains)

    async def refusal(self, email: str) -> str | None:
        labels = email.rsplit("@", 1)[-1].lower().split(".")
        # a.b.mailinator.com is checked as itself, b.mailinator.com and mailinator.com.
        for start in range(len(labels) - 1):
            if ".".join(labels[start:]) in self._domains:
                return self.MESSAGE
        return None


class MailDomainRule:
    """Refuses a domain that cannot receive mail: it does not exist, or has no MX/A/AAAA record,
    or publishes a "null MX" saying it accepts no mail (example.com does).

    A DNS server that does not answer in time lets the address through: a slow
    resolver must not turn real customers away, and the verification email
    still has to arrive before the account can be used.
    """

    MESSAGE = "This email address's domain can't receive mail. Please check it for typos."

    def __init__(self, timeout_seconds: float) -> None:
        # Shared by every request, so a popular domain is looked up once per TTL.
        self._resolver: Resolver = caching_resolver(timeout=timeout_seconds)

    async def refusal(self, email: str) -> str | None:
        try:
            # email-validator's DNS lookups are blocking; keep them off the event loop.
            await to_thread(validate_email, email, check_deliverability=True, dns_resolver=self._resolver)
        except EmailNotValidError:
            return self.MESSAGE
        return None


class EmailAddressPolicy:
    """Runs each rule in turn; the first refusal is reported against the form's email field."""

    def __init__(self, rules: Sequence[EmailRule]) -> None:
        self._rules = tuple(rules)

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        rules: list[EmailRule] = [DisposableDomainRule()]
        if settings.EMAIL_DELIVERABILITY_CHECK:
            rules.append(MailDomainRule(settings.EMAIL_DNS_TIMEOUT_SECONDS))
        return cls(rules)

    async def check(self, email: str) -> None:
        for rule in self._rules:
            if (message := await rule.refusal(email)) is not None:
                # The validation error shape every form already understands: the
                # message lands under the email input instead of in a toast.
                raise RequestValidationError(
                    [{"loc": ("body", "email"), "msg": message, "type": "value_error"}]
                )
