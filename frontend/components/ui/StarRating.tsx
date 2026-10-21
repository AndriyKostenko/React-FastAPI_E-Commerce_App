"use client";

import { useState } from "react";
import { MdStar } from "react-icons/md";

const STARS = [1, 2, 3, 4, 5] as const;
const SIZE_PX = { sm: 18, md: 24 } as const;
// MUI Rating's gold, which these replace.
const FILLED = "#faaf00";
const EMPTY = "rgba(0, 0, 0, 0.26)";

interface StarRatingProps {
    /** 0 to 5; shown to a tenth of a star. */
    value: number;
    size?: keyof typeof SIZE_PX;
    /** Makes the stars a picker of whole stars, 1 to 5. Without it they are read-only. */
    onChange?: (value: number) => void;
    /** What the picker is for, read by screen readers ("Your rating"). */
    label?: string;
}

const StarRow: React.FC<{ px: number; color: string }> = ({ px, color }) => (
    <span className="flex" aria-hidden="true">
        {STARS.map((star) => (
            <MdStar key={star} size={px} color={color} className="shrink-0" />
        ))}
    </span>
);

/**
 * Five stars: read-only with a fractional fill (4.3 fills four stars and a
 * third), or, with `onChange`, a radio group of whole stars.
 */
const StarRating: React.FC<StarRatingProps> = ({ value, size = "md", onChange, label = "Rating" }) => {
    const px = SIZE_PX[size];
    const [hovered, setHovered] = useState<number | null>(null);

    if (!onChange) {
        const clamped = Math.min(Math.max(value, 0), 5);
        return (
            <span role="img" aria-label={`Rated ${clamped.toFixed(1)} out of 5`} className="relative inline-flex">
                <StarRow px={px} color={EMPTY} />
                {/* The gold row over the grey one, cut at the rating. */}
                <span className="absolute inset-y-0 left-0 overflow-hidden" style={{ width: `${(clamped / 5) * 100}%` }}>
                    <StarRow px={px} color={FILLED} />
                </span>
            </span>
        );
    }

    const shown = hovered ?? value;
    return (
        <span role="radiogroup" aria-label={label} className="inline-flex" onMouseLeave={() => setHovered(null)}>
            {STARS.map((star) => (
                <button
                    key={star}
                    type="button"
                    role="radio"
                    aria-checked={value === star}
                    aria-label={`${star} star${star === 1 ? "" : "s"}`}
                    onMouseEnter={() => setHovered(star)}
                    onFocus={() => setHovered(star)}
                    onBlur={() => setHovered(null)}
                    onClick={() => onChange(star)}
                    className="p-0.5 transition-transform hover:scale-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary rounded"
                >
                    <MdStar size={px} color={star <= shown ? FILLED : EMPTY} />
                </button>
            ))}
        </span>
    );
};

export default StarRating;
