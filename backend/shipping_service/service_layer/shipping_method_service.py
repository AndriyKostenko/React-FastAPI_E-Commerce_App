from uuid import UUID

from shared.schemas.shipping_schemas import ShippingMethodSchema, CreateShippingMethod, UpdateShippingMethod
from database_layer.shipping_repository import ShippingMethodRepository
from exceptions.shipping_exceptions import ShippingMethodNotFoundError
from models.shipping_models import ShippingMethod


class ShippingMethodService:
    """Service layer for managing shipping methods."""

    def __init__(self, repository: ShippingMethodRepository):
        self.repository: ShippingMethodRepository = repository

    async def create_method(self, method_data: CreateShippingMethod) -> ShippingMethodSchema:
        """Create a new shipping method."""
        new_method = ShippingMethod(
            name=method_data.name,
            carrier=method_data.carrier,
            base_cost=method_data.base_cost,
            estimated_days=method_data.estimated_days,
            is_active=method_data.is_active,
        )
        created = await self.repository.create(new_method)
        return ShippingMethodSchema.model_validate(created)

    async def get_method_by_id(self, method_id: UUID) -> ShippingMethodSchema:
        """Get a shipping method by ID."""
        method = await self.repository.get_by_id(method_id)
        if not method:
            raise ShippingMethodNotFoundError(method_id=method_id)
        return ShippingMethodSchema.model_validate(method)

    async def list_active_methods(self) -> list[ShippingMethodSchema]:
        """List all active shipping methods."""
        methods = await self.repository.get_active_methods()
        return [ShippingMethodSchema.model_validate(method) for method in methods]

    async def list_all_methods(self) -> list[ShippingMethodSchema]:
        """List all shipping methods (including inactive)."""
        methods = await self.repository.get_all(sort_by="base_cost", sort_order="asc")
        return [ShippingMethodSchema.model_validate(method) for method in methods]

    async def update_method(self, method_id: UUID, method_data: UpdateShippingMethod) -> ShippingMethodSchema:
        """Update an existing shipping method."""
        method = await self.repository.get_by_id(method_id)
        if not method:
            raise ShippingMethodNotFoundError(method_id=method_id)

        update_data = method_data.model_dump(exclude_unset=True)
        if not update_data:
            return ShippingMethodSchema.model_validate(method)

        updated = await self.repository.update_by_id(method_id, update_data)
        return ShippingMethodSchema.model_validate(updated)

    async def delete_method(self, method_id: UUID) -> None:
        """Delete a shipping method."""
        method = await self.repository.get_by_id(method_id)
        if not method:
            raise ShippingMethodNotFoundError(method_id=method_id)
        await self.repository.delete(method)
