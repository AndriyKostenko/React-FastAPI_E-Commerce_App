'use client';

import type { ProductVariantProps } from "@/types/product";
import {
    getColorSwatch,
    type OptionValueState,
    VariantMatrix,
    type VariantSelection,
} from "@/utils/productVariants";

interface VariantOptionPickerProps<V extends ProductVariantProps> {
    matrix: VariantMatrix<V>;
    selection: VariantSelection;
    onChoose: (name: string, value: string) => void;
}

const STATE_TITLE: Record<Exclude<OptionValueState, "available">, string> = {
    "sold-out": "Sold out",
    missing: "Not available with this choice",
};

/**
 * One row of buttons per option (Color, Size, ...). A value that is sold out,
 * or does not exist with the choices above it, stays visible but disabled.
 */
const VariantOptionPicker = <V extends ProductVariantProps>({
    matrix,
    selection,
    onChoose,
}: VariantOptionPickerProps<V>) => (
    <>
        {matrix.options.map((option) => (
            <fieldset key={option.name} className="flex flex-col gap-2 max-w-[420px]">
                <legend className="font-label-bold text-primary mb-2">
                    {option.label}
                    {selection[option.name] !== undefined && (
                        <span className="ml-2 font-body-md text-secondary">
                            {VariantMatrix.valueLabel(selection[option.name])}
                        </span>
                    )}
                </legend>
                <div className="flex flex-wrap gap-2">
                    {option.values.map((value) => {
                        const state = matrix.valueState(option.name, value, selection);
                        const selected = selection[option.name] === value;
                        const disabled = state !== "available";
                        return (
                            <button
                                key={value}
                                type="button"
                                aria-pressed={selected}
                                disabled={disabled}
                                title={disabled ? STATE_TITLE[state] : undefined}
                                onClick={() => onChoose(option.name, value)}
                                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors ${
                                    selected
                                        ? "border-primary bg-white/70 text-primary"
                                        : "border-white/40 bg-white/40 hover:bg-white/60"
                                } disabled:cursor-not-allowed disabled:line-through disabled:opacity-50 disabled:hover:bg-white/40`}
                            >
                                {option.isColor && (
                                    <span
                                        aria-hidden="true"
                                        className="h-4 w-4 rounded-full border border-black/10"
                                        style={{ backgroundColor: getColorSwatch(value) }}
                                    />
                                )}
                                {VariantMatrix.valueLabel(value)}
                            </button>
                        );
                    })}
                </div>
            </fieldset>
        ))}
    </>
);

export default VariantOptionPicker;
