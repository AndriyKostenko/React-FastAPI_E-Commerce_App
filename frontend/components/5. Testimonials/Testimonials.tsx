import Image from "next/image";
import { MdStar, MdStarHalf, MdGroup } from "react-icons/md";
import { TESTIMONIALS } from "@/utils/constants";

const StarRating = ({ count }: { count: number }) => (
    <div className="flex gap-1 text-brand-lime">
        {Array.from({ length: 5 }).map((_, i) => {
            if (i < Math.floor(count)) return <MdStar key={i} size={20} />;
            if (i < count) return <MdStarHalf key={i} size={20} />;
            return <MdStar key={i} size={20} className="opacity-30" />;
        })}
    </div>
);

const Testimonials = () => (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="glass-card p-8 space-y-6 flex flex-col justify-between">
            <div className="space-y-4">
                <StarRating count={TESTIMONIALS[0].stars} />
                <p className="font-body-lg italic text-primary">
                    "{TESTIMONIALS[0].quote}"
                </p>
            </div>
            <div className="flex items-center gap-4 pt-4 border-t border-white/30">
                <div className="w-12 h-12 rounded-full overflow-hidden relative flex-shrink-0">
                    <Image
                        src={TESTIMONIALS[0].avatar}
                        alt={TESTIMONIALS[0].name}
                        fill
                        className="object-cover"
                    />
                </div>
                <div>
                    <p className="font-label-bold text-primary">
                        {TESTIMONIALS[0].name}
                    </p>
                    <p className="text-xs text-secondary">
                        {TESTIMONIALS[0].role}
                    </p>
                </div>
            </div>
        </div>

        <div className="glass-card bg-brand-lime p-8 space-y-6 flex flex-col justify-center items-center text-center">
            <div className="w-20 h-20 bg-black text-white rounded-full flex items-center justify-center">
                <MdGroup size={40} />
            </div>
            <div className="space-y-2">
                <h3 className="font-headline-lg text-black">
                    Join 50k+ Creators
                </h3>
                <p className="text-black/70 font-body-md">
                    Be part of the future of fashion. Start generating your own
                    unique styles today.
                </p>
            </div>
            <button className="bg-black text-white px-8 py-3 rounded-full font-label-bold hover:shadow-lg hover:bg-neutral-800 transition-all active:scale-95">
                Get Started
            </button>
        </div>

        <div className="glass-card p-8 space-y-6 flex flex-col justify-between">
            <div className="space-y-4">
                <StarRating count={TESTIMONIALS[1].stars} />
                <p className="font-body-lg italic text-primary">
                    "{TESTIMONIALS[1].quote}"
                </p>
            </div>
            <div className="flex items-center gap-4 pt-4 border-t border-white/30">
                <div className="w-12 h-12 rounded-full overflow-hidden relative flex-shrink-0">
                    <Image
                        src={TESTIMONIALS[1].avatar}
                        alt={TESTIMONIALS[1].name}
                        fill
                        className="object-cover"
                    />
                </div>
                <div>
                    <p className="font-label-bold text-primary">
                        {TESTIMONIALS[1].name}
                    </p>
                    <p className="text-xs text-secondary">
                        {TESTIMONIALS[1].role}
                    </p>
                </div>
            </div>
        </div>
    </section>
);

export default Testimonials;
