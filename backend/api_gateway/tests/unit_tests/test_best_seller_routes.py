"""Unit tests for GET /best-sellers: order-service's ranking joined to the products."""
from uuid import uuid4

from httpx import AsyncClient
from httpx import Response as HttpxResponse

from tests.constants import TEST_API

TEE, HOODIE, GONE = str(uuid4()), str(uuid4()), str(uuid4())
URL = f"{TEST_API}/best-sellers"


class ServiceStub:
    """Answers service-to-service calls by (service, path) and records the paths."""

    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], HttpxResponse] = {
            ("order-service", "/best-sellers?days=30&limit=12"): HttpxResponse(
                200, json=[{"product_id": TEE, "units_sold": 5}, {"product_id": HOODIE, "units_sold": 2}]
            ),
            ("product-service", f"/products/{TEE}/detailed"): HttpxResponse(200, json={"id": TEE, "name": "Tee"}),
            ("product-service", f"/products/{HOODIE}/detailed"): HttpxResponse(200, json={"id": HOODIE, "name": "Hoodie"}),
        }
        self.paths: list[str] = []

    async def request(self, _request, service, path, **_kwargs):
        self.paths.append(path)
        return self.responses[(service, path)]


def _stub(mock_service_request) -> ServiceStub:
    stub = ServiceStub()
    mock_service_request.side_effect = stub.request
    return stub


async def test_products_come_back_in_rank_order_with_their_units(client: AsyncClient, mock_service_request) -> None:
    _stub(mock_service_request)

    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json() == [
        {"units_sold": 5, "product": {"id": TEE, "name": "Tee"}},
        {"units_sold": 2, "product": {"id": HOODIE, "name": "Hoodie"}},
    ]


async def test_days_and_limit_reach_order_service(client: AsyncClient, mock_service_request) -> None:
    stub = _stub(mock_service_request)
    stub.responses[("order-service", "/best-sellers?days=90&limit=4")] = HttpxResponse(200, json=[])

    response = await client.get(URL, params={"days": 90, "limit": 4})

    assert response.status_code == 200 and response.json() == []
    assert stub.paths == ["/best-sellers?days=90&limit=4"]


async def test_a_deleted_product_is_left_out(client: AsyncClient, mock_service_request) -> None:
    stub = _stub(mock_service_request)
    stub.responses[("order-service", "/best-sellers?days=30&limit=12")] = HttpxResponse(
        200, json=[{"product_id": GONE, "units_sold": 9}, {"product_id": TEE, "units_sold": 5}]
    )
    stub.responses[("product-service", f"/products/{GONE}/detailed")] = HttpxResponse(404, json={"detail": "not found"})

    response = await client.get(URL)

    assert response.status_code == 200
    assert [entry["product"]["id"] for entry in response.json()] == [TEE]


async def test_a_failing_product_lookup_fails_the_answer(client: AsyncClient, mock_service_request) -> None:
    """A 2xx is cached for everybody, so a list missing a product must not be one."""
    stub = _stub(mock_service_request)
    stub.responses[("product-service", f"/products/{HOODIE}/detailed")] = HttpxResponse(503, json={"detail": "down"})

    response = await client.get(URL)

    assert response.status_code == 503


async def test_a_failing_ranking_is_passed_on(client: AsyncClient, mock_service_request) -> None:
    stub = _stub(mock_service_request)
    stub.responses[("order-service", "/best-sellers?days=30&limit=12")] = HttpxResponse(500, json={"detail": "boom"})

    response = await client.get(URL)

    assert response.status_code == 500
    assert stub.paths == ["/best-sellers?days=30&limit=12"]


async def test_out_of_range_parameters_never_reach_a_service(client: AsyncClient, mock_service_request) -> None:
    stub = _stub(mock_service_request)

    for params in ({"days": 0}, {"days": 366}, {"limit": 0}, {"limit": 51}):
        response = await client.get(URL, params=params)
        assert response.status_code == 422

    assert stub.paths == []
