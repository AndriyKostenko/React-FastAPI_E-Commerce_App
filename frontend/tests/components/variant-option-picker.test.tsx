// VariantOptionPicker with a real VariantMatrix, holding the selection the way
// the product page does: a click asks the matrix which variant to move to.
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VariantOptionPicker from "@/app/products/[productId]/VariantOptionPicker";
import type { ProductVariantProps } from "@/types/product";
import { VariantMatrix } from "@/utils/productVariants";

const variant = (key: string, inventory: number): ProductVariantProps => ({
    id: key,
    vid: `vid-${key}`,
    variant_key: key,
    inventory_num: inventory,
    active: true,
});

// Black comes in M (in stock) and L (sold out), Red in M and XL: no black XL, no red L.
const VARIANTS = [variant("Black-M", 10), variant("Black-L", 0), variant("Red-M", 5), variant("Red-XL", 3)];

const Picker = () => {
    const [matrix] = useState(() => new VariantMatrix(VARIANTS, ["Color", "Size"]));
    const [selected, setSelected] = useState(() => matrix.initialVariant());
    const selection = matrix.selectionOf(selected);
    return (
        <VariantOptionPicker
            matrix={matrix}
            selection={selection}
            onChoose={(name, value) => setSelected(matrix.choose(name, value, selection) ?? selected)}
        />
    );
};

const option = (name: string) => within(screen.getByRole("group", { name: new RegExp(`^${name}`) }));

describe("VariantOptionPicker", () => {
    it("starts on the first in-stock variant and names the choice in each legend", () => {
        render(<Picker />);
        expect(screen.getByRole("group", { name: "Color Black" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Size M" })).toBeInTheDocument();
        expect(option("Color").getByRole("button", { name: "Black" })).toHaveAttribute("aria-pressed", "true");
        expect(option("Size").getByRole("button", { name: "M" })).toHaveAttribute("aria-pressed", "true");
    });

    it("shows a sold-out size and a size missing in this colour, both disabled and explained", () => {
        render(<Picker />);
        const soldOut = option("Size").getByRole("button", { name: "L" });
        expect(soldOut).toBeDisabled();
        expect(soldOut).toHaveAttribute("title", "Sold out");

        const missing = option("Size").getByRole("button", { name: "XL" });
        expect(missing).toBeDisabled();
        expect(missing).toHaveAttribute("title", "Not available with this choice");
    });

    it("keeps the size when another colour has it, and judges sizes against the new colour", async () => {
        const user = userEvent.setup();
        render(<Picker />);
        await user.click(option("Color").getByRole("button", { name: "Red" }));

        expect(screen.getByRole("group", { name: "Color Red" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Size M" })).toBeInTheDocument();
        expect(option("Size").getByRole("button", { name: "XL" })).toBeEnabled();
        expect(option("Size").getByRole("button", { name: "L" })).toHaveAttribute("title", "Not available with this choice");
    });

    it("never blocks a colour by the size chosen below it", async () => {
        const user = userEvent.setup();
        render(<Picker />);
        await user.click(option("Color").getByRole("button", { name: "Red" }));
        await user.click(option("Size").getByRole("button", { name: "XL" }));

        // There is no black XL, but Black stays choosable and moves to a black size.
        await user.click(option("Color").getByRole("button", { name: "Black" }));
        expect(screen.getByRole("group", { name: "Color Black" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Size M" })).toBeInTheDocument();
    });
});
