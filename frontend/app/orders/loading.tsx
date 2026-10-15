import { StackSkeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="pt-8">
      <StackSkeleton label="Loading your orders…" cards={2} />
    </div>
  );
}
