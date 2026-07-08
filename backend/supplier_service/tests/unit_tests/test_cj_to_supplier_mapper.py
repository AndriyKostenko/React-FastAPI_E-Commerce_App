"""Unit tests for CJ Dropshipping to generic supplier schema mapping."""
from decimal import Decimal

import pytest

from service_layer.cj_to_supplier_mapper import CJToSupplierMapper


@pytest.fixture
def mapper() -> CJToSupplierMapper:
    return CJToSupplierMapper()


class TestCJToSupplierMapperList:
    def test_maps_list_response(self, mapper: CJToSupplierMapper) -> None:
        data = {
            "data": {
                "content": [
                    {
                        "page": {
                            "pageNumber": 1,
                            "pageSize": 10,
                            "totalRecords": 1,
                            "totalPages": 1,
                        },
                        "productList": [
                            {
                                "id": "1372719597450563584",
                                "nameEn": "Alien Football Tie Dye T-Shirt",
                                "sku": "CJNS1047537",
                                "bigImage": "https://cf.cjdropshipping.com/1616116491646.jpg",
                                "sellPrice": "10.32",
                                "categoryId": "BE11EEDB-B765-4A39-8A3D-F6015FC7A846",
                                "warehouseInventoryNum": 160000,
                            }
                        ],
                    }
                ]
            }
        }
        page = mapper.map_products_page(data, page=1, page_size=10)
        assert page.total_records == 1
        assert len(page.products) == 1
        product = page.products[0]
        assert product.supplier_id == "cjdropshipping"
        assert product.supplier_pid == "1372719597450563584"
        assert product.name == "alien football tie dye t-shirt"
        assert product.price == Decimal("10.32")
        assert product.quantity == 160000
        assert product.in_stock is True

    def test_parses_price_range(self, mapper: CJToSupplierMapper) -> None:
        data = {
            "data": {
                "content": [
                    {
                        "productList": [
                            {
                                "id": "p1",
                                "nameEn": "Range Product",
                                "sellPrice": "7.13 -- 7.77",
                                "warehouseInventoryNum": 10,
                            }
                        ]
                    }
                ]
            }
        }
        page = mapper.map_products_page(data)
        assert page.products[0].price == Decimal("7.13")


class TestCJToSupplierMapperDetails:
    def test_maps_detail_response(self, mapper: CJToSupplierMapper) -> None:
        data = {
            "data": {
                "pid": "1372719597450563584",
                "productNameEn": "Alien Football Tie Dye T-Shirt",
                "productSku": "CJNS1047537",
                "bigImage": "https://cf.cjdropshipping.com/1616116491646.jpg",
                "sellPrice": "10.32",
                "description": "<p>Product info</p>",
                "categoryId": "BE11EEDB-B765-4A39-8A3D-F6015FC7A846",
                "productImageSet": '["https://cf.cjdropshipping.com/1616116491646.jpg"]',
                "variants": [
                    {
                        "vid": "v1",
                        "variantKey": "S",
                        "variantNameEn": "T-Shirt S",
                        "variantSku": "CJNS104753701AZ",
                        "variantSellPrice": 10.32,
                    }
                ],
            }
        }
        product = mapper.map_product_details(data)
        assert product.supplier_pid == "1372719597450563584"
        assert product.name == "alien football tie dye t-shirt"
        assert product.description == "<p>Product info</p>"
        assert len(product.images) == 1
        assert len(product.variants) == 1
        assert product.variants[0].vid == "v1"
        assert product.variants[0].variant_sell_price == Decimal("10.32")
