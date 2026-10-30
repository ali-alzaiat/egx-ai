import * as React from "react";

import { cn } from "@/lib/utils";

/** A loading bar. A span, so it can sit inside table cells and inline text; the pulse stops under reduced motion. */
function Skeleton({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="skeleton"
      aria-hidden="true"
      className={cn("block h-3 rounded-sm bg-muted motion-safe:animate-pulse", className)}
      {...props}
    />
  );
}

export { Skeleton };
