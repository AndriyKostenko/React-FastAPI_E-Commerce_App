// toShopCard and the shop filters on its facets: the card is built on the Next
// server, and the filters must answer exactly as when they read variant keys.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { ProductSummary } from "@/types/product";
import { toShopCard } from "@/utils/shopCard";
import { applyProductFilters, EMPTY_FILTERS, facetsOf } from "@/utils/productFilters";

const summary = (id: string, keys: string[], ratings: number[] = [], optionNames?: string[]): ProductSummary => ({
    id,
    name: `tee ${id}`,
    price: 30,
    in_stock: true,
    date_created: "2026-10-01T00:00:00Z",
    category: { id: "cat", name: "t-shirts" },
    reviews: ratings.map((rating) => ({ rating })),
    variants: keys.map((variant_key) => ({ variant_key, active: true })),
    ...(optionNames ? { variant_option_names: optionNames } : {}),
});

describe("toShopCard", () => {
    it("keeps what the shop compares and drops the variant keys", () => {
        const card = toShopCard(summary("a", ["Black-XL", "Black-L", "Navy Blue-XL"], [5, 4]));
        assert.equal(card.averageRating, 4.5);
        assert.equal(card.reviewCount, 2);
        assert.equal(card.variantCount, 3);
        assert.deepEqual(card.facets, [
            ["black", "XL"],
            ["black", "L"],
            ["blue", "XL"],
        ]);
        assert.equal("variants" in card, false);
        assert.equal("reviews" in card, false);
    });

    it("lists each colour and size pair once", () => {
        // "Navy Blue" and "Blue" are one family, "XXL" and "2XL" one size.
        const card = toShopCard(summary("b", ["Navy Blue-XXL", "Blue-2XL", "Blue-2XL"]));
        assert.deepEqual(card.facets, [["blue", "2XL"]]);
        assert.equal(card.variantCount, 3);
    });

    it("counts only active variants", () => {
        const product = summary("c", ["Black-M"]);
        product.variants = [
            { variant_key: "Black-M", active: true },
            // Card listings carry active variants only; a full product may not.
            { variant_key: "White-M", active: false },
        ];
        assert.equal(toShopCard(product).variantCount, 1);
    });
});

describe("facet pairs", () => {
    it("gives a variant in two families one pair per family, and none as empty", () => {
        assert.deepEqual(toShopCard(summary("d", ["Black and white-M", "1 Style-L"])).facets, [
            ["black", "M"],
            ["white", "M"],
            ["", "L"],
        ]);
    });
});

describe("facet pairs by the product's option names", () => {
    it("reads a Size-Color key's size, which the end of the key does not hold", () => {
        // Read by keyword alone, "M-Red" gave red and no size.
        assert.deepEqual(toShopCard(summary("e", ["M-Red", "XXL-Navy Blue"], [], ["Size", "Color"])).facets, [
            ["red", "M"],
            ["blue", "2XL"],
        ]);
    });

    it("ignores parts that are neither a colour nor a size", () => {
        assert.deepEqual(toShopCard(summary("f", ["Brown-XS-1pcs"], [], ["Color", "Size", "Quantity"])).facets, [
            ["brown", "XS"],
        ]);
    });

    it("gives no size for a size part that is not an apparel size", () => {
        assert.deepEqual(toShopCard(summary("g", ["40-Black"], [], ["Size", "Color"])).facets, [["black", ""]]);
    });

    it("reads a colour-only key by its name", () => {
        assert.deepEqual(toShopCard(summary("h", ["White"], [], ["Color"])).facets, [["white", ""]]);
    });

    it("falls back to the keyword reading when a key does not fit the names", () => {
        // "Army-green-XL" splits into three parts for two names.
        assert.deepEqual(toShopCard(summary("i", ["Army-green-XL"], [], ["Color", "Size"])).facets, [["green", "XL"]]);
    });

    it("keeps the keyword reading where the names settle nothing", () => {
        // CJ names a whole "Apricot S" key just "Size": the part is no size, so the
        // size comes from the end of the key and the colour by keyword, as before.
        assert.deepEqual(toShopCard(summary("k", ["Apricot S", "Black XL"], [], ["Size"])).facets, [
            ["beige", "S"],
            ["black", "XL"],
        ]);
    });

    it("falls back to the keyword reading when no name is a colour or a size", () => {
        assert.deepEqual(toShopCard(summary("j", ["Black-L"], [], ["Style", "Model"])).facets, [["black", "L"]]);
    });
});

describe("filters on shop cards", () => {
    const cards = [
        toShopCard(summary("black-m-white-xl", ["Black-M", "White-XL"])),
        toShopCard(summary("black-xl", ["Black-XL"])),
        toShopCard(summary("size-only", ["M", "L"])),
        toShopCard(summary("size-color-xl", ["XL-Black", "M-White"], [], ["Size", "Color"])),
    ];

    it("matches colour and size on the same variant", () => {
        const found = applyProductFilters(cards, { ...EMPTY_FILTERS, colors: ["black"], sizes: ["XL"] });
        assert.deepEqual(found.map((card) => card.id), ["black-xl", "size-color-xl"]);
    });

    it("matches a size alone on any variant", () => {
        const found = applyProductFilters(cards, { ...EMPTY_FILTERS, sizes: ["M"] });
        assert.deepEqual(found.map((card) => card.id), ["black-m-white-xl", "size-only", "size-color-xl"]);
    });

    it("offers every colour and size of the catalogue, in chip order", () => {
        const facets = facetsOf(cards);
        assert.deepEqual(facets.colors, ["black", "white"]);
        assert.deepEqual(facets.sizes, ["M", "L", "XL"]);
    });
});
