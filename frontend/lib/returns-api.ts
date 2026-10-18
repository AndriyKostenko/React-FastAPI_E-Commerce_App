import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { proxied } from "@/lib/gateway-proxy";
import type { ReturnRequestCreate, ReturnRequestView } from "@/types/returns";

/**
 * The customer's return calls, made from the browser through the same-origin
 * proxy (which adds the token on the server). Failures throw an ApiError
 * carrying order-service's own message, e.g. why a line cannot be returned.
 */
export class ReturnsApi {
  /**
   * Asks to return units of a delivered order. Multipart: the request as JSON
   * in the `request` field and each photo as a `photos` file.
   */
  static async request(
    orderId: string,
    create: ReturnRequestCreate,
    photos: readonly File[],
  ): Promise<ReturnRequestView> {
    const form = new FormData();
    form.append("request", JSON.stringify(create));
    photos.forEach((photo) => form.append("photos", photo));
    // No Content-Type header: the browser sets multipart/form-data with its boundary.
    return ReturnsApi.post(
      settings.api.endpoints.orderReturns(orderId),
      form,
      "Could not send your return request.",
    );
  }

  /** Withdraws a return nobody has decided on yet. */
  static cancel(orderId: string, returnId: string): Promise<ReturnRequestView> {
    return ReturnsApi.post(
      settings.api.endpoints.cancelReturn(orderId, returnId),
      undefined,
      "Could not withdraw the return.",
    );
  }

  private static async post(
    gatewayUrl: string,
    body: FormData | undefined,
    fallback: string,
  ): Promise<ReturnRequestView> {
    let response: Response;
    try {
      response = await fetch(proxied(gatewayUrl), {
        method: "POST",
        body,
        cache: "no-store",
      });
    } catch (error) {
      throw ApiError.from(error, fallback);
    }
    if (!response.ok) throw await ApiError.fromResponse(response, fallback);
    return (await response.json()) as ReturnRequestView;
  }
}
