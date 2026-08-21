from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Query, UploadFile
from shared.utils.filter_parser import FilterParser
from sqlalchemy.exc import IntegrityError

from database_layer.category_repository import CategoryRepository
from database_layer.product_image_repository import ProductImageRepository
from database_layer.product_repository import ProductRepository
from database_layer.product_variant_repository import ProductVariantRepository
from database_layer.inventory_reservation_repository import InventoryReservationRepository
from exceptions.product_exceptions import (
    ProductCreationError,
    ProductNotFoundError,
    ProductReleaseError,
    ProductUpdateError,
    ProductAlreadyExistsError
)
from models.category_models import ProductCategory
from models.product_image_models import ProductImage
from models.product_models import Product
from models.product_variant_models import ProductVariant
from models.inventory_reservation_models import InventoryReservation
from service_layer.category_service import CategoryService
from service_layer.product_image_service import ProductImageService
from shared.contracts.order import OrderItem as OrderItemBase
from schemas.product_schemas import (
    CreateProduct,
    CreateProductVariant,
    ProductBase,
    ProductSchema,
    ProductsFilterParams,
    UpdateProduct,
    ProductUploadForm,
    OrderQuoteLine,
    OrderQuoteLineRequest,
    OrderQuoteResponse,
)
from utils.image_processing import image_processing_manager


class ProductService:
    """Service layer for product management operations, business logic and data validation."""
    def __init__(self,
                 repository: ProductRepository,
                 product_image_service: ProductImageService,
                 variant_repository: ProductVariantRepository | None = None,
                 image_repository: ProductImageRepository | None = None,
                 category_service: CategoryService | None = None,
                 reservation_repository: InventoryReservationRepository | None = None):
        self.repository: ProductRepository = repository
        self.product_image_service: ProductImageService = product_image_service
        self.variant_repository: ProductVariantRepository = variant_repository or ProductVariantRepository(repository.session)
        self.image_repository: ProductImageRepository = image_repository or ProductImageRepository(repository.session)
        self.category_service: CategoryService | None = category_service
        self.reservation_repository = reservation_repository or InventoryReservationRepository(
            repository.session
        )
        self.product_relations: list[str] = Product.get_relations()
        self.product_search_fileds: list[str] = Product.get_search_fields()
        self.filter_parser: FilterParser = FilterParser()

    async def _resolve_category_id(self, category_id: UUID) -> UUID:
        """Accept only product-service category UUIDs at the persistence boundary."""
        return category_id

    async def _create_variants(self, product_id: UUID, variants: list[CreateProductVariant] | None) -> None:
        """Persist variants for a product."""
        if not variants:
            return
        variant_models = [
            ProductVariant(product_id=product_id, **variant.model_dump())
            for variant in variants
        ]
        await self.variant_repository.create_many(variant_models)

    async def _create_images(self, product_id: UUID, image_urls: list[str] | None) -> None:
        """Persist image URLs for a product."""
        if not image_urls:
            return
        image_models = [ProductImage(product_id=product_id, image_url=url) for url in image_urls]
        await self.image_repository.create_many(image_models)

    async def _sync_variants(self, product_id: UUID, variants: list[CreateProductVariant] | None) -> None:
        """Upsert supplier variants by VID while preserving local UUIDs."""
        existing = {variant.vid: variant for variant in await self.variant_repository.get_by_product_id(product_id)}
        incoming = {variant.vid: variant for variant in (variants or []) if variant.vid}

        for vid, variant_data in incoming.items():
            variant = existing.get(vid)
            if variant is None:
                await self.variant_repository.create(
                    ProductVariant(product_id=product_id, active=True, **variant_data.model_dump())
                )
                continue
            for field, value in variant_data.model_dump().items():
                setattr(variant, field, value)
            variant.active = True
            await self.variant_repository.update(variant)

        for vid, variant in existing.items():
            if vid not in incoming and variant.active:
                variant.active = False
                await self.variant_repository.update(variant)

    async def _sync_images(self, product_id: UUID, image_urls: list[str] | None) -> None:
        """Reconcile image URLs without recreating unchanged image records."""
        normalized_urls = list(dict.fromkeys(url for url in (image_urls or []) if url))
        existing = await self.image_repository.get_by_product_id(product_id)
        existing_by_url = {image.image_url: image for image in existing}
        incoming = set(normalized_urls)

        missing = [
            ProductImage(product_id=product_id, image_url=url)
            for url in normalized_urls
            if url not in existing_by_url
        ]
        if missing:
            await self.image_repository.create_many(missing)
        for url, image in existing_by_url.items():
            if url not in incoming:
                await self.image_repository.delete(image)

    async def create_product_item(self, product_data: CreateProduct) -> ProductBase:
        existing_id = await self.repository.get_by_id(item_id=product_data.id)
        if existing_id:
            raise ProductCreationError(f'Product with id: "{product_data.id}" already exists.')

        existing_name = await self.repository.get_by_field("name", value=product_data.name.lower())
        if existing_name:
            raise ProductCreationError(f'Product with name: "{product_data.name}" already exists.')

        category_id = await self._resolve_category_id(product_data.category_id)

        new_product = Product(
            id=product_data.id or uuid4(),
            pid=product_data.pid,
            sku=product_data.sku,
            image_url=product_data.image_url,
            **product_data.model_dump(exclude={"id", "pid", "sku", "image_url", "category_id", "variants", "images"})
        )
        new_product.category_id = category_id

        try:
            new_db_product = await self.repository.create(new_product)
            await self._create_variants(new_db_product.id, product_data.variants)
            await self._create_images(new_db_product.id, product_data.images)
            return ProductBase.model_validate(new_db_product)
        except IntegrityError as e:
            # Check if it's a foreign key violation for category_id (the category_id does not exist)
            if "products_category_id_fkey" in str(e):
                raise ProductCreationError(f'Category with id "{category_id}" does not exist.')
            # Re-raise other integrity errors
            raise ProductCreationError(f"Failed to create product: {str(e)}")

    async def upsert_product_by_pid(self, product_data: CreateProduct) -> ProductBase:
        """Create or update a product keyed by supplier plus external PID."""
        if not product_data.pid or not product_data.supplier_id:
            raise ProductCreationError("Cannot upsert supplier product without supplier_id and pid.")

        category_id = await self._resolve_category_id(product_data.category_id)
        existing = await self.repository.get_by_supplier_pid(
            product_data.supplier_id,
            product_data.pid,
        )

        if existing:
            # Update scalar fields
            existing.name = product_data.name
            existing.supplier_category_id = product_data.supplier_category_id
            existing.description = product_data.description
            existing.category_id = category_id
            existing.brand = product_data.brand
            existing.quantity = product_data.quantity
            existing.price = product_data.price
            existing.in_stock = product_data.in_stock
            existing.sku = product_data.sku
            existing.image_url = product_data.image_url

            await self._sync_variants(existing.id, product_data.variants)
            await self._sync_images(existing.id, product_data.images)

            await self.repository.update(existing)
            return ProductBase.model_validate(existing)

        # Create new product
        new_product = Product(
            id=uuid4(),
            pid=product_data.pid,
            supplier_id=product_data.supplier_id,
            supplier_category_id=product_data.supplier_category_id,
            sku=product_data.sku,
            image_url=product_data.image_url,
            **product_data.model_dump(exclude={"id", "pid", "supplier_id", "supplier_category_id", "sku", "image_url", "category_id", "variants", "images"})
        )
        new_product.category_id = category_id

        try:
            new_db_product = await self.repository.create(new_product)
            await self._sync_variants(new_db_product.id, product_data.variants)
            await self._sync_images(new_db_product.id, product_data.images)
            return ProductBase.model_validate(new_db_product)
        except IntegrityError as e:
            if "products_category_id_fkey" in str(e):
                raise ProductCreationError(f'Category with id "{category_id}" does not exist.')
            raise ProductCreationError(f"Failed to create product: {str(e)}")

    async def bulk_upsert_products(self, products: list[CreateProduct]) -> dict[str, int]:
        """Upsert multiple products by pid, returning counts."""
        results: dict[str, int] = {"inserted": 0, "updated": 0, "failed": 0}
        for product_data in products:
            try:
                existing = (
                    await self.repository.get_by_supplier_pid(product_data.supplier_id, product_data.pid)
                    if product_data.pid and product_data.supplier_id
                    else None
                )
                async with self.repository.session.begin_nested():
                    await self.upsert_product_by_pid(product_data)
                if existing:
                    results["updated"] += 1
                else:
                    results["inserted"] += 1
            except ProductCreationError:
                results["failed"] += 1
        return results

    async def create_product_with_images(self, product_data: ProductUploadForm) -> ProductSchema:
        image_urls = await image_processing_manager.save_images(product_data.images)
        image_metadata = image_processing_manager.create_metadata_list(image_urls=image_urls,
														           image_colors=product_data.image_colors,
														           image_color_codes=product_data.image_color_codes)
        product_dto = CreateProduct(**product_data.model_dump(exclude={"images", "image_colors", "image_color_codes"}))
        new_product = await self.create_product_item(product_data=product_dto)
        await self.product_image_service.create_product_images(product_id=new_product.id,images=image_metadata)
        full_product = await self.repository.get_by_id(item_id=new_product.id,load_relations=Product.get_relations(),)
        return ProductSchema.model_validate(full_product)

    async def get_product_by_id_without_relations(self, product_id: UUID) -> ProductBase:
        db_product = await self.repository.get_by_id(item_id=product_id)
        if not db_product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")
        return ProductBase.model_validate(db_product)

    async def get_product_by_id_with_relations(self, product_id: UUID) -> ProductSchema:
        product = await self.repository.get_by_id(
            item_id=product_id,
            load_relations=self.product_relations
        )
        if not product:
            raise ProductNotFoundError(f"Product with id: {product_id} not found.")
        return ProductSchema.model_validate(product)

    async def get_all_products_without_relations(self,
                                                filters_query: Annotated[ProductsFilterParams, Query()]) -> list[ProductBase]:
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)
        products: list[Product] = await self.repository.get_all(**params)
        if not products:
            raise ProductNotFoundError("No products found with the given criteria.")
        return [ProductBase.model_validate(product) for product in products]

    async def get_all_products_with_relations(self,
                                              filters_query: Annotated[ProductsFilterParams, Query()]) -> list[ProductSchema]:
        # Parse filters using helper method and add relations
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)
        params["load_relations"] = self.product_relations
        products = await self.repository.get_all(**params)
        if not products:
            raise ProductNotFoundError("No products found with the given criteria.")
        return [ProductSchema.model_validate(product) for product in products]

    async def get_product_by_name(self, name: str) -> ProductBase:
        db_product = await self.repository.get_by_field("name", name.lower())
        if not db_product:
            raise ProductNotFoundError(f"Product with name: {name} not found")
        return ProductBase.model_validate(db_product)

    async def get_products_by_ids(self, products_ids: list[UUID]) -> list[ProductBase]:
        products = await self.repository.get_many_by_field(field_name='id', value=products_ids, limit=50)
        if not products:
            raise ProductNotFoundError("No products found with the given IDs.")
        return [ProductBase.model_validate(product) for product in products]

    async def update_product(self,
                            product_id: UUID,
                            product_data: UpdateProduct) -> ProductBase:
        update_dict = product_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise ProductUpdateError("Failed to update product: no data to update is provided")
        try:
            updated_product = await self.repository.update_by_id(product_id, data=update_dict)
            if not updated_product:
                raise ProductNotFoundError(f"Product with id: {product_id} not found")
            return ProductBase.model_validate(updated_product)
        except IntegrityError as e:
            if "products_category_id_fkey" in str(e):
                raise ProductCreationError(
                    f'Category with id "{update_dict.get("category_id")}" does not exist.'
                )
            raise

    async def delete_product_by_id(self, product_id: UUID) -> None:
        success = await self.repository.delete_by_id(product_id)
        if not success:
            raise ProductNotFoundError(f"Product with id: {product_id} not found")

    async def quote_order_items(
        self,
        items: list[OrderQuoteLineRequest],
    ) -> OrderQuoteResponse:
        """Return a canonical, inventory-aware quote for catalog order lines.

        CJ products with variants require an explicit active variant. Prices and
        availability are read from product_service; client-supplied values are
        never part of the quote.
        """
        quoted: list[OrderQuoteLine] = []
        total = Decimal("0.00")
        requested_products: dict[UUID, int] = {}
        requested_variants: dict[UUID, int] = {}
        for requested_item in items:
            requested_products[requested_item.product_id] = (
                requested_products.get(requested_item.product_id, 0)
                + requested_item.quantity
            )
            if requested_item.variant_id:
                requested_variants[requested_item.variant_id] = (
                    requested_variants.get(requested_item.variant_id, 0)
                    + requested_item.quantity
                )

        for item in items:
            product = await self.repository.get_by_id(
                item.product_id,
                load_relations=["variants"],
            )
            if product is None:
                raise ProductNotFoundError(f"Product with id {item.product_id} not found")
            if (
                not product.in_stock
                or product.quantity < requested_products[item.product_id]
            ):
                raise ProductNotFoundError(
                    f"Insufficient inventory for product {item.product_id}"
                )

            fulfillment_type = "cj" if product.supplier_id == "cjdropshipping" else "catalog"
            variant = None
            variant_snapshot = None
            unit_price = Decimal(product.price)

            active_variants = [candidate for candidate in (product.variants or []) if candidate.active]
            if fulfillment_type == "cj":
                if not active_variants:
                    raise ProductNotFoundError(
                        f"CJ product {item.product_id} has no active variants"
                    )
                if item.variant_id is None:
                    raise ProductNotFoundError(
                        f"A variant is required for CJ product {item.product_id}"
                    )
                variant = next(
                    (candidate for candidate in active_variants if candidate.id == item.variant_id),
                    None,
                )
                if variant is None:
                    raise ProductNotFoundError(
                        f"Variant {item.variant_id} is not active for product {item.product_id}"
                    )
                if (
                    variant.inventory_num is not None
                    and variant.inventory_num < requested_variants[variant.id]
                ):
                    raise ProductNotFoundError(
                        f"Insufficient inventory for variant {item.variant_id}"
                    )
                candidate_price = variant.variant_sug_sell_price or variant.variant_sell_price
                if candidate_price is not None and candidate_price > 0:
                    unit_price = Decimal(candidate_price)
                variant_snapshot = {
                    "vid": variant.vid,
                    "name": variant.variant_name_en,
                    "sku": variant.variant_sku,
                    "key": variant.variant_key,
                    "image": variant.variant_image,
                }
            elif item.variant_id is not None:
                variant = next(
                    (candidate for candidate in active_variants if candidate.id == item.variant_id),
                    None,
                )
                if variant is None:
                    raise ProductNotFoundError(
                        f"Variant {item.variant_id} is not active for product {item.product_id}"
                    )
                if (
                    variant.inventory_num is not None
                    and variant.inventory_num < requested_variants[variant.id]
                ):
                    raise ProductNotFoundError(
                        f"Insufficient inventory for variant {item.variant_id}"
                    )
                candidate_price = variant.variant_sug_sell_price or variant.variant_sell_price
                if candidate_price is not None and candidate_price > 0:
                    unit_price = Decimal(candidate_price)

            unit_price = unit_price.quantize(Decimal("0.01"))
            total += unit_price * item.quantity
            quoted.append(
                OrderQuoteLine(
                    product_id=product.id,
                    variant_id=variant.id if variant else None,
                    product_name=product.name,
                    quantity=item.quantity,
                    unit_price=unit_price,
                    fulfillment_type=fulfillment_type,
                    supplier_id=product.supplier_id,
                    variant_snapshot=variant_snapshot,
                )
            )

        return OrderQuoteResponse(
            currency="CAD",
            items=quoted,
            total_amount=total.quantize(Decimal("0.01")),
        )

    async def reserve_inventory(self, items: list[OrderItemBase]) -> dict[str, Any]:
        """
        Reserve inventory via atomic per-row decrements.

        The local DB decrement is the fast, race-safe gate. If any item cannot be
        reserved locally, all previously reserved items in this request are rolled
        back so the reservation is all-or-nothing.
        """
        if not items:
            return {"success": True, "products": []}

        order_id = items[0].order_id
        if any(item.order_id != order_id for item in items):
            return {
                "success": False,
                "reasons": "All inventory lines must belong to one order",
                "failed_products": items,
            }
        grouped: dict[tuple[UUID, UUID | None], OrderItemBase] = {}
        for item in items:
            key = (item.product_id, item.variant_id)
            if key in grouped:
                grouped[key] = grouped[key].model_copy(
                    update={"quantity": grouped[key].quantity + item.quantity}
                )
            else:
                grouped[key] = item
        reservation_items = list(grouped.values())
        existing = await self.reservation_repository.get_order_for_update(order_id)
        if existing:
            if all(row.status == "reserved" for row in existing):
                return {"success": True, "products": items}
            return {
                "success": False,
                "reasons": "Inventory reservation was already released",
                "failed_products": items,
            }

        class ReservationRejected(Exception):
            def __init__(self, item: OrderItemBase, reason: str):
                self.item = item
                self.reason = reason

        try:
            async with self.repository.session.begin_nested():
                for item in reservation_items:
                    if item.fulfillment_type == "cj" and item.variant_id is None:
                        raise ReservationRejected(
                            item, f"CJ product {item.product_id} requires a variant"
                        )
                    if item.variant_id is not None:
                        variant = await self.variant_repository.atomic_decrement_inventory(
                            item.variant_id, item.quantity
                        )
                        if variant is None:
                            raise ReservationRejected(
                                item,
                                f"Insufficient inventory for variant {item.variant_id}",
                            )

                    updated = await self.repository.atomic_decrement_quantity(
                        item_id=item.product_id,
                        requested=item.quantity,
                    )
                    if updated is None:
                        current = await self.repository.get_by_id(item.product_id)
                        if current is None:
                            reason = f"Product {item.product_id} not found"
                        elif not current.in_stock:
                            reason = f"Product {item.product_id} is out of stock"
                        else:
                            reason = f"Product {item.product_id} has insufficient inventory"
                        raise ReservationRejected(
                            item,
                            reason,
                        )

                    await self.reservation_repository.create(
                        InventoryReservation(
                            order_id=order_id,
                            product_id=item.product_id,
                            variant_id=item.variant_id,
                            line_key=f"{item.product_id}:{item.variant_id or '-'}",
                            quantity=item.quantity,
                            status="reserved",
                        )
                    )
        except ReservationRejected as exc:
            return {
                "success": False,
                "reasons": exc.reason,
                "failed_products": [exc.item],
            }

        return {"success": True, "products": items}

    async def release_inventory(self, products: list[OrderItemBase]):
        """
        Release inventory via atomic per-row increments (SAGA compensation).

        Each item is incremented with a single ``UPDATE … SET quantity = quantity + amount``
        statement so concurrent release events cannot double-add stock.
        """
        if not products:
            return
        reservations = await self.reservation_repository.get_order_for_update(
            products[0].order_id
        )
        for reservation in reservations:
            if reservation.status != "reserved":
                continue
            updated = await self.repository.atomic_increment_quantity(
                item_id=reservation.product_id,
                amount=reservation.quantity,
            )
            if updated is None:
                raise ProductReleaseError(
                    f"Cannot release inventory for product: {reservation.product_id} — product not found"
                )
            if reservation.variant_id is not None:
                variant = await self.variant_repository.atomic_increment_inventory(
                    reservation.variant_id, reservation.quantity
                )
                if variant is None:
                    raise ProductReleaseError(
                        f"Cannot release inventory for variant: {reservation.variant_id}"
                    )
            reservation.status = "released"
            await self.reservation_repository.update(reservation)
