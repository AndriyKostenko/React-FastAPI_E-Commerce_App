import { GridSkeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="py-8">
      <GridSkeleton label="Loading your wishlist…" items={4} />
    </div>
  );
}
