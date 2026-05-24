"""
Unit tests for ProductService.

All external dependencies (repository, product_image_service) are mocked
so every test runs without a live database.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from exceptions.product_exceptions import (
    ProductCreationError,
    ProductNotFoundError,
    ProductUpdateError,
)
from shared.schemas.order_schemas import OrderItemBase
from shared.schemas.product_schemas import CreateProduct, UpdateProduct


# ---------------------------------------------------------------------------
# create_product_item
# ---------------------------------------------------------------------------

class TestCreateProductItem:
    async def test_creates_product_and_returns_product_base(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_repository.get_by_field.return_value = None
        mock_product_repository.create.return_value = mock_product_orm

        data = CreateProduct(
            name="Test Laptop",
            description="A high-quality test laptop for testing",
            category_id=uuid4(),
            brand="TestBrand",
            quantity=5,
            price=Decimal("499.99"),
            in_stock=True,
        )
        result = await product_service_unit.create_product_item(data)

        assert result.name == data.name.lower()
        mock_product_repository.get_by_field.assert_awaited_once_with("name", value=data.name.lower())
        mock_product_repository.create.assert_awaited_once()

    async def test_raises_when_product_already_exists(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_repository.get_by_field.return_value = mock_product_orm

        data = CreateProduct(
            name="Existing Product",
            description="This product already exists in the database",
            category_id=uuid4(),
            brand="SomeBrand",
            quantity=1,
            price=Decimal("100.00"),
            in_stock=True,
        )
        with pytest.raises(ProductCreationError):
            await product_service_unit.create_product_item(data)

    async def test_raises_when_category_fk_violated(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.get_by_field.return_value = None
        fk_error = IntegrityError(
            statement=None,
            params=None,
            orig=Exception("products_category_id_fkey"),
        )
        mock_product_repository.create.side_effect = fk_error

        data = CreateProduct(
            name="Bad Product",
            description="Product with a non-existent category id",
            category_id=uuid4(),
            brand="BadBrand",
            quantity=1,
            price=Decimal("50.00"),
            in_stock=False,
        )
        with pytest.raises(ProductCreationError, match="does not exist"):
            await product_service_unit.create_product_item(data)

    async def test_name_and_brand_stored_lowercase(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_repository.get_by_field.return_value = None
        mock_product_repository.create.return_value = mock_product_orm

        data = CreateProduct(
            name="UPPERCASE NAME",
            description="Testing lowercase normalization on save",
            category_id=uuid4(),
            brand="BIG BRAND",
            quantity=2,
            price=Decimal("200.00"),
            in_stock=True,
        )
        await product_service_unit.create_product_item(data)

        created_product = mock_product_repository.create.call_args[0][0]
        assert created_product.name == "uppercase name"
        assert created_product.brand == "big brand"


# ---------------------------------------------------------------------------
# get_product_by_id_without_relations
# ---------------------------------------------------------------------------

class TestGetProductById:
    async def test_returns_product_base(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_repository.get_by_id.return_value = mock_product_orm
        product_id = mock_product_orm.id

        result = await product_service_unit.get_product_by_id_without_relations(product_id)

        assert result.id == product_id
        mock_product_repository.get_by_id.assert_awaited_once_with(item_id=product_id)

    async def test_raises_when_not_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.get_by_id.return_value = None

        with pytest.raises(ProductNotFoundError):
            await product_service_unit.get_product_by_id_without_relations(uuid4())


# ---------------------------------------------------------------------------
# get_all_products_without_relations
# ---------------------------------------------------------------------------

class TestGetAllProducts:
    async def test_returns_product_list(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_repository.get_all.return_value = [mock_product_orm]

        from shared.schemas.product_schemas import ProductsFilterParams
        filters = ProductsFilterParams()
        result = await product_service_unit.get_all_products_without_relations(filters)

        assert len(result) == 1
        assert result[0].id == mock_product_orm.id

    async def test_raises_when_no_products_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.get_all.return_value = []

        from shared.schemas.product_schemas import ProductsFilterParams
        with pytest.raises(ProductNotFoundError):
            await product_service_unit.get_all_products_without_relations(ProductsFilterParams())


# ---------------------------------------------------------------------------
# update_product
# ---------------------------------------------------------------------------

class TestUpdateProduct:
    async def test_updates_and_returns_product(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_repository.update_by_id.return_value = mock_product_orm
        product_id = mock_product_orm.id

        update_data = UpdateProduct(quantity=20)
        result = await product_service_unit.update_product(product_id, update_data)

        assert result.id == product_id
        mock_product_repository.update_by_id.assert_awaited_once_with(
            product_id, data={"quantity": 20}
        )

    async def test_raises_when_no_update_fields_provided(
        self,
        product_service_unit,
    ) -> None:
        with pytest.raises(ProductUpdateError):
            await product_service_unit.update_product(uuid4(), UpdateProduct())

    async def test_raises_when_product_not_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.update_by_id.return_value = None

        with pytest.raises(ProductNotFoundError):
            await product_service_unit.update_product(uuid4(), UpdateProduct(quantity=5))


# ---------------------------------------------------------------------------
# delete_product_by_id
# ---------------------------------------------------------------------------

class TestDeleteProduct:
    async def test_deletes_product_successfully(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.delete_by_id.return_value = True
        product_id = uuid4()

        await product_service_unit.delete_product_by_id(product_id)

        mock_product_repository.delete_by_id.assert_awaited_once_with(product_id)

    async def test_raises_when_product_not_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.delete_by_id.return_value = False

        with pytest.raises(ProductNotFoundError):
            await product_service_unit.delete_product_by_id(uuid4())


# ---------------------------------------------------------------------------
# reserve_inventory
# ---------------------------------------------------------------------------

class TestReserveInventory:
    async def test_reserve_succeeds_and_decrements_quantity(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_orm.quantity = 10
        mock_product_orm.in_stock = True
        mock_product_repository.atomic_decrement_quantity.return_value = mock_product_orm

        item = OrderItemBase(order_id=uuid4(), product_id=mock_product_orm.id, quantity=3, price=9.99)
        result = await product_service_unit.reserve_inventory([item])

        assert result["success"] is True
        assert len(result["products"]) == 1
        mock_product_repository.atomic_decrement_quantity.assert_awaited_once_with(
            item_id=mock_product_orm.id, requested=3
        )

    async def test_reserve_fails_when_product_not_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        # atomic_decrement returns None → service reads row for a better error message
        mock_product_repository.atomic_decrement_quantity.return_value = None
        mock_product_repository.get_by_id.return_value = None

        item = OrderItemBase(order_id=uuid4(), product_id=uuid4(), quantity=1, price=9.99)
        result = await product_service_unit.reserve_inventory([item])

        assert result["success"] is False
        assert "not found" in result["reasons"].lower()

    async def test_reserve_fails_when_out_of_stock(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_orm.quantity = 5
        mock_product_orm.in_stock = False
        # atomic_decrement returns None because in_stock = FALSE
        mock_product_repository.atomic_decrement_quantity.return_value = None
        mock_product_repository.get_by_id.return_value = mock_product_orm

        item = OrderItemBase(order_id=uuid4(), product_id=mock_product_orm.id, quantity=1, price=9.99)
        result = await product_service_unit.reserve_inventory([item])

        assert result["success"] is False
        assert "out of stock" in result["reasons"].lower()

    async def test_reserve_fails_when_insufficient_quantity(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_orm.quantity = 2
        mock_product_orm.in_stock = True
        # atomic_decrement returns None because quantity < requested
        mock_product_repository.atomic_decrement_quantity.return_value = None
        mock_product_repository.get_by_id.return_value = mock_product_orm

        item = OrderItemBase(order_id=uuid4(), product_id=mock_product_orm.id, quantity=10, price=9.99)
        result = await product_service_unit.reserve_inventory([item])

        assert result["success"] is False
        assert "insufficient" in result["reasons"].lower()


# ---------------------------------------------------------------------------
# release_inventory
# ---------------------------------------------------------------------------

class TestReleaseInventory:
    async def test_release_increments_quantity_back(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        mock_product_orm.quantity = 10
        mock_product_orm.in_stock = True
        mock_product_repository.atomic_increment_quantity.return_value = mock_product_orm

        item = OrderItemBase(order_id=uuid4(), product_id=mock_product_orm.id, quantity=3, price=9.99)
        await product_service_unit.release_inventory([item])

        mock_product_repository.atomic_increment_quantity.assert_awaited_once_with(
            item_id=mock_product_orm.id, amount=3
        )

    async def test_release_raises_when_product_not_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.atomic_increment_quantity.return_value = None

        from exceptions.product_exceptions import ProductReleaseError
        item = OrderItemBase(order_id=uuid4(), product_id=uuid4(), quantity=1, price=9.99)
        with pytest.raises(ProductReleaseError):
            await product_service_unit.release_inventory([item])
