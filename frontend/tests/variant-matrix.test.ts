// VariantMatrix on the variant key shapes CJ actually sends (taken from the
// synced catalogue, 2026-10-20): "Color-Size", "Size-Color", colour only,
// "Color-Size-style" with one style, and products whose names do not fit.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { ProductVariantProps } from "@/types/product";
import { MAX_SHOWN_STOCK, shownStock, VariantMatrix } from "@/utils/productVariants";

const variant = (key: string, inventory: number | null = 10): ProductVariantProps => ({
    id: key,
    vid: `vid-${key}`,
    variant_key: key,
    inventory_num: inventory,
    active: true,
});

const optionNames = (matrix: VariantMatrix): string[] => matrix.options.map((option) => option.name);

describe("VariantMatrix options", () => {
    it("splits Color-Size keys into a colour and a size", () => {
        const matrix = new VariantMatrix([variant("Black-M"), variant("Black-L"), variant("Red-M")], ["Color", "Size"]);
        assert.deepEqual(optionNames(matrix), ["Color", "Size"]);
        assert.deepEqual(matrix.options[0].values, ["Black", "Red"]);
        assert.equal(matrix.options[0].isColor, true);
        assert.deepEqual(matrix.options[1].values, ["M", "L"]);
    });

    it("reads Size-Color keys in the supplier's order and lists colour first", () => {
        const matrix = new VariantMatrix([variant("M-Red"), variant("M-Black"), variant("L-Red")], ["Size", "Color"]);
        assert.deepEqual(optionNames(matrix), ["Color", "Size"]);
        assert.deepEqual(matrix.options[0].values, ["Red", "Black"]);
        assert.deepEqual(matrix.selectionOf(matrix.initialVariant()), { Color: "Red", Size: "M" });
    });

    it("offers a colour-only product as colours", () => {
        const matrix = new VariantMatrix([variant("Black"), variant("White")], ["Color"]);
        assert.deepEqual(optionNames(matrix), ["Color"]);
        assert.deepEqual(matrix.options[0].values, ["Black", "White"]);
    });

    it("hides an option with one value across the product", () => {
        const matrix = new VariantMatrix(
            [variant("Brown-XS-1pcs"), variant("Brown-S-1pcs"), variant("Navy Blue-XS-1pcs")],
            ["Color", "Size", "style"],
        );
        assert.deepEqual(optionNames(matrix), ["Color", "Size"]);
        assert.deepEqual(matrix.options[0].values, ["Brown", "Navy Blue"]);
    });

    it("falls back to whole keys when the names do not fit the keys", () => {
        // CJ names this print-on-demand product "Size" but sends "Black S".
        const fitsNot = new VariantMatrix([variant("Black-S"), variant("Black-M")], ["Size", "Color", "Style"]);
        assert.deepEqual(optionNames(fitsNot), [VariantMatrix.FALLBACK_OPTION]);
        assert.deepEqual(fitsNot.options[0].values, ["Black-S", "Black-M"]);

        const unnamed = new VariantMatrix([variant("Black S"), variant("Black M")]);
        assert.deepEqual(unnamed.options[0].values, ["Black S", "Black M"]);
    });

    it("shows no option for a single variant, which stays buyable", () => {
        const matrix = new VariantMatrix([variant("Black-M")], ["Color", "Size"]);
        assert.deepEqual(matrix.options, []);
        assert.equal(matrix.initialVariant()?.id, "Black-M");
    });

    it("keeps a variant with an empty key part reachable", () => {
        const matrix = new VariantMatrix([variant("Black-"), variant("Black-M")], ["Color", "Size"]);
        assert.deepEqual(matrix.options[0].values, ["", "M"]);
        assert.equal(VariantMatrix.valueLabel(""), VariantMatrix.EMPTY_VALUE_LABEL);
        assert.equal(matrix.choose("Size", "", {})?.id, "Black-");
    });
});

describe("VariantMatrix availability", () => {
    // Red has no XL, and Black-L is sold out.
    const matrix = new VariantMatrix(
        [variant("Black-M"), variant("Black-L", 0), variant("Black-XL"), variant("Red-M"), variant("Red-L")],
        ["Color", "Size"],
    );

    it("judges a size against the chosen colour", () => {
        const red = { Color: "Red", Size: "M" };
        assert.equal(matrix.valueState("Size", "M", red), "available");
        assert.equal(matrix.valueState("Size", "XL", red), "missing");
        assert.equal(matrix.valueState("Size", "L", { Color: "Black", Size: "M" }), "sold-out");
    });

    it("never blocks a colour because of the size under it", () => {
        assert.equal(matrix.valueState("Color", "Red", { Color: "Black", Size: "XL" }), "available");
    });

    it("keeps the current size when the new colour has it, else moves to one in stock", () => {
        assert.equal(matrix.choose("Color", "Red", { Color: "Black", Size: "M" })?.id, "Red-M");
        assert.equal(matrix.choose("Color", "Red", { Color: "Black", Size: "XL" })?.id, "Red-M");
        // Black-L exists but is sold out: an in-stock Black wins over keeping L.
        assert.equal(matrix.choose("Color", "Black", { Color: "Red", Size: "L" })?.id, "Black-M");
    });

    it("opens on the first variant in stock", () => {
        const soldOutFirst = new VariantMatrix([variant("Black-M", 0), variant("Black-L")], ["Color", "Size"]);
        assert.equal(soldOutFirst.initialVariant()?.id, "Black-L");
    });

    it("treats unknown stock as in stock", () => {
        assert.equal(VariantMatrix.isInStock(variant("Black-M", null)), true);
    });
});

describe("shownStock", () => {
    it("shows at most MAX_SHOWN_STOCK units and never a negative count", () => {
        assert.equal(shownStock(39_998), MAX_SHOWN_STOCK);
        assert.equal(shownStock(100), 100);
        assert.equal(shownStock(7), 7);
        assert.equal(shownStock(-3), 0);
    });
});
