// toShopCard and the shop filters on its facets: the card is built on the Next
// server, and the filters must answer exactly as when they read variant keys.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { ProductSummary } from "@/types/product";
import { toShopCard } from "@/utils/shopCard";
import { applyProductFilters, EMPTY_FILTERS, facetsOf } from "@/utils/productFilters";

const summary = (id: string, keys: string[], ratings: number[] = []): ProductSummary => ({
    id,
    name: `tee ${id}`,
    price: 30,
    in_stock: true,
    date_created: "2026-10-01T00:00:00Z",
    category: { id: "cat", name: "t-shirts" },
    reviews: ratings.map((rating) => ({ rating })),
    variants: keys.map((variant_key) => ({ variant_key, active: true })),
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

describe("filters on shop cards", () => {
    const cards = [
        toShopCard(summary("black-m-white-xl", ["Black-M", "White-XL"])),
        toShopCard(summary("black-xl", ["Black-XL"])),
        toShopCard(summary("size-only", ["M", "L"])),
    ];

    it("matches colour and size on the same variant", () => {
        const found = applyProductFilters(cards, { ...EMPTY_FILTERS, colors: ["black"], sizes: ["XL"] });
        assert.deepEqual(found.map((card) => card.id), ["black-xl"]);
    });

    it("matches a size alone on any variant", () => {
        const found = applyProductFilters(cards, { ...EMPTY_FILTERS, sizes: ["M"] });
        assert.deepEqual(found.map((card) => card.id), ["black-m-white-xl", "size-only"]);
    });

    it("offers every colour and size of the catalogue, in chip order", () => {
        const facets = facetsOf(cards);
        assert.deepEqual(facets.colors, ["black", "white"]);
        assert.deepEqual(facets.sizes, ["M", "L", "XL"]);
    });
});
