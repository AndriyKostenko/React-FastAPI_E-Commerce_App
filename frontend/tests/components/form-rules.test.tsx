// The shared form rules through the real Input and react-hook-form: what the
// sign-up form refuses before sending, and what it sends.
import { useState } from "react";
import { type FieldValues, useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Input from "@/components/ui/Input";
import { EMAIL_RULES, NAME_RULES, NEW_PASSWORD_RULES, repeatOf } from "@/utils/formRules";

/** The sign-up form's fields and rules, without the captcha and the request. */
const SignUp = () => {
    const [sent, setSent] = useState<FieldValues | null>(null);
    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<FieldValues>();
    return (
        <form onSubmit={handleSubmit(setSent)}>
            <Input id="name" label="Name" register={register} errors={errors} required validationRules={NAME_RULES} />
            <Input id="email" label="Email" register={register} errors={errors} required validationRules={EMAIL_RULES} />
            <Input
                id="password"
                label="Password"
                type="password"
                register={register}
                errors={errors}
                required
                validationRules={NEW_PASSWORD_RULES}
            />
            <Input
                id="repeat"
                label="Repeat password"
                type="password"
                register={register}
                errors={errors}
                required
                validationRules={repeatOf("password")}
            />
            <button type="submit">Sign up</button>
            {sent && <pre data-testid="sent">{JSON.stringify(sent)}</pre>}
        </form>
    );
};

const fill = async (values: Record<string, string>) => {
    const user = userEvent.setup();
    for (const [label, value] of Object.entries(values)) {
        await user.type(screen.getByLabelText(label, { exact: true }), value);
    }
    await user.click(screen.getByRole("button", { name: "Sign up" }));
};

describe("form rules", () => {
    it("sends a trimmed name and email once every rule passes", async () => {
        render(<SignUp />);
        await fill({
            Name: "  Ada  ",
            Email: "  ada@example.com ",
            Password: "longenough",
            "Repeat password": "longenough",
        });
        const sent = JSON.parse((await screen.findByTestId("sent")).textContent ?? "{}");
        expect(sent).toMatchObject({ name: "Ada", email: "ada@example.com" });
    });

    it("explains each refusal and sends nothing", async () => {
        render(<SignUp />);
        await fill({ Name: "A", Email: "not-an-email", Password: "short", "Repeat password": "different" });
        expect(await screen.findByText("At least 2 characters")).toBeInTheDocument();
        expect(screen.getByText("Enter a valid email address")).toBeInTheDocument();
        expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
        expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
        expect(screen.queryByTestId("sent")).not.toBeInTheDocument();
    });

    it("stops typing at the server's maximum", async () => {
        render(<SignUp />);
        expect(screen.getByLabelText("Name")).toHaveAttribute("maxLength", "50");
        expect(screen.getByLabelText("Email")).toHaveAttribute("maxLength", "254");
        expect(screen.getByLabelText("Password")).toHaveAttribute("maxLength", "100");

        const user = userEvent.setup();
        await user.type(screen.getByLabelText("Name"), "x".repeat(60));
        expect(screen.getByLabelText("Name")).toHaveValue("x".repeat(50));
    });
});
