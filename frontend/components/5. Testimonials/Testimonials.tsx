import Link from "next/link";
import { MdStar, MdStarHalf, MdBrush } from "react-icons/md";
import type { FeaturedReview } from "@/types/review";

const StarRating = ({ count }: { count: number }) => (
    <div role="img" className="flex gap-1 text-brand-lime" aria-label={`Rated ${count} out of 5`}>
        {Array.from({ length: 5 }).map((_, i) => {
            if (i < Math.floor(count)) return <MdStar key={i} size={20} />;
            if (i < count) return <MdStarHalf key={i} size={20} />;
            return <MdStar key={i} size={20} className="opacity-30" />;
        })}
    </div>
);

const reviewDate = (iso: string): string =>
    new Date(iso).toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });

const ReviewCard = ({ review }: { review: FeaturedReview }) => (
    <div className="glass-card p-8 space-y-6 flex flex-col justify-between">
        <div className="space-y-4">
            <StarRating count={review.rating} />
            <p className="font-body-lg italic text-primary line-clamp-6">
                &ldquo;{review.comment}&rdquo;
            </p>
        </div>
        <div className="pt-4 border-t border-white/30 space-y-1">
            <p className="font-label-bold text-primary">Customer review</p>
            <p className="text-xs text-secondary">
                <Link href={`/products/${review.product.id}`} className="underline hover:text-primary">
                    {review.product.name}
                </Link>
                {" · "}
                {reviewDate(review.date_created)}
            </p>
        </div>
    </div>
);

const DesignCallToAction = () => (
    <div className="glass-card bg-brand-lime p-8 space-y-6 flex flex-col justify-center items-center text-center">
        <div className="w-20 h-20 bg-black text-white rounded-full flex items-center justify-center">
            <MdBrush size={40} />
        </div>
        <div className="space-y-2">
            <h3 className="font-headline-lg text-black">Design your own</h3>
            <p className="text-black/70 font-body-md">
                Describe an idea and our AI turns it into a print for your own T-shirt.
            </p>
        </div>
        <Link
            href="/#create-design"
            className="bg-black text-white px-8 py-3 rounded-full font-label-bold hover:shadow-lg hover:bg-neutral-800 transition-all active:scale-95"
        >
            Start designing
        </Link>
    </div>
);

// Tailwind only ships classes it can see written out, so no template string.
const COLUMNS: Record<number, string> = {
    1: "md:grid-cols-2",
    2: "md:grid-cols-3",
};

/**
 * Real customer reviews around a design call to action. With no reviews the
 * section is not shown at all: nothing here is ever invented.
 */
const Testimonials = ({ reviews }: { reviews: FeaturedReview[] }) => {
    if (reviews.length === 0) return null;
    const [first, ...rest] = reviews;

    return (
        <section className={`grid grid-cols-1 ${COLUMNS[reviews.length] ?? "md:grid-cols-3"} gap-8`}>
            <ReviewCard review={first} />
            <DesignCallToAction />
            {rest.map((review) => (
                <ReviewCard key={review.id} review={review} />
            ))}
        </section>
    );
};

export default Testimonials;
