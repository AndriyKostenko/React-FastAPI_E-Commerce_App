"""The return rules that need no database: policies, reasons, photo checks, storage keys."""

from types import SimpleNamespace

import pytest

from service_layer.return_evidence_storage import EvidencePhotoSniffer, LocalReturnEvidenceStorage
from service_layer.return_policy import ReturnPolicies
from shared.contracts.returns import ReturnFault, ReturnReason

SELLER, CUSTOMER = ReturnFault.SELLER, ReturnFault.CUSTOMER


@pytest.mark.parametrize(
    ("fulfillment_type", "fault", "allowed", "ships_back"),
    [
        ("custom", SELLER, True, False),
        ("custom", CUSTOMER, False, False),
        ("cj", SELLER, True, False),
        ("cj", CUSTOMER, True, True),
        ("catalog", SELLER, True, True),
        ("catalog", CUSTOMER, True, True),
    ],
)
def test_policy_table(fulfillment_type: str, fault: ReturnFault, allowed: bool, ships_back: bool) -> None:
    policy = ReturnPolicies().for_type(fulfillment_type)
    assert policy.allows(fault) is allowed
    assert policy.ships_back(fault) is ships_back


@pytest.mark.parametrize("fulfillment_type", ["custom", "cj", "catalog"])
def test_only_the_sellers_fault_refunds_shipping_and_needs_a_photo(fulfillment_type: str) -> None:
    policy = ReturnPolicies().for_type(fulfillment_type)
    assert policy.refunds_shipping(SELLER) and policy.requires_photo(SELLER)
    assert not policy.refunds_shipping(CUSTOMER) and not policy.requires_photo(CUSTOMER)


def test_an_unknown_fulfilment_type_has_no_policy() -> None:
    with pytest.raises(ValueError):
        ReturnPolicies().for_type("drone")


def test_the_reason_decides_the_fault() -> None:
    assert {r for r in ReturnReason if r.fault is SELLER} == {
        ReturnReason.DEFECTIVE, ReturnReason.DAMAGED, ReturnReason.WRONG_ITEM, ReturnReason.MISPRINT,
    }
    assert ReturnReason.CHANGED_MIND.fault is CUSTOMER
    assert ReturnReason.DOES_NOT_FIT.fault is CUSTOMER


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPrest", "image/webp"),
    ],
)
def test_photo_type_is_read_from_its_bytes(content: bytes, content_type: str) -> None:
    photo = EvidencePhotoSniffer.sniff(content)
    assert photo is not None and photo.content_type == content_type


@pytest.mark.parametrize("content", [b"", b"GIF89a...", b"<svg onload=alert(1)>", b"%PDF-1.7"])
def test_anything_else_is_refused(content: bytes) -> None:
    assert EvidencePhotoSniffer.sniff(content) is None


@pytest.mark.parametrize("key", ["../outside.jpg", "/etc/passwd", "a/../../outside.jpg"])
async def test_a_storage_key_cannot_leave_the_evidence_root(tmp_path, key: str) -> None:
    storage = LocalReturnEvidenceStorage(SimpleNamespace(RETURN_EVIDENCE_ROOT=str(tmp_path)))
    with pytest.raises(ValueError):
        await storage.load(key)


async def test_stored_evidence_reads_back(tmp_path) -> None:
    storage = LocalReturnEvidenceStorage(SimpleNamespace(RETURN_EVIDENCE_ROOT=str(tmp_path)))
    photo = EvidencePhotoSniffer.sniff(b"\xff\xd8\xff\xe0data")
    assert photo is not None

    await storage.save("order/return/0.jpg", photo)

    assert await storage.load("order/return/0.jpg") == photo.content
    assert await storage.load("order/return/1.jpg") is None
