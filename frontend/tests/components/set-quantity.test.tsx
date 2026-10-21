// SetQuantity: named buttons, and the count announced as it changes.
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SetQuantity from "@/components/4. Featured Collections/SetQuantity";
import type { ProductProps } from "@/types/product";

// SetQuantity reads only `quantity` from the line; the rest of ProductProps is not rendered.
const line = (quantity: number) => ({ quantity }) as ProductProps;

/** The product page's rule: between 1 and the units on offer. */
const Stepper = ({ max }: { max: number }) => {
    const [quantity, setQuantity] = useState(1);
    return (
        <SetQuantity
            cartProduct={line(quantity)}
            handleQtyIncrease={() => setQuantity((current) => Math.min(current + 1, max))}
            handleQtyDecrease={() => setQuantity((current) => Math.max(current - 1, 1))}
        />
    );
};

describe("SetQuantity", () => {
    it("names its buttons and its count", () => {
        render(<Stepper max={3} />);
        expect(screen.getByRole("button", { name: "Increase quantity" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Decrease quantity" })).toBeInTheDocument();
        expect(screen.getByRole("status", { name: "Quantity" })).toHaveTextContent("1");
    });

    it("steps within the limits the page sets", async () => {
        const user = userEvent.setup();
        render(<Stepper max={3} />);
        const more = screen.getByRole("button", { name: "Increase quantity" });
        await user.click(more);
        await user.click(more);
        await user.click(more);
        expect(screen.getByRole("status", { name: "Quantity" })).toHaveTextContent("3");

        const fewer = screen.getByRole("button", { name: "Decrease quantity" });
        for (let i = 0; i < 4; i += 1) await user.click(fewer);
        expect(screen.getByRole("status", { name: "Quantity" })).toHaveTextContent("1");
    });

    it("does not submit a form it sits in", async () => {
        let submitted = false;
        const user = userEvent.setup();
        render(
            <form onSubmit={(event) => { event.preventDefault(); submitted = true; }}>
                <Stepper max={3} />
            </form>,
        );
        await user.click(screen.getByRole("button", { name: "Increase quantity" }));
        expect(submitted).toBe(false);
    });
});
