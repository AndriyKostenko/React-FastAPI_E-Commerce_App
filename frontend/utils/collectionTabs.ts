import type { BestSeller, FilterTab, ProductSummary } from "@/types/product";
import calculateAverageRating from "@/utils/productRating";

/** How many products the Best Sellers tab shows, sellers first, topped up with top rated. */
export const BEST_SELLERS_SIZE = 8;

const TOP_RATED_MIN_RATING = 4.5;
const NEW_ARRIVAL_WINDOW_DAYS = 30;

/** What every tab picks its products from. */
export interface CollectionSource {
    products: ProductSummary[];
    bestSellers: BestSeller[];
    /** Read once per mount, so a list never depends on render timing. */
    now: number;
}

interface CollectionTab {
    tab: FilterTab;
    /** The `?collection=` value that opens this tab; null for All (no parameter). */
    slug: string | null;
    select: (source: CollectionSource) => ProductSummary[];
}

const averageRating = (product: ProductSummary): number => calculateAverageRating(product.reviews ?? []);

const topRated = ({ products }: CollectionSource): ProductSummary[] =>
    products
        .filter((product) => averageRating(product) >= TOP_RATED_MIN_RATING)
        .toSorted((left, right) => averageRating(right) - averageRating(left));

/** Sellers in rank order; while there are fewer than the tab holds, top-rated others fill the rest. */
const bestSellers = (source: CollectionSource): ProductSummary[] => {
    const sellers = source.bestSellers.map(({ product }) => product);
    const sold = new Set(sellers.map((product) => product.id));
    const topUp = topRated(source).filter((product) => !sold.has(product.id));
    return [...sellers, ...topUp].slice(0, BEST_SELLERS_SIZE);
};

const newArrivals = ({ products, now }: CollectionSource): ProductSummary[] => {
    const cutoff = now - NEW_ARRIVAL_WINDOW_DAYS * 86_400_000;
    return products
        .filter((product) => new Date(product.date_created).getTime() >= cutoff)
        .toSorted((left, right) => new Date(right.date_created).getTime() - new Date(left.date_created).getTime());
};

/** Each tab's products (Strategy), in the order the tabs are shown. */
export const COLLECTION_TABS: ReadonlyArray<CollectionTab> = [
    { tab: "All", slug: null, select: ({ products }) => products },
    { tab: "Best Sellers", slug: "best-sellers", select: bestSellers },
    { tab: "Top Rated", slug: "top-rated", select: topRated },
    { tab: "New Arrivals", slug: "new-arrivals", select: newArrivals },
];

const strategyFor = (tab: FilterTab): CollectionTab | undefined => COLLECTION_TABS.find((entry) => entry.tab === tab);

// Links made before Best Sellers existed opened the rating tab as "trending".
const LEGACY_SLUGS: Readonly<Record<string, FilterTab>> = { trending: "Best Sellers" };

/** The tab a `?collection=` value opens; anything unknown opens All. */
export const tabForSlug = (slug: string | null): FilterTab => {
    if (slug === null) return "All";
    return COLLECTION_TABS.find((entry) => entry.slug === slug)?.tab ?? LEGACY_SLUGS[slug] ?? "All";
};

export const slugForTab = (tab: FilterTab): string | null => strategyFor(tab)?.slug ?? null;

export const selectCollection = (tab: FilterTab, source: CollectionSource): ProductSummary[] =>
    strategyFor(tab)?.select(source) ?? source.products;
