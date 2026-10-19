import type { ImageProps } from "@/types/image";
import type { ProductProps, ProductVariantProps } from "@/types/product";
import type { OrderProductInput } from "@/types/cart";

/**
 * A catalogue product as a cart line: one unit of the given variant (or of
 * the product itself when it has none), priced at that variant's retail price.
 * Shared by the product page and the cards' Quick Add, so both put the same
 * line in the cart.
 */
export const toCartLine = (
  product: ProductProps,
  variant: ProductVariantProps | undefined,
  images: ImageProps[],
): ProductProps => ({
  id: product.id,
  category: product.category,
  quantity: 1,
  in_stock: product.in_stock,
  name: product.name,
  description: product.description,
  brand: product.brand,
  price: variant?.retail_price ?? product.price,
  date_created: product.date_created,
  selected_image: images[0],
  reviews: product.reviews,
  images,
  supplier_id: product.supplier_id,
  variants: product.variants,
  selected_variant_id: variant?.id ?? null,
  fulfillment_type: product.supplier_id === "cjdropshipping" ? "cj" : "catalog",
});

/** A product's active variants, whichever variant shape it carries (full or card). */
export const activeVariantsOf = <V extends Pick<ProductVariantProps, "active">>(product: {
  variants?: V[];
}): V[] => product.variants?.filter((variant) => variant.active) ?? [];

/**
 * Cart lines as the server prices and orders them: identity, variant, quantity
 * and customization, never the price. The cart page's pricing and checkout send
 * exactly this, so both are priced alike.
 */
export const buildOrderProducts = (products: ProductProps[]): OrderProductInput[] =>
  products.map((product) =>
    product.fulfillment_type === "custom"
      ? {
          id: product.id,
          quantity: product.quantity,
          fulfillment_type: "custom" as const,
          customization: product.customization,
        }
      : {
          id: product.id,
          variant_id: product.selected_variant_id ?? undefined,
          quantity: product.quantity,
          fulfillment_type: product.fulfillment_type ?? "catalog",
        },
  );
