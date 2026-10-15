import { StackSkeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="py-4 sm:p-8">
      <StackSkeleton label="Loading your order…" cards={3} />
    </div>
  );
}
