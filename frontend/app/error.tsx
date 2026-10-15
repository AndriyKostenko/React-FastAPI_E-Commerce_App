"use client";

import { useEffect } from "react";
import ErrorPanel from "@/components/ui/ErrorPanel";

/**
 * A page that failed while rendering, shown inside the normal layout (header,
 * styles and all) instead of Next's unstyled fallback.
 */
export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <ErrorPanel
      title="Something went wrong"
      message="This page could not be loaded. It is usually temporary; please try again."
      onRetry={retry}
      reference={error.digest}
    />
  );
}
