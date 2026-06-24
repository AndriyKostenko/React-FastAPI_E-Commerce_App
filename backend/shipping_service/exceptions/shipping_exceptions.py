from uuid import UUID

from shared.exceptions.base_exceptions import BaseAPIException


class ShippingMethodNotFoundError(BaseAPIException):
    def __init__(self, method_id: UUID):
        self.method_id = method_id
        super().__init__(
            status_code=404,
            detail=f"Shipping method with id {method_id} not found"
        )


class ShipmentNotFoundError(BaseAPIException):
    def __init__(self, shipment_id: UUID | None = None, order_id: UUID | None = None):
        if shipment_id:
            detail = f"Shipment with id {shipment_id} not found"
        elif order_id:
            detail = f"Shipment for order {order_id} not found"
        else:
            detail = "Shipment not found"
        super().__init__(status_code=404, detail=detail)


class DuplicateShipmentError(BaseAPIException):
    def __init__(self, order_id: UUID):
        super().__init__(
            status_code=409,
            detail=f"Shipment for order {order_id} already exists"
        )


class ShipmentNotCancellableError(BaseAPIException):
    def __init__(self, shipment_id: UUID, status: str):
        super().__init__(
            status_code=409,
            detail=f"Shipment {shipment_id} cannot be cancelled because it is already {status}"
        )


class InvalidShipmentStatusError(BaseAPIException):
    def __init__(self, status: str):
        super().__init__(
            status_code=400,
            detail=f"Invalid shipment status transition: {status}"
        )
