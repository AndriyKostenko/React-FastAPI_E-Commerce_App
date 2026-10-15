import { StackSkeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="py-8">
      <StackSkeleton label="Loading your account…" cards={4} />
    </div>
  );
}
