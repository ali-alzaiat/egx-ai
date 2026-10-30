import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/** Our badge recipe (Cobalt Cards): 24px tall, 8px radius, tinted by meaning. `default` is the neutral tag. */
const badgeVariants = cva(
  "inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-[var(--badge-radius)] px-2.5 text-meta font-semibold",
  {
    variants: {
      variant: {
        default: "bg-secondary text-text-2",
        gain: "bg-gain-bg text-gain",
        loss: "bg-loss-bg text-loss",
        neutral: "bg-secondary text-neutral",
        none: "border border-border bg-transparent text-muted-foreground",
        accent: "bg-brand-bg text-primary",
        warn: "bg-warn-bg text-warn",
        muted: "bg-secondary text-muted-foreground",
        outline: "border border-border bg-transparent text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
