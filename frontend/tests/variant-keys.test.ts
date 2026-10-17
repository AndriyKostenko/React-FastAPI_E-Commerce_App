// How supplier variant keys are split into colour and size, for the product
// page's picker (getVariantOption) and the shop filter (facetsOf,
// applyProductFilters). Pure functions: no stack, no stand-ins.
//
// The keys are the formats CJ actually sends (see the local catalogue):
// "Black-XL", "Army green XXXL", "1 Style-M".
//
// Run with:  npm run test:variants

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { compareSizes, parseVariantKey } from "@/utils/productVariants";
import { applyProductFilters, EMPTY_FILTERS, facetsOf } from "@/utils/productFilters";
import type { ProductProps } from "@/types/product";

describe("parseVariantKey", () => {
    const cases: Array<[key: string, color: string | null, size: string | null]> = [
        // Hyphenated: as before.
        ["Black-XL", "Black", "XL"],
        ["Black-2XL", "Black", "2XL"],
        ["1 Style-M", "1 Style", "M"],
        ["Black-White-XL", "Black - White", "XL"],
        [" Black - XL ", "Black", "XL"],
        // Space-separated, the case the picker got wrong.
        ["Apricot L", "Apricot", "L"],
        ["Army green XXXL", "Army green", "XXXL"],
        ["Hole blue S", "Hole blue", "S"],
        ["Hami Orange XXXXL", "Hami Orange", "XXXXL"],
        // A size alone.
        ["XL", null, "XL"],
        // No apparel size: the original rule, unchanged.
        ["Red-38", "Red", "38"],
        ["One Size", null, "One Size"],
        ["", null, null],
    ];

    for (const [key, color, size] of cases) {
        it(`"${key}" is colour ${JSON.stringify(color)}, size ${JSON.stringify(size)}`, () => {
            assert.deepEqual(parseVariantKey(key), { color, size });
        });
    }
});

describe("compareSizes", () => {
    it("puts sizes in wearing order, whichever way they are spelled", () => {
        // The order CJ lists one product's sizes in.
        const listed = ["XL", "XXL", "XXXL", "XXXXL", "L", "M", "S"];
        assert.deepEqual(listed.toSorted(compareSizes), ["S", "M", "L", "XL", "XXL", "XXXL", "XXXXL"]);
        assert.deepEqual(["3XL", "XXL", "M"].toSorted(compareSizes), ["M", "XXL", "3XL"]);
    });

    it("keeps sizes it does not know after the known ones, in their given order", () => {
        assert.deepEqual(["One Size", "M", "38", "S"].toSorted(compareSizes), ["S", "M", "One Size", "38"]);
    });
});

/** A catalogue product with these active variant keys. */
const productWith = (id: string, keys: string[], price = 20): ProductProps => ({
    id,
    name: id,
    description: "",
    price,
    quantity: 100,
    brand: "test",
    supplier_id: "cjdropshipping",
    in_stock: true,
    date_created: "2026-10-01T00:00:00Z",
    selected_image: { id: `${id}-image`, product_id: id, image_url: "", image_color: "", image_color_code: "" },
    category: { id: "t-shirts", name: "t-shirts" },
    reviews: [],
    images: [],
    variants: keys.map((key, index) => ({ id: `${id}-${index}`, vid: `${id}-${index}`, variant_key: key, active: true })),
});

describe("shop filter on space-separated keys", () => {
    const spaced = productWith("spaced", ["Apricot L", "Army green XXXL", "Hole blue S"]);
    const hyphenated = productWith("hyphenated", ["Black-XL", "1 Style-M"]);

    it("offers the colours and sizes those keys name", () => {
        const facets = facetsOf([spaced, hyphenated]);
        assert.deepEqual(facets.colors, ["black", "green", "blue", "beige"]);
        assert.deepEqual(facets.sizes, ["S", "M", "L", "XL", "3XL"]);
    });

    it("matches colour and size on the same variant", () => {
        const products = [spaced, hyphenated];
        const ids = (colors: string[], sizes: string[]) =>
            applyProductFilters(products, { ...EMPTY_FILTERS, colors, sizes }).map((product) => product.id);
        assert.deepEqual(ids(["green"], ["3XL"]), ["spaced"]);
        // Green comes in 3XL only, and blue in S only: no green S exists.
        assert.deepEqual(ids(["green"], ["S"]), []);
        assert.deepEqual(ids([], ["M"]), ["hyphenated"]);
    });
});
