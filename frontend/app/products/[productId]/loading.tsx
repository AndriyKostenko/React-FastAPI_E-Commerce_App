import { DetailSkeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="py-8">
      <DetailSkeleton label="Loading product…" />
    </div>
  );
}
