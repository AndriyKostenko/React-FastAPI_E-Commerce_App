/**
 * Placeholder blocks shown while a page's server data loads (Next renders a
 * route's loading.tsx instantly, then swaps in the page). Composable: a page
 * skeleton is a few of these in the shape of the real page.
 */

interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = "" }) => (
  <div aria-hidden="true" className={`animate-pulse rounded-2xl bg-white/50 ${className}`} />
);

/** Announces the loading state to screen readers once, for the whole page. */
const Loading: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div role="status" aria-live="polite" className="w-full">
    <span className="sr-only">{label}</span>
    {children}
  </div>
);

/** A heading and a stack of cards: account, orders, generic pages. */
export const StackSkeleton: React.FC<{ label?: string; cards?: number }> = ({ label = "Loading…", cards = 3 }) => (
  <Loading label={label}>
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      <Skeleton className="h-8 w-56" />
      {Array.from({ length: cards }, (_, index) => (
        <div key={index} className="glass-card p-6 flex flex-col gap-3">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ))}
    </div>
  </Loading>
);

/** A grid of product cards: wishlist, collections. */
export const GridSkeleton: React.FC<{ label?: string; items?: number }> = ({ label = "Loading…", items = 8 }) => (
  <Loading label={label}>
    <div className="flex flex-col gap-6">
      <Skeleton className="h-8 w-56" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
        {Array.from({ length: items }, (_, index) => (
          <div key={index} className="glass-card p-4 flex flex-col gap-3">
            <Skeleton className="aspect-[4/5] w-full rounded-3xl" />
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-5 w-1/3" />
          </div>
        ))}
      </div>
    </div>
  </Loading>
);

/** An image beside a column of details: the product page. */
export const DetailSkeleton: React.FC<{ label?: string }> = ({ label = "Loading…" }) => (
  <Loading label={label}>
    <div className="glass-card p-6 md:p-8 grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12">
      <Skeleton className="aspect-square w-full rounded-3xl" />
      <div className="flex flex-col gap-4">
        <Skeleton className="h-9 w-3/4" />
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-12 w-full mt-4" />
      </div>
    </div>
  </Loading>
);
