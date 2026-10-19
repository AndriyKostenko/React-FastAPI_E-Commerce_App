import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { proxied } from "@/lib/gateway-proxy";
import type { ProductProps } from "@/types/product";

/** Catalogue reads from the browser, through the same-origin proxy. */
export class CatalogueApi {
  /**
   * A product with its gallery and variants. A shop card carries neither, so
   * Quick Add reads the full product before it builds the cart line.
   */
  static async product(productId: string): Promise<ProductProps> {
    const fallback = "Could not load this product.";
    let response: Response;
    try {
      response = await fetch(proxied(settings.api.endpoints.productDetailed(productId)), { cache: "no-store" });
    } catch (error) {
      throw ApiError.from(error, fallback);
    }
    if (!response.ok) throw await ApiError.fromResponse(response, fallback);
    return (await response.json()) as ProductProps;
  }
}
