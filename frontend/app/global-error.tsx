"use client";

import "./globals.css";
import ErrorPanel from "@/components/ui/ErrorPanel";

/**
 * The last resort, when the root layout itself failed. It replaces the layout,
 * so it brings its own document and the global stylesheet.
 */
export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <html lang="en">
      <body className="font-body-md text-on-surface gradient-bg p-4 md:p-8 min-h-screen">
        <title>Something went wrong | AIGEN</title>
        <ErrorPanel
          title="Something went wrong"
          message="The shop could not be loaded. Please try again in a moment."
          onRetry={retry}
          reference={error.digest}
        />
      </body>
    </html>
  );
}
