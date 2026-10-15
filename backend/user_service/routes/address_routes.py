from uuid import UUID

from fastapi import APIRouter, status

from dependencies.dependencies import address_service_dependency, current_user_dependency
from schemas.address_schemas import AddressInput, AddressRead


# The signed-in user's own address book. Always "me": the user comes from the
# gateway's assertion, never from the path, so nobody can name another user.
address_routes = APIRouter(prefix="/users/me/addresses", tags=["addresses"])


@address_routes.get("", response_model=list[AddressRead], summary="My saved addresses, the default first")
async def list_my_addresses(current_user: current_user_dependency, addresses: address_service_dependency):
    return await addresses.list_addresses(current_user.id)


@address_routes.post(
    "", response_model=AddressRead, status_code=status.HTTP_201_CREATED, summary="Save an address"
)
async def create_my_address(
    data: AddressInput, current_user: current_user_dependency, addresses: address_service_dependency
):
    return await addresses.create_address(current_user.id, data)


@address_routes.put("/{address_id}", response_model=AddressRead, summary="Replace a saved address")
async def replace_my_address(
    address_id: UUID,
    data: AddressInput,
    current_user: current_user_dependency,
    addresses: address_service_dependency,
):
    return await addresses.replace_address(current_user.id, address_id, data)


@address_routes.post("/{address_id}/default", response_model=AddressRead, summary="Make an address the default")
async def make_my_address_default(
    address_id: UUID, current_user: current_user_dependency, addresses: address_service_dependency
):
    return await addresses.make_default(current_user.id, address_id)


@address_routes.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved address")
async def delete_my_address(
    address_id: UUID, current_user: current_user_dependency, addresses: address_service_dependency
) -> None:
    await addresses.delete_address(current_user.id, address_id)
