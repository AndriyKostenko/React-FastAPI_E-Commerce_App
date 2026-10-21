// StarRating: the read-only stars screen readers hear as one figure, and the
// picker of whole stars the review form uses.
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StarRating from "@/components/ui/StarRating";

const Picker = () => {
    const [value, setValue] = useState(0);
    return (
        <>
            <StarRating value={value} onChange={setValue} label="Your rating" />
            <p>chosen {value}</p>
        </>
    );
};

describe("StarRating", () => {
    it("reads a fractional rating as one image, clamped to 0..5", () => {
        const { rerender } = render(<StarRating value={4.25} />);
        expect(screen.getByRole("img", { name: "Rated 4.3 out of 5" })).toBeInTheDocument();
        rerender(<StarRating value={7} />);
        expect(screen.getByRole("img", { name: "Rated 5.0 out of 5" })).toBeInTheDocument();
        expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    });

    it("picks whole stars as a radio group", async () => {
        const user = userEvent.setup();
        render(<Picker />);
        const group = screen.getByRole("radiogroup", { name: "Your rating" });
        expect(group).toBeInTheDocument();
        expect(screen.getAllByRole("radio")).toHaveLength(5);

        await user.click(screen.getByRole("radio", { name: "4 stars" }));
        expect(screen.getByText("chosen 4")).toBeInTheDocument();
        expect(screen.getByRole("radio", { name: "4 stars" })).toHaveAttribute("aria-checked", "true");
        expect(screen.getByRole("radio", { name: "1 star" })).toHaveAttribute("aria-checked", "false");
    });

    it("can be set from the keyboard", async () => {
        const user = userEvent.setup();
        render(<Picker />);
        await user.tab();
        await user.tab();
        expect(screen.getByRole("radio", { name: "2 stars" })).toHaveFocus();
        await user.keyboard("{Enter}");
        expect(screen.getByText("chosen 2")).toBeInTheDocument();
    });
});
