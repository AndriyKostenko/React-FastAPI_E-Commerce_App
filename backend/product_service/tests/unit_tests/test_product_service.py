"""
Unit tests for ProductService.

All external dependencies (repository, product_image_service) are mocked
so every test runs without a live database.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from exceptions.product_exceptions import (
    ProductCreationError,
    ProductNotFoundError,
    ProductUpdateError,
)
from shared.contracts.order import OrderItem as OrderItemBase
from schemas.product_schemas import (
    CreateProduct,
    CreateProductVariant,
    OrderQuoteLineRequest,
    UpdateProduct,
)
from service_layer.product_service import ProductService


class TestOrderQuote:
    async def test_catalog_quote_uses_server_price_and_selected_variant(
        self, product_service_unit, mock_product_orm
    ) -> None:
        variant_id = uuid4()
        variant = SimpleNamespace(
            id=variant_id,
            active=True,
            inventory_num=5,
            variant_sug_sell_price=Decimal("27.50"),
            variant_sell_price=Decimal("25.00"),
            vid="supplier-variant",
            variant_name_en="Black / M",
            variant_sku="SKU-M-BLK",
            variant_key="Black-M",
            variant_image="/variant.png",
        )
        mock_product_orm.price = Decimal("999.99")
        mock_product_orm.quantity = 5
        mock_product_orm.variants = [variant]
        product_service_unit.repository.get_by_id = AsyncMock(
            return_value=mock_product_orm
        )

        quote = await product_service_unit.quote_order_items(
            [
                OrderQuoteLineRequest(
                    product_id=mock_product_orm.id,
                    variant_id=variant_id,
                    quantity=2,
                )
            ]
        )

        assert quote.items[0].unit_price == Decimal("27.50")
        assert quote.total_amount == Decimal("55.00")

    async def test_cj_quote_rejects_product_without_active_variant(
        self, product_service_unit, mock_product_orm
    ) -> None:
        mock_product_orm.supplier_id = "cjdropshipping"
        mock_product_orm.variants = []
        product_service_unit.repository.get_by_id = AsyncMock(
            return_value=mock_product_orm
        )

        with pytest.raises(ProductNotFoundError, match="no active variants"):
            await product_service_unit.quote_order_items(
                [
                    OrderQuoteLineRequest(
                        product_id=mock_product_orm.id,
                        quantity=1,
                    )
                ]
            )

    async def test_quote_aggregates_duplicate_line_inventory(
        self, product_service_unit, mock_product_orm
    ) -> None:
        mock_product_orm.quantity = 3
        product_service_unit.repository.get_by_id = AsyncMock(
            return_value=mock_product_orm
        )
        line = OrderQuoteLineRequest(product_id=mock_product_orm.id, quantity=2)

        with pytest.raises(ProductNotFoundError, match="Insufficient inventory"):
            await product_service_unit.quote_order_items([line, line])


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

        from schemas.product_schemas import ProductsFilterParams
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

        from schemas.product_schemas import ProductsFilterParams
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
        product_service_unit.reservation_repository.get_order_for_update.return_value = [
            SimpleNamespace(
                product_id=item.product_id,
                variant_id=None,
                quantity=item.quantity,
                status="reserved",
            )
        ]
        await product_service_unit.release_inventory([item])

        mock_product_repository.atomic_increment_quantity.assert_awaited_once_with(
            item_id=mock_product_orm.id, amount=3
        )

    async def test_release_is_idempotent_across_distinct_events(
        self, product_service_unit, mock_product_repository, mock_product_orm
    ) -> None:
        item = OrderItemBase(
            order_id=uuid4(), product_id=mock_product_orm.id, quantity=3, price=9.99
        )
        reservation = SimpleNamespace(
            product_id=item.product_id,
            variant_id=None,
            quantity=item.quantity,
            status="reserved",
        )
        product_service_unit.reservation_repository.get_order_for_update.return_value = [reservation]
        mock_product_repository.atomic_increment_quantity.return_value = mock_product_orm

        await product_service_unit.release_inventory([item])
        await product_service_unit.release_inventory([item])

        assert mock_product_repository.atomic_increment_quantity.await_count == 1
        assert reservation.status == "released"

    async def test_release_raises_when_product_not_found(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
    ) -> None:
        mock_product_repository.atomic_increment_quantity.return_value = None

        from exceptions.product_exceptions import ProductReleaseError
        item = OrderItemBase(order_id=uuid4(), product_id=uuid4(), quantity=1, price=9.99)
        product_service_unit.reservation_repository.get_order_for_update.return_value = [
            SimpleNamespace(
                product_id=item.product_id,
                variant_id=None,
                quantity=item.quantity,
                status="reserved",
            )
        ]
        with pytest.raises(ProductReleaseError):
            await product_service_unit.release_inventory([item])


class TestSupplierReconciliation:
    async def test_sync_variants_preserves_ids_and_deactivates_missing(self) -> None:
        product_id = uuid4()
        retained = SimpleNamespace(id=uuid4(), vid="v1", active=True)
        removed = SimpleNamespace(id=uuid4(), vid="v2", active=True)
        variant_repository = MagicMock()
        variant_repository.get_by_product_id = AsyncMock(return_value=[retained, removed])
        variant_repository.create = AsyncMock()
        variant_repository.update = AsyncMock()
        image_repository = MagicMock()
        image_repository.get_by_product_id = AsyncMock(return_value=[])

        service = ProductService(
            repository=MagicMock(session=MagicMock()),
            product_image_service=MagicMock(),
            variant_repository=variant_repository,
            image_repository=image_repository,
        )
        await service._sync_variants(
            product_id,
            [CreateProductVariant(vid="v1", variant_sku="updated")],
        )

        assert retained.id is not None
        assert retained.variant_sku == "updated"
        assert retained.active is True
        assert removed.active is False
        variant_repository.create.assert_not_awaited()
        assert variant_repository.update.await_count == 2

    async def test_sync_images_keeps_unchanged_rows(self) -> None:
        product_id = uuid4()
        kept = SimpleNamespace(id=uuid4(), image_url="https://example.com/keep.jpg")
        removed = SimpleNamespace(id=uuid4(), image_url="https://example.com/remove.jpg")
        image_repository = MagicMock()
        image_repository.get_by_product_id = AsyncMock(return_value=[kept, removed])
        image_repository.create_many = AsyncMock()
        image_repository.delete = AsyncMock()

        service = ProductService(
            repository=MagicMock(session=MagicMock()),
            product_image_service=MagicMock(),
            variant_repository=MagicMock(),
            image_repository=image_repository,
        )
        await service._sync_images(
            product_id,
            ["https://example.com/keep.jpg", "https://example.com/new.jpg"],
        )

        created = image_repository.create_many.await_args.args[0]
        assert [image.image_url for image in created] == ["https://example.com/new.jpg"]
        image_repository.delete.assert_awaited_once_with(removed)


# ---------------------------------------------------------------------------
# reserve_inventory rollback
# ---------------------------------------------------------------------------

class TestReserveInventoryRollback:
    async def test_rolls_back_previous_local_reservations_on_local_failure(
        self,
        product_service_unit,
        mock_product_repository: MagicMock,
        mock_product_orm: MagicMock,
    ) -> None:
        order_id = uuid4()
        first_item = OrderItemBase(order_id=order_id, product_id=uuid4(), quantity=1, price=9.99)
        second_item = OrderItemBase(order_id=order_id, product_id=uuid4(), quantity=5, price=9.99)

        # First decrement succeeds, second fails.
        mock_product_repository.atomic_decrement_quantity.side_effect = [mock_product_orm, None]
        mock_product_repository.get_by_id.return_value = None

        result = await product_service_unit.reserve_inventory([first_item, second_item])

        assert result["success"] is False
        assert result["failed_products"] == [second_item]
        assert "not found" in result["reasons"].lower()
        mock_product_repository.atomic_increment_quantity.assert_not_awaited()
