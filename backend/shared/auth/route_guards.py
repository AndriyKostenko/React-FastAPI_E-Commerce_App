"""
Authorisation guards every service applies itself (bug list 4).

The gateway already enforces these rules, but a service that relied on that
alone was one forgotten check — or one request that reached it directly — away
from serving anyone anything. Each route now states its own requirement:

    @router.delete("/products/{product_id}")
    async def delete_product(product_id: UUID, admin: AdminDep): ...

    @router.get("/users/{user_id}/cart")
    async def get_cart(user_id: UUID, caller: SelfOrAdminDep): ...

For a resource whose owner is only known after loading it (an order, a
payment), load it and call ``ensure_owner_or_admin(caller, resource.user_id)``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from shared.settings import get_settings
from shared.utils.authenticated_caller import AuthenticatedCaller


def _admin_role() -> str:
    # Read per request rather than captured at import, so the settings object
    # tests adjust in place is the one that decides.
    return get_settings().SECRET_ROLE


def require_caller(request: Request) -> AuthenticatedCaller:
    """Any signed-in user; 401 for an anonymous request."""
    return AuthenticatedCaller.require(request)


def require_admin(request: Request) -> AuthenticatedCaller:
    """An admin; 401 when anonymous, 403 for anyone else."""
    return AuthenticatedCaller.require_admin(request, _admin_role())


def require_self_or_admin(user_id: UUID, request: Request) -> AuthenticatedCaller:
    """
    The user named by the route's ``{user_id}`` path parameter, or an admin.

    FastAPI fills ``user_id`` from the path, so this only suits routes that
    declare one.
    """
    caller = AuthenticatedCaller.require(request)
    ensure_owner_or_admin(caller, user_id)
    return caller


def ensure_owner_or_admin(caller: AuthenticatedCaller, owner_id: UUID | None) -> None:
    """Raise 403 unless ``caller`` owns the resource or is an admin."""
    if caller.is_admin(_admin_role()):
        return
    if owner_id is None or caller.user_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own resources",
        )


CallerDep = Annotated[AuthenticatedCaller, Depends(require_caller)]
AdminDep = Annotated[AuthenticatedCaller, Depends(require_admin)]
SelfOrAdminDep = Annotated[AuthenticatedCaller, Depends(require_self_or_admin)]
